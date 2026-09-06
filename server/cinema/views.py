"""API 視圖 —— 全部都是薄殼。

注意每一支的長度：真正的邏輯都在 movieapp/ 裡，
這裡只負責「把 HTTP 請求翻譯成函式呼叫，再把結果包成 JSON」。

這就是為什麼要把邏輯抽出去：同一份程式碼，
notebook 直接 import 來用，這個服務也 import 來用，
改一個地方兩邊同時生效。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

import json
import time
from pathlib import Path

from django.http import FileResponse, Http404, JsonResponse

from movieapp import gemini, merge, sources, tmdb

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _json(payload, error=None, status_on_error=502):
    """統一的回應格式：有錯誤就帶上 error 欄位和非 200 狀態碼。"""
    if error:
        return JsonResponse(dict(payload, error=error), status=status_on_error)
    return JsonResponse(payload)


# --------------------------------------------------------------------------
# 影城（01）
# --------------------------------------------------------------------------
def showtimes(request):
    titles, error = sources.showtimes()
    return _json({"movies": titles}, error)


def miramar(request):
    titles, error = sources.miramar()
    return _json({"movies": titles}, error)


# --------------------------------------------------------------------------
# TMDB（02）
# --------------------------------------------------------------------------
def tmdb_search(request):
    query = request.GET.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "缺少 query 參數", "results": []}, status=400)

    language = request.GET.get("language", "zh-TW")
    results, error = tmdb.search(query, language=language)
    if error:
        return _json({"results": []}, error)

    # 前端只取 results[0]，所以這裡先把最像的排到最前面。
    # 不這樣做的話，TMDB 自己的相關度排序常常會讓「藍色監獄」
    # 拿到一部完全無關的電影。
    best = tmdb.best_match(query, results)
    if best is not None:
        results = [best] + [m for m in results if m.get("id") != best.get("id")]
    else:
        results = []

    return JsonResponse({"results": results})


def tmdb_genres(request):
    language = request.GET.get("language", "zh-TW")
    names, error = tmdb.genres(language=language)
    if error:
        return _json({"genres": []}, error)
    # 前端要的是 [{id, name}, ...] 這種形狀
    return JsonResponse({"genres": [{"id": k, "name": v} for k, v in names.items()]})


# --------------------------------------------------------------------------
# 整合後的電影清單（03）
# --------------------------------------------------------------------------
def movies(request):
    """前端唯一需要的資料端點：兩家影城 -> TMDB 補資料 -> 跨來源去重。

    整條流程都在 merge.catalog() 裡，這裡一樣只是薄殼。
    某一家影城掛掉不會讓整份清單失敗，錯誤放在 errors 欄位一起回去。
    """
    catalog, genre_names, errors = merge.catalog()
    return JsonResponse({
        "movies": catalog,
        "genres": [{"id": k, "name": v} for k, v in genre_names.items()],
        "labels": merge.SOURCE_LABELS,
        "errors": errors,
    })


# --------------------------------------------------------------------------
# 聊天（04）
# --------------------------------------------------------------------------
def chat(request):
    if request.method != "POST":
        return JsonResponse({"error": "請使用 POST"}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "無效的請求格式"}, status=400)

    messages = body.get("messages") or []
    latest = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            latest = str(message.get("content", "")).strip()
            break
    if not latest:
        return JsonResponse({"error": "沒有使用者訊息"}, status=400)

    reply, error = gemini.ask(
        latest,
        system=str(body.get("system", "")).strip() or None,
        session_id=str(body.get("session_id", "")).strip() or None,
    )
    return _json({"reply": reply}, error)


# --------------------------------------------------------------------------
# 伺服器時間（05）
# --------------------------------------------------------------------------
def server_time(request):
    """回傳伺服器目前時間（UNIX 毫秒），供前端校時使用。

    瀏覽器沒辦法直接用 NTP（那是 UDP 123），所以改用 HTTP 對時：
    前端記錄送出與收到的時間，扣掉來回延遲的一半，推算出時鐘誤差。
    """
    return JsonResponse({"now": int(time.time() * 1000)})


# --------------------------------------------------------------------------
# 前端網頁
# --------------------------------------------------------------------------
def index(request):
    """把 build 好的前端首頁送出去。"""
    page = STATIC_DIR / "index.html"
    if not page.exists():
        raise Http404("找不到前端網頁，請確認 server/static/index.html 存在")
    return FileResponse(page.open("rb"), content_type="text/html")
