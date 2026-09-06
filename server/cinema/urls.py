"""API 的網址對照表。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
"""

from django.urls import path

from . import views

urlpatterns = [
    path("movies/", views.movies, name="movies"),
    path("showtimes/", views.showtimes, name="showtimes"),
    path("miramar/", views.miramar, name="miramar"),
    path("tmdb/search/", views.tmdb_search, name="tmdb-search"),
    path("tmdb/genres/", views.tmdb_genres, name="tmdb-genres"),
    path("chat/", views.chat, name="chat"),
    path("keys/", views.keys, name="keys"),
    path("time/", views.server_time, name="server-time"),
]
