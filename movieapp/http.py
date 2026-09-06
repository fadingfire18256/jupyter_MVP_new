"""所有對外的 HTTP 請求都必須走這裡。

為什麼要統一出入口？因為「錯誤處理」只要寫一次。
外部 API 會逾時、會斷線、會回 429、會回一坨不是 JSON 的東西，
這些狀況在這裡一次翻譯成看得懂的中文訊息，
呼叫端只要處理 (data, error) 這組回傳值就好。

之後想加快取、加重試、加日誌，也都只有這一個地方要改。

本檔案由 notebooks/00_環境設定.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

from __future__ import annotations

# 外部 API 的預設 timeout（秒）
DEFAULT_TIMEOUT = 20

# 影城的 API 沒有公開文件，不帶瀏覽器特徵的請求會被擋，
# 所以統一準備一組看起來像瀏覽器的 header。
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    headers: dict | None = None,
    json_body: dict | None = None,
    timeout: int | None = None,
):
    """抓取外部 API 並解析 JSON。

    回傳 (data, error)：成功時 error 為 None，失敗時 data 為 None。

    為什麼不丟例外？因為外部 API 失敗是「正常會發生的事」，不是程式寫錯。
    把錯誤當成一般的值傳回去，呼叫端就不必到處包 try/except，
    也不會因為一家影城掛掉就讓整個服務噴 500。
    """
    try:
        import requests
    except ImportError:
        return None, "沒有安裝 requests，請執行 %pip install -r ../requirements.txt"

    try:
        resp = requests.request(
            method,
            url,
            params=params,
            headers=headers,
            json=json_body,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.Timeout:
        return None, f"外部 API 逾時（超過 {timeout or DEFAULT_TIMEOUT} 秒）"
    except requests.exceptions.ConnectionError:
        return None, "無法連線到外部 API，請檢查網路"
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code
        if code == 401:
            return None, "外部 API 回應 401：金鑰無效或未帶上金鑰"
        if code == 429:
            return None, "外部 API 回應 429：請求太頻繁，配額或流量限制已達上限"
        return None, f"外部 API 回應錯誤：HTTP {code}"
    except ValueError:
        # requests 的 .json() 解析失敗時丟的是 ValueError（JSONDecodeError 是它的子類）
        return None, "外部 API 的回應不是有效的 JSON"
    except requests.exceptions.RequestException as exc:
        return None, f"請求失敗：{exc}"
