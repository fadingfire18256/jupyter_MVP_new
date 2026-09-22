"""網址設定。

同一個服務同時提供兩件東西：
    /api/...   後端 API
    /          前端網頁；/assets/ 提供分開的樣式與腳本

兩者在同一個網域底下，所以瀏覽器不會有跨來源問題，
前端也不需要 build 步驟 —— 沒有 Node.js、沒有打包工具、沒有 dist 資料夾。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

from django.urls import include, path

from cinema.views import asset, index

urlpatterns = [
    path("api/", include("cinema.urls")),
    path("assets/<str:filename>", asset, name="asset"),
    path("", index, name="index"),
]
