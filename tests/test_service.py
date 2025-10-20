import pytest

def test_service_property(dummy_service):
    # We should be able to read and write to a property.
    try:
        dummy_service.readwrite_property = 2
        assert dummy_service.readwrite_property == 2
    except RuntimeError as e:
        if "appears to be inactive" in str(e):
            pytest.skip(f"Service inactive: {e}")
        raise

def test_service_property_readonly(dummy_service):
    try:
        expected_value = dummy_service.config['readonly_property']

        # We should be able to read from a readonly property.
        assert dummy_service.readonly_property == expected_value

        # Writing to a readonly property should yield an exception.
        with pytest.raises(RuntimeError):
            dummy_service.readonly_property = 3
    except RuntimeError as e:
        if "appears to be inactive" in str(e):
            pytest.skip(f"Service inactive: {e}")
        raise

def test_service_command(dummy_service):
    try:
        a = 'a'
        b = 'b'

        assert dummy_service.add(a=a, b=b) == a + b
    except RuntimeError as e:
        if "appears to be inactive" in str(e):
            pytest.skip(f"Service inactive: {e}")
        raise

def test_service_datastream(dummy_service):
    try:
        assert dummy_service.stream.dtype == 'float64'

        # Check that push_on_stream() submits something to the datastream.
        before_id = dummy_service.stream.get_latest_frame().id
        dummy_service.push_on_stream()
        after_id = dummy_service.stream.get_latest_frame().id

        assert after_id == before_id + 1
    except RuntimeError as e:
        if "appears to be inactive" in str(e):
            pytest.skip(f"Service inactive: {e}")
        raise
