"""WSGI 進入點。正式部署時 gunicorn／uwsgi 會找這個檔案。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
