import logging
from datetime import datetime

from envoy.notification.handler import get_enabled_broker
from envoy.notification.task.check import check_db_change_or_delete
from envoy.server.model.subscription import SubscriptionResource

logger = logging.getLogger(__name__)


class NotificationManager:
    @staticmethod
    async def notify_changed_deleted_entities(resource: SubscriptionResource, timestamp: datetime) -> bool:
        """If notifications are enabled - enqueues a task that will look for changes (insert/update) in the specified
        entities and deletes in the archive tables associated with resource. Returns True in this case.

        If notifications are NOT enabled - this will essentially be a no-op and return False.

        The work will NOT occur on this process - it's purely enqueuing it to run elsewhere"""
        enabled_broker = get_enabled_broker()
        if enabled_broker is None:
            return False

        try:

            await check_db_change_or_delete.kicker().with_broker(enabled_broker).kiq(
                resource=resource, timestamp_epoch=timestamp.timestamp()
            )
            return True
        except Exception as ex:
            logger.error("Exception kicking check_db_change_or_delete for %s at %s", resource, timestamp, exc_info=ex)
            return False
