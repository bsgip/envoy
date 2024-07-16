import urllib

import pytest
from httpx import AsyncClient
import envoy_schema.server.schema.uri as uris

from tests.data.certificates.certificate1 import TEST_CERTIFICATE_FINGERPRINT as AGG_1_VALID_CERT
from tests.integration.integration_server import cert_header


@pytest.mark.anyio
@pytest.mark.allow_eq_xmlns_middleware
async def test_AllowEquivalentXmlNsMiddleware(client: AsyncClient, pg_base_config):
    xml_body = b"""<MirrorMeterReading
            xmlns="urn:ieee:std:2030.5:ns"
            xmlns:csipaus="http://csipaus.org/ns"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" href="" xsi:type="">
            <description></description>
            <mRID>1234</mRID>
            <version></version>
            <lastUpdateTime></lastUpdateTime>
            <nextUpdateTime></nextUpdateTime>
            <MirrorReadingSet href="" xsi:type="">
                <description></description>
                <mRID>1234abc</mRID>
                <version></version>
                <timePeriod>
                    <duration>603</duration>
                    <start>1341579365</start>
                </timePeriod>
                <Reading href="" xsi:type="" subscribable="0">
                    <consumptionBlock>0</consumptionBlock>
                    <qualityFlags>00</qualityFlags>
                    <timePeriod>
                        <duration>301</duration>
                        <start>1341579365</start>
                    </timePeriod>
                    <touTier>0</touTier>
                    <value>-10</value>
                    <localID>123</localID>
                </Reading>
                <Reading href="" xsi:type="" subscribable="0">
                    <consumptionBlock>0</consumptionBlock>
                    <qualityFlags>00</qualityFlags>
                    <timePeriod>
                        <duration>302</duration>
                        <start>1341579666</start>
                    </timePeriod>
                    <touTier>0</touTier>
                    <value>9</value>
                    <localID>0f0d</localID>
                </Reading>
            </MirrorReadingSet>
        </MirrorMeterReading>
    """

    response = await client.post(
        uris.MirrorUsagePointUri.format(mup_id=1),
        content=xml_body,
        headers={cert_header: urllib.parse.quote(AGG_1_VALID_CERT)},
    )
    assert response
