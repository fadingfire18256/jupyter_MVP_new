"""電影整合系統的核心邏輯層。

這一層是共用的 Python 核心：由 Notebook 產生，供 Notebook 與 Django 匯入。
前端保留即時篩選與顯示，聊天提示統一由這一層建立。

裡面每一個 .py 都是 notebook 用 %%writefile 產生的：
  * config.py / http.py                      —— 00_環境設定
  * sources.py / tmdb.py / merge.py / gemini.py —— 01 ~ 04

所以這個資料夾可以整個刪掉，照順序重跑 notebook 就會長回來。
"""

__all__ = ["config", "http"]
