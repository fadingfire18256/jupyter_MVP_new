"""TMDB（The Movie Database）查詢。

跟 01 的影城 API 完全相反：這是一支正規 API ——
有公開文件、要金鑰、有速率限制、回應結構穩定。

金鑰用 Read Access Token，放在 Authorization header（不是網址參數），
所以就算程式出錯把網址印出來，也不會把金鑰一起印出去。

本檔案由 notebooks/02_TMDB.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

import difflib
import re
import time
from concurrent.futures import ThreadPoolExecutor

from movieapp import config
from movieapp.http import fetch_json

SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
GENRE_URL = "https://api.themoviedb.org/3/genre/movie/list"

# 海報與劇照的圖片網址前綴（w92 小圖、w300 中圖、original 原始尺寸）
IMAGE_BASE = "https://image.tmdb.org/t/p/"

# 同一個片名在一次上課中會被查很多次，用簡單的 TTL 快取擋掉重複請求
_CACHE = {}
_CACHE_TTL = 3600  # 秒

# 判定「這筆結果算不算命中」的相似度門檻
MATCH_THRESHOLD = 0.6

# TMDB 的 zh-TW 類型名稱實際回的是簡體中文（zh-Hant、zh-HK 也一樣），
# 這是它資料端的限制，改參數沒用。總共只有 19 個，直接補一張正體對照表。
# 對照的是類型 id 而不是名稱，因為 id 是穩定的。
ZH_TW_GENRES = {
    28: "動作", 12: "冒險", 16: "動畫", 35: "喜劇", 80: "犯罪",
    99: "紀錄", 18: "劇情", 10751: "家庭", 14: "奇幻", 36: "歷史",
    27: "恐怖", 10402: "音樂", 9648: "懸疑", 10749: "愛情", 878: "科幻",
    10770: "電視電影", 53: "驚悚", 10752: "戰爭", 37: "西部",
}


def _headers():
    return {
        "Authorization": f"Bearer {config.tmdb_token()}",
        "accept": "application/json",
    }


def clear_cache():
    _CACHE.clear()


def search(query, language="zh-TW", use_cache=True):
    """用片名查 TMDB。回傳 (results, error)。"""
    query = str(query or "").strip()
    if not query:
        return [], "缺少查詢字串"

    cache_key = f"{query.lower()}|{language}"
    if use_cache:
        hit = _CACHE.get(cache_key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return hit[1], None

    data, error = fetch_json(
        SEARCH_URL,
        params={"query": query, "language": language},
        headers=_headers(),
    )
    if error:
        return [], error

    results = data.get("results", []) if isinstance(data, dict) else []
    _CACHE[cache_key] = (time.time(), results)
    return results, None


def genres(language="zh-TW"):
    """類型 id 對照表。回傳 ({id: 名稱}, error)。"""
    data, error = fetch_json(
        GENRE_URL,
        params={"language": language},
        headers=_headers(),
    )
    if error:
        return {}, error
    return {
        g["id"]: ZH_TW_GENRES.get(g["id"], g["name"]) for g in data.get("genres", [])
    }, None


# --------------------------------------------------------------------------
# 比對：為什麼不能直接拿 results[0]
# --------------------------------------------------------------------------
def _normalize(text):
    """比對前先把標點、空白、大小寫的差異抹平。"""
    return re.sub(r"[\s　:：,，.。!！?？'\"’\-—－]", "", str(text or "")).lower()


def match_score(query, movie):
    """片名和某筆搜尋結果的相似度，0.0 ~ 1.0。"""
    q = _normalize(query)
    title = _normalize(movie.get("title"))
    original = _normalize(movie.get("original_title"))
    if not q:
        return 0.0
    if q == title or q == original:
        return 1.0
    if q in title or title in q or q in original or original in q:
        return 0.9
    return max(
        difflib.SequenceMatcher(None, q, title).ratio(),
        difflib.SequenceMatcher(None, q, original).ratio(),
    )


def best_match(query, results, threshold=MATCH_THRESHOLD):
    """從搜尋結果裡挑最像的一筆，都不夠像就回 None。

    原始版本直接取 results[0]，但 TMDB 的排序是它自己的相關度，
    不保證第一筆就是你要的那部片。相似度太低時寧可回 None，
    也不要放一部完全無關的電影到畫面上。
    """
    if not results:
        return None
    ranked = sorted(
        results,
        key=lambda m: (match_score(query, m), m.get("popularity", 0)),
        reverse=True,
    )
    top = ranked[0]
    return top if match_score(query, top) >= threshold else None


def lookup(title, language="zh-TW"):
    """查一個片名，回傳 (最佳結果或 None, error)。"""
    results, error = search(title, language=language)
    if error:
        return None, error
    return best_match(title, results), None


# --------------------------------------------------------------------------
# 批次補資料
# --------------------------------------------------------------------------
def enrich(titles, language="zh-TW", workers=8, source=None):
    """把一串片名補成完整的電影資料。

    回傳 ([{"title": 影城片名, "meta": TMDB 資料, "source": 來源}, ...], errors)，
    查不到的片會被略過。

    workers=1 會退回逐筆查詢，用來對比平行查詢的速度差異。
    """
    titles = list(titles)
    if not titles:
        return [], {}

    def one(title):
        return title, lookup(title, language=language)

    if workers and workers > 1:
        with ThreadPoolExecutor(workers) as pool:
            pairs = list(pool.map(one, titles))
    else:
        pairs = [one(t) for t in titles]

    movies = []
    errors = {}
    for title, (meta, error) in pairs:
        if error:
            errors[title] = error
        elif meta:
            movies.append({"title": title, "meta": meta, "source": source})
    return movies, errors


def poster_url(meta, size="w300"):
    """海報網址；沒有海報回傳 None。"""
    path = (meta or {}).get("poster_path")
    return f"{IMAGE_BASE}{size}{path}" if path else None
