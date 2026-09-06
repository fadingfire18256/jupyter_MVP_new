"""Gemini 聊天：把目前的電影清單交給模型，讓它根據這些資料回答。

用的是 Interactions API。它和一般 chat API 最大的差別是
「對話記憶由伺服器保管」：每次回應會給一個 interaction id，
下一次帶上 previous_interaction_id 就能接續前文，
不必自己把整段對話重新送一遍。

本檔案由 notebooks/04_Gemini對話.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

import time
from datetime import datetime

from movieapp import config
from movieapp.http import fetch_json

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# 模型會下架。gemini-2.5-flash 和 gemini-2.0-flash 都已經對新使用者關閉，
# 呼叫會收到 404 not_found。主模型不可用時自動往後試。
MODELS = ["gemini-3.6-flash", "gemini-flash-latest"]

# 每個 session_id 目前接到哪一輪對話
_INTERACTION_IDS = {}

# 一次對話最多帶幾部電影進 system prompt，避免 prompt 過長
MAX_MOVIES_IN_PROMPT = 60

# 模型回一段話要花的時間比一般 API 長很多
REPLY_TIMEOUT = 90


def reset_session(session_id=None):
    """清掉對話記憶，讓下一句重新開始。"""
    if session_id is None:
        _INTERACTION_IDS.clear()
    else:
        _INTERACTION_IDS.pop(session_id, None)


def build_system_prompt(movies, genre_names=None, now=None):
    """把目前的電影整理成一段文字，當作模型的背景知識。

    這就是最陽春的 RAG：模型本身不知道今天有哪些電影在上映，
    我們把資料放進 system prompt，它才能根據實際片單回答。
    """
    genre_names = genre_names or {}
    if not movies:
        return ""

    lines = []
    for index, movie in enumerate(movies[:MAX_MOVIES_IN_PROMPT], 1):
        meta = movie.get("meta") or {}
        parts = []
        if meta.get("title"):
            parts.append(f"片名: {meta['title']}")
        if meta.get("release_date"):
            parts.append(f"上映日期: {meta['release_date']}")
        if meta.get("vote_average") is not None:
            parts.append(f"評分: {meta['vote_average']:.1f}")
        if meta.get("genre_ids"):
            names = "、".join(genre_names.get(g, str(g)) for g in meta["genre_ids"])
            parts.append(f"類型: {names}")
        if movie.get("sources"):
            from movieapp.merge import source_labels

            parts.append(f"上映影城: {'、'.join(source_labels(movie))}")
        if meta.get("overview"):
            parts.append(f"簡介: {meta['overview'][:200]}")
        detail = f"（{'，'.join(parts)}）" if parts else ""
        lines.append(f"{index}. {movie.get('title')}{detail}")

    stamp = (now or datetime.now()).strftime("%Y年%m月%d日 %H:%M:%S")
    return (
        f"你是電影推薦助手，請用繁體中文回答。目前時間：{stamp}。\n"
        "以下是目前頁面顯示的電影資料，請依據這些資料回答使用者的問題"
        "（例如推薦、比較、說明）。資料裡沒有的電影不要編造。\n"
        + "\n".join(lines)
    )


def _describe_error(error):
    """把 API 錯誤翻譯成看得懂的說明。"""
    text = str(error or "")
    if "429" in text:
        return (
            "Gemini 配額已用完（429）。免費額度是綁在金鑰上計算的，"
            "全班共用一把金鑰時很容易同時撞到。可以等幾分鐘再試，或改用自己的金鑰。"
        )
    if "404" in text or "not found" in text.lower():
        return f"模型不存在或已下架：{text}"
    return text


def extract_reply(data):
    """從 Interactions API 的回應裡取出模型講的話。

    回應是一連串 steps，我們只要 type 為 model_output 的文字部分。
    """
    steps = (data or {}).get("steps") or []
    return "".join(
        part.get("text", "")
        for step in steps
        if step.get("type") == "model_output"
        for part in (step.get("content") or [])
        if part.get("type") == "text"
    ).strip()


def ask(message, system=None, session_id=None, models=None, retries=1):
    """問一句話，回傳 (reply, error)。

    session_id 相同時會自動接續前一輪對話。
    """
    message = str(message or "").strip()
    if not message:
        return "", "沒有訊息內容"

    payload_base = {"input": message}
    if system:
        payload_base["system_instruction"] = system
    if session_id and session_id in _INTERACTION_IDS:
        payload_base["previous_interaction_id"] = _INTERACTION_IDS[session_id]

    last_error = "Gemini 無回應"
    for model in models or MODELS:
        for attempt in range(retries + 1):
            payload = dict(payload_base, model=model)
            data, error = fetch_json(
                API_URL,
                method="POST",
                headers={
                    "x-goog-api-key": config.gemini_key(),
                    "Content-Type": "application/json",
                },
                json_body=payload,
                # 語言模型要花時間想，20 秒的預設值不夠
                timeout=REPLY_TIMEOUT,
            )

            if error:
                last_error = error
                # 伺服器忙碌（500）值得重試；配額或模型問題重試沒用
                if "500" in str(error) and attempt < retries:
                    time.sleep(2)
                    continue
                break

            reply = extract_reply(data)
            interaction_id = (data or {}).get("id") or ""
            if session_id and interaction_id:
                _INTERACTION_IDS[session_id] = interaction_id
            if reply:
                return reply, None
            last_error = "Gemini 回應中沒有文字內容"
            break

        # 模型不可用才換下一個試
        if "404" not in str(last_error) and "429" not in str(last_error):
            break

    return "", _describe_error(last_error)


# 畫面上聊天面板的快捷問題
QUICK_PROMPTS = [
    "推薦一部高分電影",
    "推薦黑暗風格的電影",
    "推薦喜劇片",
    "哪部電影評分最高？",
    "推薦今天上映的電影",
    "推薦動作片",
]
