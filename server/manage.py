#!/usr/bin/env python
"""Django 管理指令進入點。

一般不用手動執行，05_接成服務.ipynb 會用 subprocess 幫你啟動：
    python manage.py runserver 8008 --noreload

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""
import os
import sys
from pathlib import Path

# 讓 server/ 底下的程式找得到上一層的 movieapp 套件
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
