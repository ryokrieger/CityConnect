"""
Design Pattern 3 — Factory Pattern
Applied to: notification creation.

Views never build NotificationRecord objects directly — they declare
intent via NotificationFactory.create(type, context) and call .save() on
the result. Adding a new notification type means adding one enum member
and one builder method here; no call sites change.
"""

from enum import Enum


class NotificationType(Enum):
    FRIEND_REQUEST = "friend_request"
    REQUEST_ACCEPTED = "request_accepted"
    NEW_MESSAGE = "new_message"
    EVENT_CREATED = "event_created"


class Notification:
    def __init__(self, recipient, notif_type: NotificationType, message: str, url: str = ""):
        self.recipient = recipient
        self.notif_type = notif_type
        self.message = message
        self.url = url

    def save(self):
        from apps.core.models import NotificationRecord
        NotificationRecord.objects.create(
            recipient=self.recipient,
            notif_type=self.notif_type.value,
            message=self.message,
            url=self.url,
        )


class NotificationFactory:
    """Creates the correct Notification for a given type and context dict."""

    @staticmethod
    def create(notif_type: NotificationType, context: dict) -> Notification:
        builders = {
            NotificationType.FRIEND_REQUEST: NotificationFactory._friend_request,
            NotificationType.REQUEST_ACCEPTED: NotificationFactory._request_accepted,
            NotificationType.NEW_MESSAGE: NotificationFactory._new_message,
            NotificationType.EVENT_CREATED: NotificationFactory._event_created,
        }
        builder = builders.get(notif_type)
        if not builder:
            raise ValueError(f"No builder registered for: {notif_type}")
        return builder(context)

    @staticmethod
    def _friend_request(ctx) -> Notification:
        return Notification(
            recipient=ctx['recipient'],
            notif_type=NotificationType.FRIEND_REQUEST,
            message=f"{ctx['sender'].username} sent you a friend request.",
            url="/social/requests/",
        )

    @staticmethod
    def _request_accepted(ctx) -> Notification:
        return Notification(
            recipient=ctx['recipient'],
            notif_type=NotificationType.REQUEST_ACCEPTED,
            message=f"{ctx['acceptor'].username} accepted your friend request.",
            url="/social/friends/",
        )

    @staticmethod
    def _new_message(ctx) -> Notification:
        return Notification(
            recipient=ctx['recipient'],
            notif_type=NotificationType.NEW_MESSAGE,
            message=f"New message from {ctx['sender'].username}.",
            url=f"/messaging/{ctx['sender'].id}/",
        )

    @staticmethod
    def _event_created(ctx) -> Notification:
        return Notification(
            recipient=ctx['recipient'],
            notif_type=NotificationType.EVENT_CREATED,
            message=f"New event '{ctx['event'].name}' in {ctx['group'].name}.",
            url=f"/groups/{ctx['group'].id}/",
        )


# Usage:
#   notif = NotificationFactory.create(NotificationType.FRIEND_REQUEST, {
#       'recipient': receiver,
#       'sender': request.user,
#   })
#   notif.save()