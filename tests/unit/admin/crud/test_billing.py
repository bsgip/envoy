from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

import pytest

from envoy.admin.crud.billing import (
    BillingData,
    fetch_aggregator,
    fetch_aggregator_billing_data,
    fetch_calculation_log_billing_data,
    fetch_sites_billing_data,
)
from envoy.admin.crud.log import select_calculation_log_by_id
from envoy.server.model.aggregator import Aggregator
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site_reading import SiteReading, SiteReadingType
from envoy.server.model.tariff import TariffGeneratedRate
from tests.postgres_testing import generate_async_session


def assert_billing_data_types(bd: BillingData):
    assert isinstance(bd, BillingData)
    assert isinstance(bd.active_does, list)
    assert isinstance(bd.active_tariffs, list)
    assert isinstance(bd.varh_readings, list)
    assert isinstance(bd.wh_readings, list)
    assert all([isinstance(e, DynamicOperatingEnvelope) for e in bd.active_does])
    assert all([isinstance(e, TariffGeneratedRate) for e in bd.active_tariffs])
    assert all([isinstance(e, SiteReading) for e in bd.varh_readings])
    assert all([isinstance(e.site_reading_type, SiteReadingType) for e in bd.varh_readings])
    assert all([isinstance(e, SiteReading) for e in bd.wh_readings])
    assert all([isinstance(e.site_reading_type, SiteReadingType) for e in bd.wh_readings])


aest = ZoneInfo("Australia/Brisbane")  # This is UTC+10 to align with the start times in the DB


@pytest.mark.parametrize(
    "period_start, period_end, aggregator_id, tariff_id, expected_tariff_imports, expected_doe_imports, expected_wh_readings, expected_varh_readings, expected_watt_readings",  # noqa e501
    [
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            1,  # aggregator_id
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("1.1"),
                Decimal("2.1"),
                Decimal("3.1"),
                Decimal("6.1"),
            ],
            [  # expected_doe_imports
                Decimal("1.11"),
                Decimal("2.11"),
                Decimal("5.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 11),
                (1, 72, 22),
                (2, 72, 77),
            ],
            [  # expected_var_readings
                (1, 73, 55),
            ],
            [(1, 38, 99), (1, 38, 1010)],  # expected_watt_readings
        ),
        # Variation on date
        (
            datetime(2023, 9, 11, tzinfo=aest),  # Period start
            datetime(2023, 9, 12, tzinfo=aest),  # Period end
            1,  # aggregator_id
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("4.1"),
                Decimal("5.1"),
            ],
            [  # expected_doe_imports
                Decimal("3.11"),
                Decimal("4.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 33),
                (1, 72, 44),
            ],
            [  # expected_var_readings
                (1, 73, 66),
            ],
            [(1, 38, 1111)],  # expected_watt_readings
        ),
        # Variation on tariff ID
        (
            datetime(2023, 9, 11, tzinfo=aest),  # Period start
            datetime(2023, 9, 12, tzinfo=aest),  # Period end
            1,  # aggregator_id
            2,  # tariff_id
            [],  # expected_tariff_imports
            [  # expected_doe_imports
                Decimal("3.11"),
                Decimal("4.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 33),
                (1, 72, 44),
            ],
            [  # expected_var_readings
                (1, 73, 66),
            ],
            [(1, 38, 1111)],  # expected_watt_readings
        ),
        # Time mismatch
        (
            datetime(2023, 9, 9, tzinfo=aest),  # Period start
            datetime(2023, 9, 10, tzinfo=aest),  # Period end
            1,  # aggregator_id
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        # Agg ID mismatch
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            3,  # aggregator_id
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_aggregator_billing_data(
    pg_billing_data,
    period_start: datetime,
    period_end: datetime,
    aggregator_id: int,
    tariff_id: int,
    expected_tariff_imports: list,
    expected_doe_imports: list,
    expected_wh_readings: list,
    expected_varh_readings: list,
    expected_watt_readings: list,
):
    """Assert fetch billing data fetches the correct data given a pg_billing_data database"""

    async with generate_async_session(pg_billing_data) as session:
        billing_data = await fetch_aggregator_billing_data(
            period_start=period_start,
            period_end=period_end,
            aggregator_id=aggregator_id,
            session=session,
            tariff_id=tariff_id,
        )
        assert_billing_data_types(billing_data)

        assert [b.import_active_price for b in billing_data.active_tariffs] == expected_tariff_imports

        assert [b.import_limit_active_watts for b in billing_data.active_does] == expected_doe_imports

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.wh_readings
        ] == expected_wh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.varh_readings
        ] == expected_varh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.watt_readings
        ] == expected_watt_readings


@pytest.mark.parametrize(
    "calculation_log_id, tariff_id, expected_tariff_imports, expected_doe_imports, expected_wh_readings, expected_varh_readings, expected_watt_readings",  # noqa e501
    [
        (99, 1, None, None, None, None, None),
        (
            4,  # calculation_log_id
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("1.1"),
                Decimal("2.1"),
                Decimal("3.1"),
                Decimal("7.1"),
            ],
            [  # expected_doe_imports
                Decimal("1.11"),
                Decimal("2.11"),
                Decimal("6.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 11),
                (1, 72, 22),
                (3, 72, 88),
            ],
            [  # expected_var_readings
                (1, 73, 55),
            ],
            [(1, 38, 99), (1, 38, 1010)],  # expected_watt_readings
        ),
        (
            5,  # calculation_log_id
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        (
            6,  # calculation_log_id
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("1.1"),
            ],
            [  # expected_doe_imports
                Decimal("1.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 11),
            ],
            [  # expected_var_readings
                (1, 73, 55),
            ],
            [(1, 38, 99)],  # expected_watt_readings
        ),
        (
            7,  # calculation_log_id
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        (
            4,  # calculation_log_id
            99,  # tariff_id
            [],  # expected_tariff_imports
            [  # expected_doe_imports
                Decimal("1.11"),
                Decimal("2.11"),
                Decimal("6.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 11),
                (1, 72, 22),
                (3, 72, 88),
            ],
            [  # expected_var_readings
                (1, 73, 55),
            ],
            [(1, 38, 99), (1, 38, 1010)],  # expected_watt_readings
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_calculation_log_billing_data(
    pg_billing_data,
    calculation_log_id: int,
    tariff_id: int,
    expected_tariff_imports: Optional[list],
    expected_doe_imports: Optional[list],
    expected_wh_readings: Optional[list],
    expected_varh_readings: Optional[list],
    expected_watt_readings: Optional[list],
):
    """Assert fetch billing data fetches the correct data given a pg_billing_data database"""

    async with generate_async_session(pg_billing_data) as session:
        calculation_log = await select_calculation_log_by_id(session, calculation_log_id)
        if calculation_log is None:
            assert (
                expected_tariff_imports is None
                and expected_doe_imports is None
                and expected_wh_readings is None
                and expected_varh_readings is None
                and expected_watt_readings is None
            )
            return

        billing_data = await fetch_calculation_log_billing_data(
            calculation_log=calculation_log,
            session=session,
            tariff_id=tariff_id,
        )

        assert_billing_data_types(billing_data)

        assert [b.import_active_price for b in billing_data.active_tariffs] == expected_tariff_imports

        assert [b.import_limit_active_watts for b in billing_data.active_does] == expected_doe_imports

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.wh_readings
        ] == expected_wh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.varh_readings
        ] == expected_varh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.watt_readings
        ] == expected_watt_readings


@pytest.mark.parametrize(
    "period_start, period_end, site_ids, tariff_id, expected_tariff_imports, expected_doe_imports, expected_wh_readings, expected_varh_readings, expected_watt_readings",  # noqa e501
    [
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            [1, 2, 4],  # site_ids
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("1.1"),
                Decimal("2.1"),
                Decimal("3.1"),
                Decimal("6.1"),
            ],
            [  # expected_doe_imports
                Decimal("1.11"),
                Decimal("2.11"),
                Decimal("5.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 11),
                (1, 72, 22),
                (2, 72, 77),
            ],
            [  # expected_var_readings
                (1, 73, 55),
            ],
            [(1, 38, 99), (1, 38, 1010)],  # expected_watt_readings
        ),
        # Variation on sites
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            [2],  # site_ids
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("6.1"),
            ],
            [  # expected_doe_imports
                Decimal("5.11"),
            ],
            [  # expected_wh_readings
                (2, 72, 77),
            ],
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        # Variation on date
        (
            datetime(2023, 9, 11, tzinfo=aest),  # Period start
            datetime(2023, 9, 12, tzinfo=aest),  # Period end
            [1, 2, 4],  # site_ids
            1,  # tariff_id
            [  # expected_tariff_imports
                Decimal("4.1"),
                Decimal("5.1"),
            ],
            [  # expected_doe_imports
                Decimal("3.11"),
                Decimal("4.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 33),
                (1, 72, 44),
            ],
            [  # expected_var_readings
                (1, 73, 66),
            ],
            [(1, 38, 1111)],  # expected_watt_readings
        ),
        # Variation on tariff ID
        (
            datetime(2023, 9, 11, tzinfo=aest),  # Period start
            datetime(2023, 9, 12, tzinfo=aest),  # Period end
            [1, 2, 4],  # site_ids
            2,  # tariff_id
            [],  # expected_tariff_imports
            [  # expected_doe_imports
                Decimal("3.11"),
                Decimal("4.11"),
            ],
            [  # expected_wh_readings
                (1, 72, 33),
                (1, 72, 44),
            ],
            [  # expected_var_readings
                (1, 73, 66),
            ],
            [(1, 38, 1111)],  # expected_watt_readings
        ),
        # Time mismatch
        (
            datetime(2023, 9, 9, tzinfo=aest),  # Period start
            datetime(2023, 9, 10, tzinfo=aest),  # Period end
            [1, 2, 4],  # site_ids
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        # Site ID mismatch
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            [99],  # site_ids
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
        # Site ID Empty
        (
            datetime(2023, 9, 10, tzinfo=aest),  # Period start
            datetime(2023, 9, 11, tzinfo=aest),  # Period end
            [],  # site_ids
            1,  # tariff_id
            [],  # expected_tariff_imports
            [],  # expected_doe_imports
            [],  # expected_wh_readings
            [],  # expected_var_readings
            [],  # expected_watt_readings
        ),
    ],
)
@pytest.mark.anyio
async def test_fetch_sites_billing_data(
    pg_billing_data,
    period_start: datetime,
    period_end: datetime,
    site_ids: list[int],
    tariff_id: int,
    expected_tariff_imports: list,
    expected_doe_imports: list,
    expected_wh_readings: list,
    expected_varh_readings: list,
    expected_watt_readings: list,
):
    """Assert fetch billing data fetches the correct data given a pg_billing_data database"""

    async with generate_async_session(pg_billing_data) as session:
        billing_data = await fetch_sites_billing_data(
            period_start=period_start,
            period_end=period_end,
            site_ids=site_ids,
            session=session,
            tariff_id=tariff_id,
        )
        assert_billing_data_types(billing_data)

        assert [b.import_active_price for b in billing_data.active_tariffs] == expected_tariff_imports

        assert [b.import_limit_active_watts for b in billing_data.active_does] == expected_doe_imports

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.wh_readings
        ] == expected_wh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.varh_readings
        ] == expected_varh_readings

        assert [
            (b.site_reading_type.site_id, b.site_reading_type.uom, b.value) for b in billing_data.watt_readings
        ] == expected_watt_readings


@pytest.mark.anyio
async def test_fetch_aggregator(pg_base_config):
    async with generate_async_session(pg_base_config) as session:
        agg_1 = await fetch_aggregator(session, 1)
        assert isinstance(agg_1, Aggregator)
        assert agg_1.name == "Aggregator 1"
        assert agg_1.aggregator_id == 1

        agg_2 = await fetch_aggregator(session, 2)
        assert isinstance(agg_2, Aggregator)
        assert agg_2.name == "Aggregator 2"
        assert agg_2.aggregator_id == 2

        assert (await fetch_aggregator(session, 99)) is None
