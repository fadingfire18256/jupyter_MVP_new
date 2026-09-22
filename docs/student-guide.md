# 學生操作指南

安裝入口統一使用 [README](../README.md)。本指南以 Windows、Python 3.12 為準。

## 確認你正在使用哪個 Python

從 README 指令啟動 JupyterLab，在 Notebook 執行：

```python
import sys
print(sys.executable)
```

路徑應包含這份教材的 `.venv\Scripts\python.exe`。若選到其他環境，關閉 JupyterLab，從教材根目錄重新執行：

```powershell
.\.venv\Scripts\python.exe -m jupyter lab notebooks
```

每本 Notebook 請使用自己的 kernel。換章節時從開頭執行；重新啟動 kernel 後，變數與匯入模組都需要重新建立。

## 逐格操作

- `Shift+Enter`：執行目前儲存格並往下移。
- 收合的程式格：選取橫條後仍要執行。`Writing`／`Overwriting` 是正常訊息。
- `assert`：固定案例的驗證；沒有錯誤輸出代表通過。
- 「小練習」：先改一個條件，觀察結果，再回到原始案例確認規則。
- 若只想驗證完整流程，可使用 Run → Run All Cells；上課仍建議逐格閱讀。

六本講義預設 `MODE = "demo"`。demo 的電影是虛構資料，聊天是固定程式回應，沒有真正的模型推理或多輪記憶。

## 直接看完成品

先完成 README 的環境安裝，在教材根目錄執行：

```powershell
$env:MOVIEAPP_MODE = "demo"
.\.venv\Scripts\python.exe server/manage.py runserver 127.0.0.1:8008 --noreload
```

開啟 http://127.0.0.1:8008。關閉時回到這個終端機按 Ctrl+C。
這種啟動方式與第 05 章二選一；同一個埠號不能同時啟動兩份服務。

## 第 05 章的服務啟停

「啟動服務」格使用獨立行程，並把 PID、建立時間與埠號記錄在 `.classroom-server.json`。
重跑會先確認原行程的身分，再重啟。kernel 重開後，重新執行本章，仍可找到原服務。
最後的「關閉服務」格也能獨立執行，不依賴 kernel 內保存的 `server` 變數。

若提示「無法確認或停止原服務」：

1. 若服務從終端機啟動，回到原終端機按 Ctrl+C。
2. 若是舊版講義留下的背景服務，在工作管理員確認啟動指令包含本教材的 `server/manage.py` 或在本教材 `server` 目錄執行的 `manage.py runserver`，再結束該行程。不要依照名稱一次結束所有 Python。
3. 確認原服務已停止後，刪除教材根目錄的 `.classroom-server.json` 與舊版 `.classroom-server.pid`（若存在），再重跑啟動格。

若埠號 8008 已被其他程式使用，可在第 05 章啟動格之前設定：

```python
import os
os.environ["MOVIEAPP_PORT"] = "8010"
```

之後以啟動格印出的網址為準。啟動失敗的詳細內容在 `.classroom-server.log`。

## 切換 live 模式

先完成 demo。真實模式才會連接影城、TMDB 與 Gemini，可能受服務狀態、帳戶配額及費用影響。

1. 使用教材建立的 `.env` 填入自己的 `TMDB_READ_ACCESS_TOKEN` 與 `GEMINI_API_KEY`；也可在本機網頁的「API 金鑰」視窗設定。`.env.example` 請保持空白範本。
2. 在需要連線的 Notebook 開頭設定 `MODE = "live"`，重跑開場與相關載入格。各本 Notebook 的模式要分別設定。
3. 第 05 章改模式後重跑啟動服務格；若從終端機啟動，先 Ctrl+C，再設定 `$env:MOVIEAPP_MODE = "live"` 後重啟。

不要把金鑰寫進 Notebook 或保存到輸出。`.env` 已被 `.gitignore` 排除。
Gemini 配額以 [Google 官方說明](https://ai.google.dev/gemini-api/docs/rate-limits) 與帳戶狀態為準。

## 常見狀況

| 狀況 | 處理方式 |
|---|---|
| `git` 或 `py` 找不到 | 安裝 Git／Python 3.12 後重新開終端機；README 提供 `python` 替代指令 |
| `ModuleNotFoundError` | 先確認 kernel 路徑，再由根目錄重跑 README 的套件安裝指令 |
| 看不到程式，只看到橫條 | 那是收合的完整程式格，可以展開；仍需要執行 |
| 修改完整函式卻沒生效 | 重跑對應 `%%writefile` 格；重啟 kernel 並從頭執行；網頁後端則重啟服務 |
| demo 電影沒有海報 | 正常，三部虛構電影沒有外部海報，畫面使用預設版面 |
| live 回 401 或 429 | 401 檢查個人金鑰，429 查看服務配額；可先切回 demo 繼續課程 |

## 保留作業後再更新教材

Notebook 執行與練習都會改動檔案。更新前先關閉服務、儲存講義，使用 `git status` 查看修改。
Git 尚不熟悉時，先把自己的 Notebook 複製到專案外的作業資料夾，再將新版 clone 到另一個新資料夾；不要覆蓋原本的作業。
若講師指定版本標籤，以該標籤下載，例如：

```powershell
# class-v1.0 是範例，請替換成講師已發布的標籤。
git clone --branch class-v1.0 https://github.com/fadingfire18256/jupyter_MVP_new.git aisaclass-v1
```

不要為了讓 `git pull` 成功而丟棄尚未備份的練習。作業繳交前，先檢查儲存格與輸出沒有個人金鑰。
