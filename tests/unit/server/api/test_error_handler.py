from http import HTTPStatus

from envoy_schema.server.schema.sep2.error import ErrorResponse
from envoy_schema.server.schema.sep2.types import ReasonCodeType

from envoy.server.api.error_handler import generate_error_response, http_status_code_to_reason_code
from envoy.server.api.response import SEP_XML_MIME


def test_http_status_code_to_reason_code_nocrash():
    """Just a quick scan of values to make sure the utility functions work with a variety of inputs"""

    # test ints
    for i in range(-600, 600):
        reason_code = http_status_code_to_reason_code(i)
        assert reason_code is not None and type(reason_code) == ReasonCodeType, f"Failure at {i}"

    # test enums
    for e in HTTPStatus:
        reason_code = http_status_code_to_reason_code(e)
        assert reason_code is not None and type(reason_code) == ReasonCodeType, f"Failure at {e}"

        # test that enum values are equivalent to the enums directly (eg 500 == INTERNAL_SERVER_ERROR)
        assert http_status_code_to_reason_code(e.value) == http_status_code_to_reason_code(e)

    reason_code = http_status_code_to_reason_code(None)
    assert reason_code is not None and type(reason_code) == ReasonCodeType

    reason_code = http_status_code_to_reason_code("401")
    assert reason_code is not None and type(reason_code) == ReasonCodeType


def test_generate_error_response_optional_message_encoding():
    """Test that special chars decode fine (this isn't exhaustive)"""
    message = "My custom message <>&amp;\n\t123#--"
    response = generate_error_response(HTTPStatus.BAD_GATEWAY, message)
    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(response.body)
    assert error_response.message == message
    assert error_response.maxRetryDuration is None


def test_generate_error_response_optional_message_missing():
    """Tests that a none message isn't going to crash anything"""
    response = generate_error_response(HTTPStatus.IM_A_TEAPOT, None)
    assert response.status_code == HTTPStatus.IM_A_TEAPOT
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(response.body)
    assert error_response.message is None
    assert error_response.maxRetryDuration is None


def test_generate_error_response_optional_retry_duration():
    """Tests that max_retry_duration is encoded"""
    response = generate_error_response(HTTPStatus.OK, max_retry_duration=54321)
    assert response.status_code == HTTPStatus.OK
    assert response.media_type == SEP_XML_MIME

    # test the message encodes/decodes OK
    error_response: ErrorResponse = ErrorResponse.from_xml(response.body)
    assert error_response.message is None
    assert error_response.maxRetryDuration == 54321
