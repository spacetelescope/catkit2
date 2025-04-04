from catkit2.catkit_bindings import LocalMemory, MessageBroker, get_timestamp
import numpy as np

def test_message_broker():
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = MessageBroker.create(header, [block])

    for _ in range(1):
        start = get_timestamp()

        message = broker.prepare_message("topic", 16, 0)
        broker.publish_message(message, True)

        end = get_timestamp()
        print(f"Time taken: {end - start} ns")

    N = 100

    arr = np.random.randn(4, 4)

    start = get_timestamp()

    for _ in range(N):
        message = broker.prepare_message("topic", arr.nbytes, 0)
        message.payload = arr
        broker.publish_message(message, True)

    end = get_timestamp()
    print(f"Time taken: {(end - start) / N} ns")
