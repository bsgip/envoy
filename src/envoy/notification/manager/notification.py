import logging
from datetime import datetime

from envoy.notification.handler import get_enabled_broker
from envoy.notification.task.check import check_db_upsert
from envoy.server.model.subscription import SubscriptionResource

logger = logging.getLogger(__name__)


class NotificationManager:
    @staticmethod
    async def notify_upserted_entities(resource: SubscriptionResource, timestamp: datetime) -> bool:
        """If notifications are enabled - enqueues a task that will look for changes in the specified entities

        The work will NOT occur on this process - it's purely enqueuing it to run elsewhere"""
        enabled_broker = get_enabled_broker()
        if enabled_broker is None:
            return False

        try:

            await check_db_upsert.kicker().with_broker(enabled_broker).kiq(
                resource=resource, timestamp_epoch=timestamp.timestamp()
            )
            return True
        except Exception as ex:
            logger.error("Exception kicking check_db_upsert for %s at %s", resource, timestamp, exc_info=ex)
            return False
