from __future__ import annotations


class NotificationError(Exception):
    def __init__(self, message: str = "Notification error") -> None:
        self.message = message
        super().__init__(self.message)


class NotificationNotFoundError(NotificationError):
    def __init__(self) -> None:
        super().__init__("Notification not found")
