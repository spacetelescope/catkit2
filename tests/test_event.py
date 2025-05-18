from catkit2.catkit_bindings import Event, EventWaitMethod, LocalMemory, is_wait_method_implemented
import threading
import pytest
import time

def event_wait(event, signaled, waiting, condition):
    waiting.set()

    event.wait(lambda: condition[0] != 0, 2)

    signaled.set()

@pytest.mark.parametrize("wait_method", [
    EventWaitMethod.Default,
    EventWaitMethod.Semaphore,
    EventWaitMethod.ConditionVariable,
    EventWaitMethod.Futex,
    EventWaitMethod.SpinLock])
def test_event(wait_method):
    if not is_wait_method_implemented(wait_method):
        pytest.skip(f"Wait method {wait_method} is not implemented.")

    memory = LocalMemory.create(1024)
    event = Event.create(memory, 'test_event')

    signaled = threading.Event()
    waiting = threading.Event()

    # The condition that the threads will wait on. This needs to be a mutable object.
    condition = [0]

    thread = threading.Thread(target=event_wait, args=(event, signaled, waiting, condition))
    thread.start()

    # Ensure that the waiting thread has started waiting.
    waiting.wait(1)
    assert waiting.is_set(), 'Something went wrong starting the waiting thread.'

    # Ensure the event is not triggered unless signaled.
    start = time.perf_counter()
    with pytest.raises(RuntimeError):
        event.wait(lambda: condition[0] != 0, 0.1)
    end = time.perf_counter()

    # Ensure that we at least waited for the timeout duration.
    assert (end - start) >= 0.1

    # Signal the event.
    condition[0] = 1
    event.signal()

    # Wait for the wait to end.
    signaled.wait(1)

    # Ensure that the wait actually ended and was triggered.
    assert signaled.is_set(), 'The waiting thread was not signaled.'

    thread.join()
