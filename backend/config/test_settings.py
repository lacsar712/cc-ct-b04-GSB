"""本地/CI 验收用：复用正式配置，仅把数据库换成 SQLite 内存库。"""

from config.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
