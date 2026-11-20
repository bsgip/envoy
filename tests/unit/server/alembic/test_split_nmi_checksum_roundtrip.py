from envoy.server.alembic import downgrade, upgrade

PREV_REVISION = "beb692fa34d5"
COLS = (
    "site_id, nmi, aggregator_id, timezone_id, created_time, changed_time, lfdi, sfdi, device_category, "
    "registration_pin, post_rate_seconds"
)


def test_split_nmi_checksum_migration_roundtrip(pg_base_config):
    """Downgrades past the split_nmi_checksum migration, populates 11 char / short / NULL NMIs and then ensures that
    upgrading splits them appropriately (and that downgrading recombines them)"""

    downgrade(PREV_REVISION)

    with pg_base_config.cursor() as cur:
        cur.execute("UPDATE site SET nmi = '12345678901' WHERE site_id = 1")  # 11 chars - gets split
        cur.execute("UPDATE site SET nmi = '1234567890' WHERE site_id = 2")  # 10 chars - no checksum
        cur.execute("UPDATE site SET nmi = 'abc' WHERE site_id = 3")  # short - no checksum
        cur.execute("UPDATE site SET nmi = NULL WHERE site_id = 4")
        cur.execute(f"INSERT INTO archive_site ({COLS}) SELECT {COLS} FROM site")  # noqa: S608
    pg_base_config.commit()

    upgrade("head")

    expected = {1: ("1234567890", "1"), 2: ("1234567890", None), 3: ("abc", None), 4: (None, None)}
    with pg_base_config.cursor() as cur:
        for table in ("site", "archive_site"):
            cur.execute(f"SELECT site_id, nmi, nmi_checksum FROM {table} WHERE site_id <= 4")  # noqa: S608
            assert {r[0]: (r[1], r[2]) for r in cur.fetchall()} == expected, table
    pg_base_config.commit()

    downgrade(PREV_REVISION)

    expected_combined = {1: "12345678901", 2: "1234567890", 3: "abc", 4: None}
    with pg_base_config.cursor() as cur:
        for table in ("site", "archive_site"):
            cur.execute(f"SELECT site_id, nmi FROM {table} WHERE site_id <= 4")  # noqa: S608
            assert {r[0]: r[1] for r in cur.fetchall()} == expected_combined, table
    pg_base_config.commit()

    upgrade("head")
