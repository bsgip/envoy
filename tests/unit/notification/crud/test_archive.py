from datetime import datetime, timedelta, timezone

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session

from envoy.notification.crud.archive import fetch_relationship_with_archive
from envoy.server.model.archive.site import ArchiveSite, ArchiveSiteDER
from envoy.server.model.site import Site, SiteDER


@pytest.mark.parametrize(
    "requested_pk_ids, expected_source_pk_ids, expected_archive_pk_ids",
    [
        (set(), [], []),
        ({1, 6, 9, 11, 12, 13, 14, 15}, [1, 6], [11, 12]),
        ({1, 3}, [1, 3], []),
        ({9}, [], []),
        ({11, 14}, [], [11]),
        ({11}, [], [11]),
    ],
)
@pytest.mark.anyio
async def test_fetch_relationship_with_archive_site(
    pg_base_config, requested_pk_ids: set[int], expected_source_pk_ids: list[int], expected_archive_pk_ids: list[int]
):
    """Tests fetch_relationship_with_archive can differentiate archive records from normal records and can
    correctly source entities from the archive table if the main table is empty"""

    # Load our archive with values - mark the "correct" deleted record with a custom nmi
    async with generate_async_session(pg_base_config) as session:
        # Site 1 has some audit records (with an old deletion)
        session.add(generate_class_instance(ArchiveSite, seed=1, archive_id=None, deleted_time=None, site_id=1))
        session.add(generate_class_instance(ArchiveSite, seed=2, archive_id=None, site_id=1))

        # Site 2 has some audit records
        session.add(generate_class_instance(ArchiveSite, seed=3, archive_id=None, deleted_time=None, site_id=2))

        # Site 11 DNE in the main table (it was deleted)
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
        source_entities, archive_entities = await fetch_relationship_with_archive(
            session, Site, ArchiveSite, requested_pk_ids
        )

        # Ensure we get the expected entities and IDs
        assert_list_type(Site, source_entities, count=len(expected_source_pk_ids))
        assert_list_type(ArchiveSite, archive_entities, count=len(expected_archive_pk_ids))
        assert sorted([e.site_id for e in source_entities]) == sorted(expected_source_pk_ids)
        assert sorted([e.site_id for e in archive_entities]) == sorted(expected_archive_pk_ids)

        # Ensure we get the expected values too
        for e in source_entities:
            assert e.nmi == str(e.site_id) * 10, "This is just the convention for pg_base_config"
        for e in archive_entities:
            assert e.nmi == f"archive_{e.site_id}", "This is just a convention for this test thats setup above"


@pytest.mark.parametrize(
    "requested_pk_ids, expected_source_pk_ids, expected_archive_pk_ids",
    [
        (set(), [], []),
        ({1, 2, 9, 11, 12, 13, 14, 15}, [1, 2], [11, 12]),
        ({1, 3}, [1], []),
        ({9}, [], []),
        ({11, 14}, [], [11]),
        ({11}, [], [11]),
    ],
)
@pytest.mark.anyio
async def test_fetch_relationship_with_archive_site_der(
    pg_base_config, requested_pk_ids: set[int], expected_source_pk_ids: list[int], expected_archive_pk_ids: list[int]
):
    """Tests fetch_relationship_with_archive can differentiate archive records from normal records and can
    correctly source entities from the archive table if the main table is empty"""

    # Load our archive with values - mark the "correct" deleted record with a changed_time
    expected_changed_time = datetime(2027, 11, 1, 4, 5, 6, tzinfo=timezone.utc)
    async with generate_async_session(pg_base_config) as session:
        # Site DER 1 has some audit records (with an old deletion)
        session.add(generate_class_instance(ArchiveSiteDER, seed=1, archive_id=None, deleted_time=None, site_der_id=1))
        session.add(generate_class_instance(ArchiveSiteDER, seed=2, archive_id=None, site_der_id=1))

        # Site DER 2 has some audit records
        session.add(generate_class_instance(ArchiveSiteDER, seed=3, archive_id=None, deleted_time=None, site_der_id=2))

        # Site DER 11 DNE in the main table (it was deleted)
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=101, archive_id=None, deleted_time=None, site_der_id=11)
        )
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=202, archive_id=None, deleted_time=None, site_der_id=11)
        )
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=303,
                archive_id=None,
                deleted_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
                site_der_id=11,
                changed_time=expected_changed_time,
            )
        )

        # Site DER 12 has multiple deletes - we should get the highest delete time
        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=404,
                archive_id=None,
                deleted_time=datetime(2024, 11, 12, tzinfo=timezone.utc),
                site_der_id=12,
            )
        )

        session.add(
            generate_class_instance(
                ArchiveSiteDER,
                seed=505,
                archive_id=None,
                deleted_time=datetime(2024, 12, 1, tzinfo=timezone.utc),
                site_der_id=12,
                changed_time=expected_changed_time,
            )
        )
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=606, archive_id=None, deleted_time=None, site_der_id=12)
        )

        # Site DER 13 has no deletes
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=707, archive_id=None, deleted_time=None, site_der_id=13)
        )

        # Site DER 14 has no deletes
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=808, archive_id=None, deleted_time=None, site_der_id=14)
        )
        session.add(
            generate_class_instance(ArchiveSiteDER, seed=909, archive_id=None, deleted_time=None, site_der_id=14)
        )

        await session.commit()

    async with generate_async_session(pg_base_config) as session:
        source_entities, archive_entities = await fetch_relationship_with_archive(
            session, SiteDER, ArchiveSiteDER, requested_pk_ids
        )

        # Ensure we get the expected entities and IDs
        assert_list_type(SiteDER, source_entities, count=len(expected_source_pk_ids))
        assert_list_type(ArchiveSiteDER, archive_entities, count=len(expected_archive_pk_ids))
        assert sorted([e.site_der_id for e in source_entities]) == sorted(expected_source_pk_ids)
        assert sorted([e.site_der_id for e in archive_entities]) == sorted(expected_archive_pk_ids)

        # Ensure we get the expected values too
        for e in source_entities:
            assert e.changed_time == datetime(
                2024, 3, 14, 3 + e.site_der_id, 55, 44, 500000, tzinfo=timezone.utc
            ), "This is just the convention for pg_base_config"
        for e in archive_entities:
            assert e.changed_time == expected_changed_time, "This is just a convention for this test (setup above)"
