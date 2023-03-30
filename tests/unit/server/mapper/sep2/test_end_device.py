from datetime import datetime

from envoy.server.mapper.sep2.end_device import EndDeviceListMapper, EndDeviceMapper
from envoy.server.model.site import Site
from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from tests.data.fake.generator import generate_class_instance, generate_value


def test_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)

    result_all_set = EndDeviceMapper.map_to_response(site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, EndDeviceResponse)
    assert result_all_set.changedTime == site_all_set.changed_time.timestamp()
    assert result_all_set.lFDI == site_all_set.lfdi

    result_optional = EndDeviceMapper.map_to_response(site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, EndDeviceResponse)
    assert result_optional.changedTime == site_optional.changed_time.timestamp()
    assert result_optional.lFDI == site_optional.lfdi


def test_list_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site1: Site = generate_class_instance(Site, seed=303, optional_is_none=False, generate_relationships=False)
    site2: Site = generate_class_instance(Site, seed=404, optional_is_none=False, generate_relationships=True)
    site3: Site = generate_class_instance(Site, seed=505, optional_is_none=True, generate_relationships=False)
    site4: Site = generate_class_instance(Site, seed=606, optional_is_none=True, generate_relationships=True)
    site_count = 199

    all_sites = [site1, site2, site3, site4]

    result = EndDeviceListMapper.map_to_response(all_sites, site_count)
    assert result is not None
    assert isinstance(result, EndDeviceListResponse)
    assert result.all_ == site_count
    assert result.result == len(all_sites)
    assert isinstance(result.EndDevice, list)
    assert len(result.EndDevice) == len(all_sites)
    assert all([isinstance(ed, EndDeviceResponse) for ed in result.EndDevice])
    assert len(set([ed.lFDI for ed in result.EndDevice])) == len(all_sites), f"Expected {len(all_sites)} unique LFDI's in the children"

    empty_result = EndDeviceListMapper.map_to_response([], site_count)
    assert empty_result is not None
    assert isinstance(empty_result, EndDeviceListResponse)
    assert empty_result.all_ == site_count
    assert isinstance(empty_result.EndDevice, list)
    assert len(empty_result.EndDevice) == 0

    no_result = EndDeviceListMapper.map_to_response([], 0)
    assert no_result is not None
    assert isinstance(no_result, EndDeviceListResponse)
    assert no_result.all_ == 0
    assert isinstance(no_result.EndDevice, list)
    assert len(no_result.EndDevice) == 0


def test_map_from_request():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    end_device_all_set: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=101, optional_is_none=False)
    end_device_optional: EndDeviceRequest = generate_class_instance(EndDeviceRequest, seed=202, optional_is_none=True)
    changed_time: datetime = generate_value(datetime, 303)
    aggregator_id: int = 404

    result_all_set = EndDeviceMapper.map_from_request(end_device_all_set, aggregator_id, changed_time)
    assert result_all_set is not None
    assert isinstance(result_all_set, Site)
    assert result_all_set.changed_time == changed_time
    assert result_all_set.aggregator_id == aggregator_id
    assert result_all_set.lfdi == end_device_all_set.lFDI

    result_optional = EndDeviceMapper.map_from_request(end_device_optional, aggregator_id, changed_time)
    assert result_optional is not None
    assert isinstance(result_optional, Site)
    assert result_optional.changed_time == changed_time
    assert result_optional.aggregator_id == aggregator_id
    assert result_optional.lfdi == end_device_optional.lFDI
