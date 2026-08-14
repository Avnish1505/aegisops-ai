"""Define the notification channel interface and send messages through it."""

from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, message: object) -> dict[str, object]:
        ...


class EmailChannel(NotificationChannel):
    def send(self, message: object) -> dict[str, object]:
        return {"sent": True, "channel": "email", "message": message}
