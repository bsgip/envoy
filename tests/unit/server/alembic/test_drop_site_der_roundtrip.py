from envoy.server.alembic import downgrade, upgrade

PREV_REVISION = "f91bfeaeca8f"


def test_drop_site_der_migration_roundtrip(pg_base_config):
    """Downgrades past the drop_site_der migration and back up, ensuring both directions run cleanly and the
    flattened DER sub resources retain their site linkage."""

    # pg_base_config is already at head with site 1's DER sub resources flattened onto site_id=1
    downgrade(PREV_REVISION)  # recreates site_der + archive_site_der, repoints children at site_der_id
    upgrade("head")  # drops them again, repoints children at site_id

    with pg_base_config.cursor() as cur:
        for table in ("site_der_rating", "site_der_setting", "site_der_availability", "site_der_status"):
            cur.execute(f"SELECT site_id FROM {table}")  # noqa: S608
            assert cur.fetchone()[0] == 1

        # site_der / archive_site_der should no longer exist
        cur.execute("SELECT to_regclass('public.site_der'), to_regclass('public.archive_site_der')")
        assert cur.fetchone() == (None, None)
