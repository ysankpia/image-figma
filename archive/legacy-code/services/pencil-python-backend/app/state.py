from __future__ import annotations

from .config import Settings, get_settings
from .storage import TaskStorage
from .tasks import TaskManager


class AppState:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage = TaskStorage(self.settings.storage_root)
        self.tasks = TaskManager(self.storage, self.settings)


state = AppState()
