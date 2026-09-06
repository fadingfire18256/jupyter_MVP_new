"""Django 設定。

這個服務只做兩件事：把 movieapp 的功能開成 API、以及把前端網頁送出去。
沒有資料庫、沒有登入、沒有後台，所以 INSTALLED_APPS 幾乎是空的。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# 教學用途，正式部署要改成從環境變數讀取
SECRET_KEY = "django-insecure-jupyter-teaching-package"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "cinema",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# 沒有用到資料庫
DATABASES = {}

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

# 前端和 API 都由這個服務提供（同一個網域），
# 所以不需要 CORS 設定，前端也不需要任何 build 步驟。
