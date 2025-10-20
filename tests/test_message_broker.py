from catkit2.catkit_bindings import LocalMemory, LocalMessageBroker, MessageSubscriptionMode
import numpy as np
import pytest


# Create a new broker for each test to avoid state pollution
# (service inactivity detector relies on timestamps from previous publishes)
@pytest.fixture()
def broker():
    """Create a fresh broker instance for each test."""
    header_memory = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)
    broker = LocalMessageBroker.create(header_memory, [block])
    yield broker


def test_message_subscription(broker):
    topic = "test_message_subscription"

    subscription_newest = broker.subscribe(
        topic, mode=MessageSubscriptionMode.NewestOnly
    )
    subscription_sequential = broker.subscribe(
        topic, mode=MessageSubscriptionMode.Sequential
    )

    for i in range(3):
        arr = np.array([i + 10]).astype('int32')
        message = broker.prepare_message(topic, arr.nbytes)
        message.payload = arr
        broker.publish_message(message)

    # First message from NewestOnly should skip non-current messages
    m = subscription_newest.get_next_message(0.01)
    assert m is not None
    assert m.frame_id == 2
    assert m.payload[0] == 12

    # Getting next should raise timeout or service inactive (no more messages)
    # The exact exception depends on timing and service activity detection
    with pytest.raises(
        RuntimeError,
        match="(Waiting time has expired|Service appears to be inactive)"
    ):
        subscription_newest.get_next_message(0.01)

    # First message from Sequential should not skip any messages
    m = subscription_sequential.get_next_message(0.01)
    assert m is not None
    assert m.frame_id == 0
    assert m.payload[0] == 10

    # Second message
    m = subscription_sequential.get_next_message(0.01)
    assert m is not None
    assert m.frame_id == 1
    assert m.payload[0] == 11

    # Third message
    m = subscription_sequential.get_next_message(0.01)
    assert m is not None
    assert m.frame_id == 2
    assert m.payload[0] == 12

    # Getting next should raise timeout or service inactive (only 3 messages)
    # The exact exception depends on timing and service activity detection
    with pytest.raises(
        RuntimeError,
        match="(Waiting time has expired|Service appears to be inactive)"
    ):
        subscription_sequential.get_next_message(0.01)

    # NewestOnly subscription starting at ID 1 should get newest (ID 2)
    subscription_newest2 = broker.subscribe(
        topic, preferred_next_frame_id=1,
        mode=MessageSubscriptionMode.NewestOnly
    )
    m = subscription_newest2.get_next_message(0.01)
    assert m.frame_id == 2

    # Sequential subscription starting at ID 1 should get ID 1
    subscription_sequential2 = broker.subscribe(
        topic, preferred_next_frame_id=1,
        mode=MessageSubscriptionMode.Sequential
    )
    m = subscription_sequential2.get_next_message(0.01)
    assert m.frame_id == 1


dtypes = [
    'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32',
    'int64', 'uint64', 'float32', 'float64'
]
shapes = [[10], [10, 10], [10, 10, 10], [10, 10, 10, 10]]


@pytest.mark.parametrize("shape", shapes)
@pytest.mark.parametrize("dtype", dtypes)
def test_message_dtype_and_shape(broker, shape, dtype):
    topic = f'{dtype}_{len(shape)}_topic'

    arr = np.abs(np.random.randn(*shape)).astype(dtype)

    message = broker.prepare_message(topic, arr.nbytes)
    message.payload = arr
    broker.publish_message(message)

    retrieved_message = broker.get_current_message(topic)

    assert np.all(arr == retrieved_message.payload)
    assert retrieved_message.payload.dtype == dtype
    assert np.array_equal(retrieved_message.payload.shape, shape)
    assert retrieved_message.payload.nbytes == arr.nbytes
    assert retrieved_message.payload.size == arr.size
    assert retrieved_message.payload.itemsize == arr.itemsize
    assert retrieved_message.payload.ndim == len(shape)
    assert retrieved_message.topic == topic


def test_message_broker_publish_array(broker):
    arr = np.random.randn(10)
    broker.publish_array('test_array', arr)

    msg = broker.get_current_message('test_array')
    assert np.array_equal(msg.payload, arr)


def test_message_broker_publish_data(broker):
    data = b'abcd'
    broker.publish_data('test_data', data)

    msg = broker.get_current_message('test_data')
    assert msg.payload.data == data
    assert msg.payload.dtype == 'uint8'


def test_message_broker_publish(broker):
    topic = "test_message_broker_publish"
    data = b'hello world'
    arr = np.frombuffer(data, dtype='uint8')

    broker.publish_data(topic, data)

    retrieved_message = broker.get_current_message(topic)

    assert (retrieved_message.payload == arr).all()


def test_message_broker_trace_id(broker):
    topic = "test_message_broker_trace_id"
    data = b'hello world'

    broker.publish_data(topic, data)
    message_1 = broker.get_current_message(topic)

    broker.publish_data(topic, data * 2)
    message_2 = broker.get_current_message(topic)

    assert str(message_2.trace_id) != str(message_1.trace_id)

    broker.publish_data(topic, data * 3, trace_id=message_1.trace_id)
    message_3 = broker.get_current_message(topic)

    assert str(message_3.trace_id) == str(message_1.trace_id)
