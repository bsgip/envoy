from datetime import datetime, timedelta, timezone

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session

from envoy.notification.crud.archive import fetch_relationship_with_archive
from envoy.server.model.archive.site import ArchiveSite
from envoy.server.model.site import Site


@pytest.mark.parametrize(
    "requested_pk_ids, expected_pk_ids", [(set(), []), ({1, 6, 9, 11, 12, 13, 14, 15}, [1, 6, 11, 12])]
)
@pytest.mark.anyio
async def test_fetch_relationship_with_archive_site(
    pg_base_config, requested_pk_ids: set[int], expected_pk_ids: list[int]
):
    """Tests the filtering on select_subscriptions_for_resource"""

    # Load our archive with values - mark the "correct" deleted record with a custom nmi
    async with generate_async_session(pg_base_config) as session:
        # Site 11 was deleted at time
        session.add(generate_class_instance(ArchiveSite, seed=101, archive_id=None, deleted_time=None, site_id=11))
        session.add(generate_class_instance(ArchiveSite, seed=202, archive_id=None, deleted_time=None, site_id=11))
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=303,
                archive_id=None,
                deleted_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
                site_id=11,
                nmi="archive_11",
            )
        )

        # Site 12 has multiple deletes - we should get the highest delete time
        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=404,
                archive_id=None,
                deleted_time=datetime(2024, 11, 12, tzinfo=timezone.utc),
                site_id=12,
            )
        )

        session.add(
            generate_class_instance(
                ArchiveSite,
                seed=505,
                archive_id=None,
                deleted_time=datetime(2024, 12, 1, tzinfo=timezone.utc),
                site_id=12,
                nmi="archive_12",
            )
        )
        session.add(generate_class_instance(ArchiveSite, seed=606, archive_id=None, deleted_time=None, site_id=12))

        # Site 13 has no deletes
        session.add(generate_class_instance(ArchiveSite, seed=707, archive_id=None, deleted_time=None, site_id=13))

        # Site 14 has no deletes
        session.add(generate_class_instance(ArchiveSite, seed=808, archive_id=None, deleted_time=None, site_id=14))
        session.add(generate_class_instance(ArchiveSite, seed=909, archive_id=None, deleted_time=None, site_id=14))

        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        entities = await fetch_relationship_with_archive(session, Site, ArchiveSite, requested_pk_ids)

        # Ensure we get the expected entities
        assert len(entities) == len(expected_pk_ids), [e.site_id for e in entities]
        assert sorted([e.site_id for e in entities]) == sorted(expected_pk_ids)

        # Ensure we get the expected values too
        for e in entities:
            if isinstance(e, Site):
                assert e.nmi == str(e.site_id) * 10, "This is just the convention for pg_base_config"
            elif isinstance(e, ArchiveSite):
                assert e.nmi == f"archive_{e.site_id}", "This is just a convention for this test thats setup above"
            else:
                raise Exception(f"Unexpected type returned {e} {type(e)}")
