"""Define the notification channel interface and send messages through it."""

from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, message):
        ...


class EmailChannel(NotificationChannel):
    def send(self, message):
        return {"sent": True, "channel": "email", "message": message}
