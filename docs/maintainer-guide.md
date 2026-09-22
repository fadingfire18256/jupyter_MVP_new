# 講師維護與發布指南

## 維護來源與目錄分工

`notebooks/00–05` 是教學程式來源。修改來源儲存格、相關講解與固定案例，保留既有 cell id，再重建 `movieapp/`、`server/`、`requirements.txt`、`.env.example`。
這些產出檔也提交 Git，讓 clone 後可以直接執行完成品。README、docs、tests、tools、其餘 requirements 與 Git 設定可直接修改。

本版增加 `movieapp/service.py`，由第 05 章產生，用於管理本機服務。完整來源格收合，啟動與關閉格保留短程式供學生操作。

三份套件清單依序包含：runtime → classroom → dev。學生只安裝 `requirements-classroom.txt`，講師安裝 `requirements-dev.txt`。直接相依使用已驗證版本；更新套件時一併更新第 00 章安裝格並重新驗證。

## 本機驗證

在教材根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe build_modules.py
.\.venv\Scripts\python.exe build_modules.py --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/verify_notebooks.py --output .lesson-runs
```

`--check` 只比較，不寫入。單元測試使用 demo 或 mock，不使用真實金鑰。
有 Node.js 時額外執行前端排序與過期回應測試；CI 會安裝 Node.js，學生啟動系統不需要 Node.js。

整套驗證工具將教材複製到暫存目錄，排除 `.env`、虛擬環境、服務紀錄與既有執行輸出，移除產出檔後依序執行六本 Notebook。
已先安裝相依套件，因此略過標記 `install` 的儲存格；執行期間只允許本機通訊。結果放在 `.lesson-runs/`，不修改來源講義。

## GitHub 自動檢查

`.github/workflows/check.yml` 在 push、pull request 或手動觸發時執行。使用 Windows 與 Python 3.12，檢查產出同步、回歸測試、Notebook 格式及六章完整執行。
不需要設定 API secrets，也不部署服務。首次推送後仍須確認 GitHub 上的工作流程結果。

## 發布第一版

1. 執行上述驗證，再檢查 `git status` 與差異，確認所有必要的新檔案都有納入，包括前端拆分檔、demo、service、tests、tools 與套件清單。
2. `.env`、`.venv/`、執行後講義、PID／JSON／log 等本機產物不提交。原始 Notebook 不保存執行輸出與 execution count。
3. 將已驗證變更提交並合併到 GitHub 的預設分支。只推送工作分支，學生一般的 clone 不會自動選到它。
4. 從 GitHub clone 到新目錄，以全新 `.venv` 完整照 README 安裝並操作；確認不依賴舊環境或本機未提交檔案。
5. 驗證通過後建立課程版本標籤，例如 `class-v1.0`，課前告知學生使用哪個版本。標籤名稱在本文件中只是範例，不代表已發布。

上課期間盡量維持課程版本穩定。修正後提供新版本與更新說明，提醒學生保留自己的練習。

## 舊版文件

根目錄的「安裝與啟動指南.md」只保留導覽連結；舊 Markdown 與 Word 文件放在 `docs/archive/`，僅供講師查閱歷史內容，不作為學生操作依據。

## 實作依據

- [GitHub：Python 建置與測試](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [psutil：行程管理與 PID 重用檢查](https://psutil.readthedocs.io/stable/)

demo 不代表 live 服務已驗證；外部 API、模型可用性與帳戶限制須在授課前另外確認。
