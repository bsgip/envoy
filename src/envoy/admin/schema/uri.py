"""Defines all the URIs"""

AdminTariffUri = "/admin/tariff/TODO"
AdminDoeUri = "/admin/doe/TODO"

TariffCreateUri = "/tariff"
TariffUpdateUri = "/tariff/{tariff_id}"
TariffGeneratedRateCreateUri = TariffUpdateUri + "/tariff_generated_rate"
TariffGeneratedRateUpdateUri = TariffGeneratedRateCreateUri + "/{tariff_generated_rate_id}"
