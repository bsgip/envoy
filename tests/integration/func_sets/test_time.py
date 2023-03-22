import urllib.parse
from datetime import datetime

from server.schema.sep2.time import TimeResponse
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_PEM as VALID_PEM
from tests.integration.integration_server import cert_pem_header, create_test_server
from tests.integration.response import assert_status_code, read_response_body_string, run_basic_unauthorised_tests


def test_get_time_resource(pg_base_config):
    with create_test_server(pg_base_config) as client:
        response = client.get('/tm', headers={cert_pem_header: urllib.parse.quote(VALID_PEM)})
        assert_status_code(response, 200)
        body = read_response_body_string(response)
        assert len(body) > 0

        parsed_response: TimeResponse = TimeResponse.from_xml(body)

        diff = datetime.now().timestamp() - parsed_response.currentTime
        assert diff > 0 and diff < 20, f"Diff between now and the timestamp value is {diff}. Was expected to be small"
        assert parsed_response.quality == 4


def test_get_time_resource_unauthorised(pg_base_config):
    with create_test_server(pg_base_config) as client:
        run_basic_unauthorised_tests(client, '/tm', method='GET')


def test_get_time_resource_invalid_methods(pg_base_config):
    with create_test_server(pg_base_config) as client:
        response = client.put('/tm', headers={cert_pem_header: VALID_PEM})
        assert_status_code(response, 405)

        response = client.delete('/tm', headers={cert_pem_header: VALID_PEM})
        assert_status_code(response, 405)

        response = client.post('/tm', headers={cert_pem_header: VALID_PEM})
        assert_status_code(response, 405)
