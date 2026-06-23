import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from envoy.notification.handler import notifications_enabled
from envoy.server.model.subscription import NotificationCheck, SubscriptionResource

logger = logging.getLogger(__name__)


class NotificationManager:
    @staticmethod
    async def notify_changed_deleted_entities(
        session: AsyncSession, resource: SubscriptionResource, timestamp: datetime
    ) -> bool:
        """If notifications are enabled - enqueues (within the supplied session) a check that will (on the notification
        worker) look for changes (insert/update) in the specified entities and deletes in the archive tables
        associated with resource. Returns True in this case.

        If notifications are NOT enabled - this will be a no-op and return False.

        The check is added to session but NOT committed - it will be persisted atomically with the originating data
        change when the caller commits the session (transactional outbox). The notification work itself runs later, on
        the notification worker.

        resource: The resource that has changed/been deleted
        timestamp: The exact changed_at/deleted_time that will be used to find the affected records"""
        if not notifications_enabled():
            return False

        session.add(NotificationCheck(resource_type=resource, changed_time=timestamp))
        return True
