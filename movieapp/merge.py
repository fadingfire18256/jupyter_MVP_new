"""跨影城的資料整合：合併、去重、篩選、排序。

同一部電影在兩家影城會出現兩次，而且片名可能不一樣。
光比字串沒辦法判斷是不是同一部，所以要用 TMDB 的電影 id 當作共同身分證。

本檔案由 notebooks/03_資料整合.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

import re

# 來源代號對應的顯示名稱
SOURCE_LABELS = {"showtimes": "秀泰影城", "miramar": "美麗華影城"}


def movie_key(movie):
    """一部電影的唯一身分。

    有 TMDB id 就用 id（跨影城通用），沒有的話退而求其次用片名。
    """
    tmdb_id = (movie.get("meta") or {}).get("id")
    return f"tmdb:{tmdb_id}" if tmdb_id is not None else f"title:{movie.get('title')}"


def merge_sources(enriched_by_source):
    """把各影城的電影清單合併成一份，同一部片只留一筆。

    enriched_by_source: {來源代號: [tmdb.enrich() 產生的電影, ...]}

    回傳的每一筆會多出 sources（在哪幾家上映）和 titles（各家的原始片名）。
    """
    merged = {}
    for source, movies in enriched_by_source.items():
        for movie in movies:
            key = movie_key(movie)
            existing = merged.get(key)
            if existing:
                if source not in existing["sources"]:
                    existing["sources"].append(source)
                existing["titles"].setdefault(source, movie.get("title"))
            else:
                merged[key] = {
                    "title": movie.get("title"),
                    "meta": movie.get("meta"),
                    "sources": [source],
                    "titles": {source: movie.get("title")},
                }
    return list(merged.values())


def source_labels(movie):
    """把來源代號換成中文名稱，例如 ['秀泰影城', '美麗華影城']。"""
    return [SOURCE_LABELS.get(s, s) for s in movie.get("sources", [])]


# --------------------------------------------------------------------------
# 篩選與排序
# --------------------------------------------------------------------------
def _release_month(date_str):
    """把 "2026-08-07" 換成可以直接比大小的月份序號。"""
    match = re.match(r"^(\d{4})-(\d{1,2})", str(date_str or "").strip())
    if not match:
        return None
    return int(match.group(1)) * 12 + int(match.group(2))


def apply_filters(
    movies,
    adult=None,
    genre_id=None,
    min_popularity=None,
    min_vote_average=None,
    since=None,
    sort_by=None,
    descending=True,
):
    """篩選並排序電影清單。

    adult             True/False 只留成人片或非成人片，None 不篩
    genre_id          只留包含這個類型的電影
    min_popularity    熱門度下限
    min_vote_average  評分下限
    since             上映日期下限，格式 "2026-01"
    sort_by           "popularity" / "vote_average" / "release_date"
    """
    since_month = _release_month(since) if since else None
    result = []

    for movie in movies:
        meta = movie.get("meta") or {}
        if adult is not None and bool(meta.get("adult")) is not bool(adult):
            continue
        if genre_id is not None and genre_id not in (meta.get("genre_ids") or []):
            continue
        if min_popularity is not None and (meta.get("popularity") or 0) < min_popularity:
            continue
        if min_vote_average is not None and (meta.get("vote_average") or 0) < min_vote_average:
            continue
        if since_month is not None:
            month = _release_month(meta.get("release_date"))
            if month is None or month < since_month:
                continue
        result.append(movie)

    if sort_by:
        def sort_key(movie):
            value = (movie.get("meta") or {}).get(sort_by)
            if sort_by == "release_date":
                return _release_month(value) or 0
            return value or 0

        result.sort(key=sort_key, reverse=descending)

    return result


def search_movies(movies, keyword):
    """用關鍵字比對影城片名和 TMDB 片名。"""
    query = str(keyword or "").strip().lower()
    if not query:
        return list(movies)
    return [
        m
        for m in movies
        if query in str(m.get("title", "")).lower()
        or query in str((m.get("meta") or {}).get("title", "")).lower()
    ]


def bounds(movies):
    """算出各欄位的實際範圍，畫面上的滑桿要用它決定刻度。"""
    populars = [(m.get("meta") or {}).get("popularity") or 0 for m in movies]
    years = []
    for m in movies:
        date = str((m.get("meta") or {}).get("release_date") or "")
        if len(date) >= 4 and date[:4].isdigit():
            years.append(int(date[:4]))
    return {
        "popularity_max": max(populars) if populars else 0,
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "count": len(movies),
    }


# --------------------------------------------------------------------------
# 給 pandas 用的表格形式
# --------------------------------------------------------------------------
def to_records(movies, genre_names=None):
    """把巢狀的電影資料攤平成一列一部電影，方便丟進 DataFrame。"""
    genre_names = genre_names or {}
    records = []
    for movie in movies:
        meta = movie.get("meta") or {}
        records.append(
            {
                "片名": movie.get("title"),
                "TMDB片名": meta.get("title"),
                "上映日期": meta.get("release_date") or None,
                "評分": meta.get("vote_average"),
                "評分人數": meta.get("vote_count"),
                "熱門度": meta.get("popularity"),
                "類型": "、".join(
                    genre_names.get(g, str(g)) for g in (meta.get("genre_ids") or [])
                ),
                "成人片": bool(meta.get("adult")),
                "上映影城": "、".join(source_labels(movie)),
                "tmdb_id": meta.get("id"),
            }
        )
    return records


def to_dataframe(movies, genre_names=None):
    """需要 pandas，沒安裝時給出明確訊息而不是 ImportError。"""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("需要 pandas，請執行 %pip install -r ../requirements.txt")
    return pd.DataFrame(to_records(movies, genre_names))

# --------------------------------------------------------------------------
# 整條流程
# --------------------------------------------------------------------------
def catalog(language="zh-TW", workers=8):
    """把整條流程串起來：抓兩家影城 -> TMDB 補資料 -> 跨來源合併去重。

    回傳 (movies, genre_names, errors)。

    網頁服務的 /api/movies/ 直接回傳這個結果，notebook 也呼叫同一個函式 ——
    兩邊跑的是同一段程式碼，不是兩份各自走鐘的複製品。
    這就是「邏輯只留一份」在這個專案裡最具體的樣子。

    任何一家影城掛掉都不會讓整份清單失敗：錯誤收集在 errors 裡回報，
    拿得到的資料照常回傳。
    """
    from movieapp import sources, tmdb

    by_source, errors = sources.titles_by_source()

    genre_names, genre_error = tmdb.genres(language=language)
    if genre_error:
        errors["TMDB 類型"] = genre_error

    enriched = {}
    for key, titles in by_source.items():
        movies, failures = tmdb.enrich(titles, language=language, workers=workers, source=key)
        enriched[key] = movies
        if failures:
            label = SOURCE_LABELS.get(key, key)
            errors[f"{label} TMDB 查詢"] = next(iter(failures.values()))

    return merge_sources(enriched), genre_names, errors
