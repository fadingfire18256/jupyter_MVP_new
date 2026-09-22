# 本專案的修改規則

這是一套逐段教學的 Jupyter 講義。notebooks/00–05 的儲存格是教學程式的維護來源。
movieapp/、server/、requirements.txt、.env.example 都由 %%writefile 產生。

- 修改功能時，先修改對應 Notebook 的來源儲存格及相關講解／小練習。
- 執行 python build_modules.py，再執行 python build_modules.py --check。
- 執行 python -m unittest discover -s tests 驗證；不使用真實金鑰或付費 API。
- 需要執行整套講義時，依 README 的工具執行順序，先用 demo 模式。
- 不只修改產生後的 .py 或前端檔案；下次重建會覆蓋它。
- 保留既有儲存格 id；不要把 API 金鑰或本機敏感資料存進輸出。
- demo 的電影是虛構範例，聊天為固定程式回應，畫面與講義必須明確標示。
- README、build_modules.py、tests/、tools/ 可直接維護，不由 Notebook 產生。
