"""兩家影城的片名抓取。

秀泰   GET   https://capi.showtimes.com.tw/4/app/bootstrap        -> programs[].name
美麗華 POST  https://www.miramarcinemas.tw/api/Booking/GetMovie/  -> TitleAlt

兩支都沒有公開文件，結構是逆向觀察出來的。

本檔案由 notebooks/01_影城API.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

import re

from movieapp.http import BROWSER_HEADERS, fetch_json

SHOWTIMES_URL = "https://capi.showtimes.com.tw/4/app/bootstrap"
MIRAMAR_URL = "https://www.miramarcinemas.tw/api/Booking/GetMovie/"

# 影城片名常帶「放映場次」的註記，這些字對查電影資料庫只會幫倒忙：
#   驀然回首 友誼場 / 藍色監獄 Ado應援特別場 / 劇場版 吉伊卡哇 (國語版)
#   攻殼機動隊(1995) 4K 數位修復版 / 超時空甩尾 經典重映
_PAREN = re.compile(r"[（(][^（()）]*[)）]")
_TAIL = re.compile(r"[\s　_]+\S*(場|版|重映|加映|上映)\d*\s*$")
_FORMAT = re.compile(r"[\s　]+(4K|IMAX|3D|2D|DTS|ATMOS)\s*$", re.I)


def collect_keys(obj, target_key, result=None):
    """遞迴走訪整個 JSON，收集所有名為 target_key 的欄位值。"""
    if result is None:
        result = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == target_key:
                result.append(value)
            collect_keys(value, target_key, result)
    elif isinstance(obj, list):
        for item in obj:
            collect_keys(item, target_key, result)

    return result


def clean_title(name):
    """把影城的片名整理成適合查詢電影資料庫的形式。

    反覆套用三條規則直到不再變化，因為註記常常疊在一起
    （例如「攻殼機動隊(1995) 4K 數位修復版 粉絲紀念場」要剝三層）。
    """
    title = str(name or "").strip()
    previous = None
    while previous != title:
        previous = title
        title = _PAREN.sub(" ", title).strip()
        title = _TAIL.sub("", title).strip()
        title = _FORMAT.sub("", title).strip()
        title = re.sub(r"\s{2,}", " ", title)
    return title


def clean_titles(titles):
    """整理片名並去重（保留原始順序）。

    先整理再去重，順序不能反：同一部片的六個場次要先被整理成
    同一個字串，去重才有辦法把它們併成一筆。
    """
    cleaned = [clean_title(t) for t in titles]
    return list(dict.fromkeys([t for t in cleaned if t]))


def find_programs(data):
    """在回應裡找出電影清單。

    為什麼不直接遞迴撈 "name"？因為 name 是個到處都有的通用欄位 ——
    影城名稱、常見問題、場館、類型都叫 name，整份回應裡有 224 個，
    真正是片名的只有一小部分。

    所以先找出「看起來像電影清單」的那個陣列，再從裡面取片名。
    判斷依據是結構而不是路徑：一個 list、元素是 dict、而且帶有
    nameAlternative 欄位 —— 這是電影項目才有的特徵。
    這樣對方就算把 programs 搬到別的層級，程式還是找得到。
    """
    for candidate in collect_keys(data, "programs"):
        if (
            isinstance(candidate, list)
            and candidate
            and isinstance(candidate[0], dict)
            and "nameAlternative" in candidate[0]
        ):
            return candidate
    return []


def showtimes():
    """秀泰影城的片名清單。回傳 (titles, error)。

    用 name（中文片名）而不是 nameAlternative（英文片名）——
    下一章會實測，查電影資料庫時中文名的命中率高很多。
    """
    data, error = fetch_json(SHOWTIMES_URL, headers=BROWSER_HEADERS)
    if error:
        return [], error
    programs = find_programs(data)
    return clean_titles([p.get("name") for p in programs]), None


def miramar():
    """美麗華影城的片名清單。回傳 (titles, error)。

    這支要用 POST（雖然不必帶 body），而且少了 Referer 會被擋。
    """
    headers = dict(BROWSER_HEADERS, Referer="https://www.miramarcinemas.tw/")
    data, error = fetch_json(MIRAMAR_URL, method="POST", headers=headers)
    if error:
        return [], error
    return clean_titles(collect_keys(data, "TitleAlt")), None


# 之後要加第三家影城，只要寫一個同樣形狀的函式再登記到這裡
SOURCES = {
    "showtimes": ("秀泰影城", showtimes),
    "miramar": ("美麗華影城", miramar),
}


def titles_by_source():
    """每家影城各自的片名清單。回傳 ({來源代號: titles}, errors)。

    保留「哪部片在哪家上映」這個資訊，第 3 章合併時要用。
    """
    result = {}
    errors = {}
    for key, (label, fetch) in SOURCES.items():
        titles, error = fetch()
        result[key] = titles
        if error:
            errors[label] = error
    return result, errors


def all_titles():
    """抓所有影城並合併去重。回傳 (titles, errors)。

    某一家掛掉不影響另一家 —— 錯誤收集在 errors 裡回報，
    能拿到的資料照樣回傳。
    """
    by_source, errors = titles_by_source()
    merged = []
    for titles in by_source.values():
        merged.extend(titles)
    return clean_titles(merged), errors
