from dataclasses import dataclass
from typing import Generic, Sequence

from envoy.notification.crud.batch import TResourceModel
from envoy.server.model.subscription import Subscription


@dataclass
class Notification(Generic[TResourceModel]):
    """A notification represents a set of entities to communicate to remote URI via a subscription"""

    entities: Sequence[TResourceModel]  # The entities to send
    subscription: Subscription  # The subscription being serviced
