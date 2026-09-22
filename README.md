# 電影整合系統：Notebook 課堂版

用六份 Jupyter Notebook，逐段學習影城資料、TMDB 查詢、資料整合、AI 對話，最後做出本機網頁。

**第一次上課請用 demo 模式：不需要 API Key。** 三部電影是虛構範例，聊天是固定程式回應，畫面會標示「示範」。套件安裝需要網路；安裝完成後，demo 的課堂練習不需要外部 API。

## 從 GitHub 下載並開始上課

以下以 **Windows PowerShell、Git、Python 3.12** 為準。先安裝 Git 與 Python 3.12，再在你想放教材的資料夾開啟 PowerShell，逐行執行：

```powershell
git clone https://github.com/fadingfire18256/jupyter_MVP_new.git aisaclass
cd aisaclass
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-classroom.txt
.\.venv\Scripts\python.exe -m jupyter lab notebooks
```

若沒有 `py` 指令，但 `python --version` 顯示 Python 3.12，可用 `python -m venv .venv` 取代第三行。後面的指令都使用專案內的 Python，無須執行 Activate.ps1。

瀏覽器開啟 JupyterLab 後：

1. 雙擊 `00_環境設定.ipynb`，選擇 **Python 3 (ipykernel)**。
2. 從第一格開始，按 **Shift+Enter** 逐格執行；收合成橫條的程式格也要執行。
3. 保持每本開頭的 `MODE = "demo"`，依序完成 **00 → 01 → 02 → 03 → 04 → 05**。
4. 第 05 章啟動服務後開啟 [本機電影系統](http://127.0.0.1:8008)，做完執行「關閉服務」格。

看到 `Writing`／`Overwriting` 是產生程式檔成功；`assert` 沒有報錯就是該格驗證通過。GitHub 上的 Notebook 預覽只能閱讀，執行請使用本機 JupyterLab。

下次上課只要在 `aisaclass` 資料夾執行最後一行啟動 JupyterLab，不必重新安裝。

## 六章學習路線

| 章節 | 學習內容 | 完成時可觀察到的成果 |
|---|---|---|
| 00 環境設定 | 環境、模式、共用工具 | 環境檢查通過、示範資料可用 |
| 01 影城 API | JSON、資料定位、清理去重 | 兩家影城的片名清單 |
| 02 TMDB | 查詢、名稱比對、快取、平行查詢 | 片名配對到電影資料 |
| 03 資料整合 | 共同 id、合併、篩選排序 | 三部虛構電影與各自的影城來源 |
| 04 Gemini 對話 | 片單、提示、回應與錯誤 | 明確標示未呼叫 AI 的示範回答 |
| 05 接成服務 | API、前端、服務啟停 | 可篩選電影與聊天的本機網頁 |

## 專案裡的其他檔案做什麼用？

```text
aisaclass/
├─ notebooks/                  # 上課主線：00–05，程式的維護來源
├─ movieapp/                   # Notebook 產生的共用 Python 模組
├─ server/                     # Notebook 產生的 Django 與網頁程式
├─ docs/                       # 學生操作、講師維護、舊版指南封存
├─ tests/                      # 功能與前端回歸測試
├─ tools/                      # 整套 Notebook 的離線驗證工具
├─ .github/workflows/          # GitHub 自動檢查
├─ requirements.txt            # 應用程式需要的套件
├─ requirements-classroom.txt  # 上課環境：應用程式 + JupyterLab
├─ requirements-dev.txt        # 講師環境：上課環境 + 驗證工具
├─ build_modules.py            # 從 Notebook 同步產生程式檔
├─ .env.example                # 空白金鑰範本
└─ AGENTS.md                   # OpenCode 修改教材時的規則
```

學生先專注 `notebooks/`。完整產出檔也保留在 GitHub，方便對照與直接看完成品。
**程式修改要回到 Notebook 的來源格**，再重建對應檔案；只改 `movieapp/` 或 `server/` 會在重跑講義時被覆蓋。

## 進一步操作

- [學生操作指南](docs/student-guide.md)：確認 kernel、直接看完成品、切換 live、常見錯誤、保留作業後更新。
- [講師維護與發布指南](docs/maintainer-guide.md)：同步產出、測試、乾淨 clone 驗證、發布分支與版本。
- [OpenCode 修改規則](AGENTS.md)：讓 AI 修改時保留 Notebook 作為來源。

課堂 demo 已納入離線驗證；live 需要個人金鑰與外部服務，本版未使用真實金鑰驗證。
