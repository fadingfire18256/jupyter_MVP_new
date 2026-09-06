"""Django app 設定。

本檔案由 notebooks/05_接成服務.ipynb 的 %%writefile 產生。
"""

from django.apps import AppConfig


class CinemaConfig(AppConfig):
    name = "cinema"

    def ready(self):
        """服務啟動時關掉「當場詢問金鑰」。

        movieapp 的 get_key() 找不到金鑰時會用 getpass 問人，那是給
        notebook 用的。在網頁服務裡，提示只會印在伺服器主控台，
        瀏覽器那邊看不到，請求就這樣一直卡著等一個沒人會填的輸入框。
        關掉之後改成回傳 401，前端就能跳出金鑰設定視窗。
        """
        from movieapp import config

        config.set_interactive(False)
