import pytest

def test_service_property(dummy_service):
    # We should be able to read and write to a property.
    dummy_service.readwrite_property = 2
    assert dummy_service.readwrite_property == 2

def test_service_property_readonly(dummy_service):
    expected_value = dummy_service.config['readonly_property']

    # We should be able to read from a readonly property.
    assert dummy_service.readonly_property == expected_value

    # Writing to a readonly property should yield an exception.
    with pytest.raises(RuntimeError):
        dummy_service.readonly_property = 3

def test_service_datastream_backed_property_readonly(dummy_service):
    expected_value = dummy_service.config['readonly_property']

    # We should be able to read from a streambacked readonly property.
    assert dummy_service.readonly_stream_backed_property == expected_value

    with pytest.raises(RuntimeError):
        dummy_service.readonly_stream_backed_property = 3

def test_service_datastream_backed_property(dummy_service):
    # We should be able to read and write to a streambacked property.
    dummy_service.readwrite_stream_backed_property = 2
    assert dummy_service.readwrite_stream_backed_property == 2

    # If a wrong data type is given, it will be casted to the right one.
    dummy_service.readwrite_stream_backed_property = 3.0
    assert dummy_service.readwrite_stream_backed_property == 3

    # If an uncompatible data type, this will raise an exception.
    with pytest.raises(RuntimeError):
        dummy_service.readwrite_stream_backed_property = '4'

def test_service_command(dummy_service):
    a = 'a'
    b = 'b'

    assert dummy_service.add(a=a, b=b) == a + b

def test_service_datastream(dummy_service):
    assert dummy_service.stream.dtype == 'float64'

    # Check that push_on_stream() submits something to the datastream.
    before_id = dummy_service.stream.get_latest_frame().id
    dummy_service.push_on_stream()
    after_id = dummy_service.stream.get_latest_frame().id

    assert after_id == before_id + 1
