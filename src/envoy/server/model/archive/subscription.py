from datetime import datetime
from typing import Optional

from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier
from sqlalchemy import INTEGER, VARCHAR, DateTime
from sqlalchemy.orm import Mapped, mapped_column

import envoy.server.model as original_models
from envoy.server.model.archive.base import ARCHIVE_TABLE_PREFIX, ArchiveBase


class ArchiveSubscription(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.Subscription.__tablename__  # type: ignore

    subscription_id: Mapped[int] = mapped_column(INTEGER, index=True)
    aggregator_id: Mapped[int] = mapped_column(INTEGER)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    resource_type: Mapped[original_models.SubscriptionResource] = mapped_column(INTEGER)
    resource_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)
    scoped_site_id: Mapped[Optional[int]] = mapped_column(INTEGER, nullable=True)

    notification_uri: Mapped[str] = mapped_column(VARCHAR(length=2048))
    entity_limit: Mapped[int] = mapped_column(INTEGER)


class ArchiveSubscriptionCondition(ArchiveBase):
    __tablename__ = ARCHIVE_TABLE_PREFIX + original_models.SubscriptionCondition.__tablename__  # type: ignore

    subscription_condition_id: Mapped[int] = mapped_column(INTEGER, index=True)
    subscription_id: Mapped[int] = mapped_column(INTEGER)

    attribute: Mapped[ConditionAttributeIdentifier] = mapped_column(INTEGER)
    lower_threshold: Mapped[int] = mapped_column(INTEGER, nullable=False)
    upper_threshold: Mapped[int] = mapped_column(INTEGER, nullable=False)
