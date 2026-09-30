import pytest
import numpy as np

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


def test_service_slot_json_readwrite(dummy_service):
    """Test read-write JSON slot: service publishes, proxy reads and writes."""
    slot = dummy_service.get_slot('json_slot')

    # Should be writable
    assert slot.is_read_only is False

    # Initially should return None
    assert slot.get() is None

    # Service publishes data via command
    test_data = {"test": "value", "number": 42}
    dummy_service.publish_json_slot(data=test_data)

    # Client should be able to read it
    result = slot.get()
    assert result is not None
    assert result["test"] == "value"
    assert result["number"] == 42

    # Client can also write
    client_data = {"from": "client", "value": 100}
    slot.set(client_data)

    import time
    time.sleep(0.05)

    # Should be able to read back the confirmed value
    result = slot.get()
    assert result is not None
    assert result["from"] == "client"
    assert result["value"] == 100


def test_service_slot_raw_readwrite(dummy_service):
    """Test read-write raw slot: service publishes, proxy reads and writes."""
    slot = dummy_service.get_slot('raw_slot')

    # Should be writable
    assert slot.is_read_only is False

    # Initially should return None
    assert slot.get() is None

    # Service publishes data via command
    test_data = "hello world"
    dummy_service.publish_raw_slot(data=test_data)

    # Client should be able to read it
    result = slot.get()
    assert result is not None
    assert result.decode('utf-8') == test_data

    # Client can also write
    client_data = b"from client"
    slot.set(client_data)

    import time
    time.sleep(0.05)

    # Should be able to read back the confirmed value
    result = slot.get()
    assert result is not None
    assert result == client_data


def test_service_slot_array_readwrite(dummy_service):
    """Test read-write array slot: service publishes, proxy reads and writes."""
    slot = dummy_service.get_slot('array_slot')

    # Should be writable
    assert slot.is_read_only is False

    # Initially should return None
    assert slot.get() is None

    # Service publishes data via command
    test_array = np.random.randn(16, 16).astype('float64').tolist()
    dummy_service.publish_array_slot(data=test_array)

    # Client should be able to read it
    result = slot.get()
    assert result is not None
    expected = np.array(test_array).astype('float64')
    assert np.array_equal(result, expected)

    # Client can also write
    client_array = np.ones((16, 16), dtype='float64')
    slot.set(client_array)

    import time
    time.sleep(0.05)

    # Should be able to read back the confirmed value
    result = slot.get()
    assert result is not None
    assert np.array_equal(result, client_array)


def test_service_slot_subscription(dummy_service):
    """Test slot subscription for streaming updates."""
    slot = dummy_service.get_slot('json_slot')
    subscription = slot.subscribe()

    # Publish data via command
    test_data = {"seq": 1}
    dummy_service.publish_json_slot(data=test_data)

    # Should receive the message
    msg = subscription.try_get_next_message()
    assert msg is not None


def test_service_slot_readonly_raw(dummy_service):
    """Test that readonly_raw_slot is read-only from proxy."""
    slot = dummy_service.get_slot('readonly_raw_slot')

    # The slot should be read-only
    assert slot.is_read_only

    # Attempting to set should raise an error
    with pytest.raises(RuntimeError, match="read-only"):
        slot.set(b"test data")
