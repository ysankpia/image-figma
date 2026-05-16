from __future__ import annotations

from .config import Settings, get_settings
from .database import Database
from .storage import Storage


class AppState:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage = Storage(self.settings.storage_root, self.settings.public_base_url)
        self.database = Database(self.settings.database_path)


state = AppState()
