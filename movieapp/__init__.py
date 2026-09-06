"""電影整合系統的核心邏輯層。

這一層是「唯一真相」：notebook 和 Django 服務都只是它的使用者，
自己不藏任何邏輯。

裡面每一個 .py 都是 notebook 用 %%writefile 產生的：
  * config.py / http.py                      —— 00_環境設定
  * sources.py / tmdb.py / merge.py / gemini.py —— 01 ~ 04

所以這個資料夾可以整個刪掉，照順序重跑 notebook 就會長回來。
"""

__all__ = ["config", "http"]
