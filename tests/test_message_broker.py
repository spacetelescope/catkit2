from catkit2.catkit_bindings import LocalMemory, MessageBroker, MessageSubscriptionMode
import numpy as np
import pytest

@pytest.fixture(scope='module')
def broker():
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = MessageBroker.create(header, [block])
    yield broker

def test_message_subscription(broker):
    topic = "test_message_subscription"

    subscription_newest = broker.subscribe(topic, mode=MessageSubscriptionMode.NewestOnly)
    subscription_sequential = broker.subscribe(topic, mode=MessageSubscriptionMode.Sequential)

    for i in range(3):
        arr = np.array([i]).astype('int32')
        message = broker.prepare_message(topic, arr.nbytes)
        message.payload = arr
        broker.publish_message(message)

    assert subscription_newest.next_message_id == 2
    assert subscription_sequential.next_message_id == 0

    message_1 = subscription_newest.get_next_message(0.01)
    message_2 = subscription_sequential.get_next_message(0.01)
    message_3 = subscription_sequential.get_next_message(0.01)

    assert message_1 is not None
    assert message_2 is not None
    assert message_3 is not None

    assert message_1.payload[0] == 2
    assert message_2.payload[0] == 0
    assert message_3.payload[0] == 1

    assert subscription_newest.try_get_next_message() is None

    m = subscription_sequential.try_get_next_message()
    assert m is not None
    assert m.payload[0] == 2

    assert subscription_sequential.try_get_next_message() is None

dtypes = ['int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64', 'float32', 'float64', 'complex64', 'complex128']
shapes = [[10], [10, 10], [10, 10, 10], [10, 10, 10, 10]]


@pytest.mark.parametrize("shape", shapes)
@pytest.mark.parametrize("dtype", dtypes)
def test_message_dtype_and_shape(broker, shape, dtype):
    topic = f'{dtype}_{len(shape)}_topic'

    arr = np.abs(np.random.randn(*shape)).astype(dtype)

    message = broker.prepare_message(topic, arr.nbytes)
    message.payload = arr
    broker.publish_message(message)

    retrieved_message = broker.get_newest_message(topic)

    assert np.all(arr == retrieved_message.payload)
    assert retrieved_message.payload.dtype == dtype
    assert np.allclose(retrieved_message.payload.shape, shape)
    assert retrieved_message.payload.nbytes == arr.nbytes
    assert retrieved_message.payload.size == arr.size
    assert retrieved_message.payload.itemsize == arr.itemsize
    assert retrieved_message.payload.ndim == len(shape)
    assert retrieved_message.topic == topic

def test_message_broker_publish(broker):
    topic = "test_message_broker_publish"
    data = b'hello world'
    arr = np.frombuffer(data, dtype='uint8')

    broker.publish_data(topic, data)

    retrieved_message = broker.get_newest_message(topic)

    assert (retrieved_message.payload == arr).all()

def test_message_broker_trace_id(broker):
    topic = "test_message_broker_trace_id"
    data = b'hello world'
    arr = np.frombuffer(data, dtype='uint8')

    broker.publish_data(topic, data)
    message_1 = broker.get_newest_message(topic)

    broker.publish_data(topic, data * 2)
    message_2 = broker.get_newest_message(topic)

    assert str(message_2.trace_id) != str(message_1.trace_id)

    broker.publish_data(topic, data * 3, trace_id=message_1.trace_id)
    message_3 = broker.get_newest_message(topic)

    assert str(message_3.trace_id) == str(message_1.trace_id)
