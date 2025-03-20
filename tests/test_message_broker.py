import catkit2

from catkit2.catkit_bindings import Memory, LocalMemory, SharedMemory, MessageBroker, get_timestamp

def test_message_broker():
    header = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = MessageBroker.create(header, [block])

    for _ in range(10):
        start = get_timestamp()

        message = broker.prepare_message("topic", 16, 0)
        broker.publish_message(message, True)

        end = get_timestamp()
        print(f"Time taken: {end - start} ns")

    N = 100000

    start = get_timestamp()

    for _ in range(N):
        message = broker.prepare_message("topic", 16, 0)
        message.payload[:] = b'0123456789abcdef'
        broker.publish_message(message, True)


    end = get_timestamp()
    print(f"Time taken: {(end - start) / N} ns")

test_message_broker()
