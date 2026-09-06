# 電影整合系統 ・ Jupyter 教材版

把兩家影城「現在上映什麼」抓下來，補上電影資料庫的評分、海報、類型，
整合成一份清單，再讓 AI 根據這份清單回答問題，最後接成一個可以操作的網頁。

原本是 Django + React 的專案，改寫成在 Jupyter 裡一步步做出來的教材。

## 這包教材的特別之處

**除了 notebook，沒有任何程式碼是先寫好給你的。**

`movieapp/`、`server/`、甚至最後那個網頁前端，
全部都是六本 notebook 用 `%%writefile` 一格一格寫出來的。
整包刪到只剩 `notebooks/`，照順序重跑就會長回來。

## 快速開始

```bash
python -m pip install jupyter requests pandas "Django>=4.2,<5.1" django-cors-headers
jupyter notebook          # 或 jupyter lab
```

打開 `notebooks/00_環境設定.ipynb`，照編號依序做完六本。全程大約三到四小時。

> **這套教材全程需要連線。** 影城、TMDB、Gemini 三個外部服務都是即時呼叫，
> 沒有離線備援。上課前請先跑 00 的連線測試那一格確認四支 API 都通。

## 課程內容

| Notebook | 主題 | 產出 |
|---|---|---|
| `00_環境設定` | 地基：金鑰、統一的網路出入口、`(data, error)` | `movieapp/config.py`、`movieapp/http.py` |
| `01_影城API` | 沒有文件的 API、遞迴搜尋的代價、髒資料清理 | `movieapp/sources.py` |
| `02_TMDB` | 正規 API、金鑰安全、比對不能只信第一筆、快取與平行化 | `movieapp/tmdb.py` |
| `03_資料整合` | 用穩定 id 跨來源去重、pandas 篩選、把流程收成函式 | `movieapp/merge.py` |
| `04_Gemini對話` | 把資料塞進 prompt（RAG 雛形）、多輪對話、配額 | `movieapp/gemini.py` |
| `05_接成服務` | 薄殼、免 build 的前端、同網域部署、行程管理 | `server/` 全部 |

**請照順序做。** 每一本都會產生真正的檔案，後面的章節都靠它們。

## 目錄結構

拿到手時只有 `notebooks/` 和文件；其餘都是你做完課程後長出來的。

```
jupyter_MVP/
├── notebooks/              課程本體，六本依序做
├── .env                    課程共用金鑰（沒有也能上課，程式會當場問）
├── build_modules.py        講師捷徑：一次生出所有檔案
│
│   ↓ 以下全部由 notebook 產生 ↓
│
├── movieapp/               核心邏輯（唯一真相）
│   ├── config.py           金鑰、環境檢查、表格排版        ← 00
│   ├── http.py             所有對外請求的唯一出入口        ← 00
│   ├── sources.py          兩家影城的片名                 ← 01
│   ├── tmdb.py             評分、海報、類型               ← 02
│   ├── merge.py            合併去重、篩選、catalog()      ← 03
│   └── gemini.py           AI 對話                       ← 04
├── server/                 Django 薄殼                    ← 05
│   ├── cinema/views.py     每支 API 三到五行
│   └── static/index.html   整個前端，單一檔案
├── requirements.txt                                       ← 00
└── .env.example                                           ← 00
```

### 為什麼邏輯要放在 movieapp/ 而不是 cell 裡

notebook cell 裡的程式碼**沒辦法被其他 notebook 或網頁服務使用**。
把邏輯集中在 `movieapp/`，notebook 和服務就都只是它的使用者，
改一個地方兩邊同時生效，不會出現三份各自走鐘的複製品。

最直接的證據是 `merge.catalog()`：第 3 章寫它，
第 5 章的 `/api/movies/` 就是一行呼叫它。
`server/cinema/views.py` 每支 API 只有三到五行，也是同一件事的證據。

> **要改請改 notebook 的那一格再重跑**，不要直接編輯產生出來的檔案 ——
> 下次重跑那一格會蓋掉手改的內容。

## 前端沒有 build 步驟

整個前端是**一個 `index.html`**，樣式和程式都內嵌在裡面：
沒有框架、沒有 Node.js、沒有打包工具、沒有 `dist`。

所以它才能跟其他檔案一樣，由 notebook 的 `%%writefile` 寫出來 ——
學員看得到前端每一行在做什麼，包括它怎麼呼叫 `/api/`。

### 為什麼前端不打 `/api/movies/`

`/api/movies/` 會在伺服器端把「抓片單 → 查 TMDB → 去重」整條做完才回應。
用它當前端的唯一資料來源最省事，但**整個畫面要空白等到最後一部片查完**。

所以前端改成兩步：先要片單（快，一次就好），再對每個片名查 TMDB
（慢，六十幾次，用一個大小 8 的池子跑）。片單一到就先畫出來，
海報和評分再一批一批補上去。總時間差不多，但第一秒就看得到東西。

`/api/movies/` 仍然留著，第 3 章的 `merge.catalog()` 和第 5 章都用它，
只是網頁前端沒有走這條路。

## 金鑰

`.env` 裡已填入課程共用的 TMDB 和 Gemini 金鑰，兩把都是免費額度。

**沒有 `.env` 也能上課** —— `config.get_key()` 會在需要的那一刻跳出輸入提示，
輸入內容不會留在 notebook 的輸出裡。申請網址寫在 `.env.example`。

> **Gemini 的免費額度是按金鑰計算的。** 全班共用一把時，
> 大家同時發問會有人收到 429。程式會把這個錯誤翻譯成看得懂的中文說明，
> 學員可以等幾分鐘或換自己的金鑰。

## 常見狀況

| 症狀 | 處理 |
|---|---|
| `ModuleNotFoundError: movieapp` | 00 還沒跑完。`movieapp/` 是 00 產生的 |
| 「缺少前置模組」 | 跳著執行了，回去把它指定的那一本做完 |
| `%%writefile` 說找不到目錄 | 該本 notebook 的建立資料夾那一格沒跑到 |
| 影城 / TMDB 連不上 | 檢查網路。這套教材沒有離線模式 |
| Gemini 回 429 | 配額用完，等幾分鐘或換自己的金鑰 |
| 05 的 port 被佔用 | 重跑啟動那一格，它會先關掉舊的 |
| 環境怪怪的 | 跑 `config.doctor()`，它會列出每一項的狀態 |

## 講師備註

- `build_modules.py` 直接從 notebook 生出**全部 19 個檔案**（不需要 Jupyter），
  用來快速確認教材改動後還跑不跑得動，或第一堂課先展示完成品。
- 打包給學員前記得清掉 notebook 的執行結果：
  `jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace notebooks/*.ipynb`
- 不要打包 `venv/`、`__pycache__/`，也不用打包 `movieapp/`、`server/` ——
  它們是課程的產出，不是教材的一部分。
- 模型名稱會下架。寫這份教材時 `gemini-2.5-flash` 和 `gemini-2.0-flash`
  都已對新使用者關閉，目前用 `gemini-3.6-flash`。
  `movieapp/gemini.py` 的 `MODELS` 是一個清單，主模型不可用時會自動往後試 ——
  哪天又下架了，改 04 那一格就好。
