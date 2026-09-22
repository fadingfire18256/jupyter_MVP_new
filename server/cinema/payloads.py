"""HTTP 輸入驗證；由 05_接成服務.ipynb 產生。"""
import json

from django.http import JsonResponse


def read_object(request):
    if request.content_type != "application/json":
        return None, JsonResponse({"error": "請使用 application/json"}, status=415)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse({"error": "無效的 JSON"}, status=400)
    if not isinstance(body, dict):
        return None, JsonResponse({"error": "JSON 最外層必須是物件"}, status=400)
    return body, None


def chat_input(body):
    """回傳 (已驗證資料, error)。輸入 shape 不正確時不呼叫模型。"""
    messages = body.get("messages", [])
    if not isinstance(messages, list) or len(messages) > 100:
        return None, "messages 必須是最多 100 筆的陣列"
    for message in messages:
        if (not isinstance(message, dict) or message.get("role") not in ("user", "assistant")
                or not isinstance(message.get("content"), str)):
            return None, "每則訊息必須包含 role 與文字 content"
        if len(message["content"]) > 20000:
            return None, "訊息過長"
    latest = next((m["content"].strip() for m in reversed(messages) if m["role"] == "user"), "")
    if not latest:
        return None, "沒有使用者訊息"
    session = body.get("session_id", "")
    if not isinstance(session, str) or len(session) > 100:
        return None, "session_id 必須是最多 100 字的文字"
    movies = body.get("movies", [])
    if not isinstance(movies, list) or len(movies) > 200:
        return None, "movies 必須是最多 200 筆的陣列"
    for movie in movies:
        if not isinstance(movie, dict) or not isinstance(movie.get("title"), str):
            return None, "每部電影必須包含文字 title"
        meta = movie.get("meta")
        if meta is not None and not isinstance(meta, dict):
            return None, "電影 meta 必須是物件或 null"
        meta = meta or {}
        for field in ("title", "release_date", "overview"):
            if meta.get(field) is not None and not isinstance(meta[field], str):
                return None, f"meta.{field} 必須是文字"
        rating = meta.get("vote_average")
        if rating is not None and (type(rating) not in (int, float) or not 0 <= rating <= 10):
            return None, "評分必須是 0 到 10 的數字"
        genres = meta.get("genre_ids") or []
        if not isinstance(genres, list) or any(type(g) is not int for g in genres):
            return None, "genre_ids 必須是整數陣列"
        sources = movie.get("sources", [])
        if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
            return None, "sources 必須是文字陣列"
    names = body.get("genres", {})
    if not isinstance(names, dict) or any(not (k.isascii() and k.isdecimal() and len(k) <= 10) or not isinstance(v, str) for k, v in names.items()):
        return None, "genres 必須是數字 id 對應文字名稱的物件"
    return {"message": latest, "movies": movies, "genres": {int(k): v for k, v in names.items()},
            "session_id": session.strip() or None}, None
