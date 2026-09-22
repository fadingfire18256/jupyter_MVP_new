"""固定的虛構課堂資料；由 00_環境設定.ipynb 產生，不代表即時上映資訊。"""
from copy import deepcopy
import re

GENRES = {16: "動畫", 18: "劇情", 35: "喜劇", 878: "科幻"}
MOVIES = [
    {"id": 910001, "title": "星際郵差", "original_title": "Star Courier",
     "release_date": "2026-07-01", "vote_average": 8.2, "vote_count": 120,
     "popularity": 31.0, "genre_ids": [16, 878], "adult": False,
     "overview": "一位郵差與機器人合作，把一封信送到遙遠的星球。這是虛構的教學電影。",
     "poster_path": None, "backdrop_path": None},
    {"id": 910002, "title": "午後的書店", "original_title": "Afternoon Bookshop",
     "release_date": "2026-07-31", "vote_average": 7.6, "vote_count": 80,
     "popularity": 18.0, "genre_ids": [18], "adult": False,
     "overview": "兩位陌生人在小書店交換閱讀筆記。這是虛構的教學電影。",
     "poster_path": None, "backdrop_path": None},
    {"id": 910003, "title": "雨天練習曲", "original_title": "Rainy Rehearsal",
     "release_date": "2026-08-05", "vote_average": 6.8, "vote_count": 40,
     "popularity": 12.0, "genre_ids": [18, 35], "adult": False,
     "overview": "社區樂團在雨天準備第一次演出。這是虛構的教學電影。",
     "poster_path": None, "backdrop_path": None},
]

def showtimes_payload():
    return {"success": True, "payload": {
        "programs": [
            {"name": "星際郵差 (國語版)", "nameAlternative": "Star Courier"},
            {"name": "星際郵差 特別場", "nameAlternative": "Star Courier"},
            {"name": "午後的書店", "nameAlternative": "Afternoon Bookshop"},
        ],
        "cinemas": [{"name": "示範影城"}],
        "eventsForCorporations": [{"name": "不是電影的活動"}],
    }}

def miramar_payload():
    return {"movies": [{"TitleAlt": "星際 郵差"}, {"TitleAlt": "雨天練習曲"}]}

def search_results(query):
    normalize = lambda value: re.sub(r"\s+", "", str(value)).casefold()
    needle = normalize(query)
    return deepcopy([m for m in MOVIES if needle and any(
        needle in normalize(m[field]) for field in ("title", "original_title"))])

def response_for(url, params=None):
    """只回傳已知範例；示範模式不會偷偷改成真實連線。"""
    params = params or {}
    if url == "https://capi.showtimes.com.tw/4/app/bootstrap":
        return showtimes_payload(), None
    if url == "https://www.miramarcinemas.tw/api/Booking/GetMovie/":
        return miramar_payload(), None
    if url == "https://api.themoviedb.org/3/search/movie":
        return {"results": search_results(params.get("query", ""))}, None
    if url == "https://api.themoviedb.org/3/genre/movie/list":
        return {"genres": [{"id": k, "name": v} for k, v in GENRES.items()]}, None
    return None, "示範模式未定義這個端點；請改用教材範例或明確切換 live 模式。"

def chat_reply(message, system=None):
    """展示資料傳遞，沒有呼叫模型，也不模擬真正的推理或多輪記憶。"""
    lines = [line for line in (system or "").splitlines() if re.match(r"^\d+\.", line)]
    prefix = "【示範回應・未呼叫 AI】"
    if not lines:
        return prefix + "目前沒有提供電影資料，請先載入或調整篩選條件。"
    return (prefix + "收到問題：「" + message[:100] + "」。" +
            "本次提示包含 " + str(len(lines)) + " 部電影；第一筆資料是：\n" + lines[0] +
            "\n這是固定程式展示資料傳遞；切換 live 模式後才會由 Gemini 回答。")
