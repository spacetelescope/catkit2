from catkit2.catkit_bindings import Event, EventWaitMethod, LocalMemory, SharedMemory, is_wait_method_implemented
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

def event_wait_and_time(event, condition, timeout, started, result):
    started.set()

    start = time.perf_counter()

    try:
        event.wait(condition, timeout)
        result['success'] = True
    except RuntimeError:
        result['success'] = False

    result['duration'] = time.perf_counter() - start

@pytest.mark.parametrize("wait_method", [
    EventWaitMethod.Default,
    EventWaitMethod.Semaphore,
    EventWaitMethod.ConditionVariable,
    EventWaitMethod.Futex,
    EventWaitMethod.SpinLock])
def test_event_wait_from_second_mapping(wait_method):
    # Regression test: waiting on the same event through two different mappings of the
    # same shared memory (as happens between processes) must not block the signaling side.
    # On macOS, process-shared pthread condition variables reject the second waiter without
    # releasing the mutex, which used to stall every signaler until the second waiter timed out.
    if not is_wait_method_implemented(wait_method):
        pytest.skip(f"Wait method {wait_method} is not implemented.")

    memory_id = 'test_event_second_mapping'
    memory_created = SharedMemory.create(memory_id, 4096)
    event_created = Event.create(memory_created, memory_id)

    memory_opened = SharedMemory.open(memory_id)
    event_opened = Event.open(memory_opened)

    condition = [0]

    # Waiter A waits on the created mapping for a condition that we will satisfy shortly.
    started_a = threading.Event()
    result_a = {}
    thread_a = threading.Thread(target=event_wait_and_time,
                                args=(event_created, lambda: condition[0] != 0, 3, started_a, result_a))

    # Waiter B waits on the opened mapping for a condition that never becomes true.
    started_b = threading.Event()
    result_b = {}
    thread_b = threading.Thread(target=event_wait_and_time,
                                args=(event_opened, lambda: False, 1.5, started_b, result_b))

    try:
        thread_a.start()
        started_a.wait(1)
        time.sleep(0.05)  # Make sure A is actually parked in the wait.

        thread_b.start()
        started_b.wait(1)
        time.sleep(0.05)  # Make sure B has tried to park as well.

        # Signal from the opened mapping; A should wake up promptly regardless of B.
        condition[0] = 1

        start = time.perf_counter()
        event_opened.signal()
        signal_duration = time.perf_counter() - start

        thread_a.join(3)
    finally:
        thread_a.join(5)
        thread_b.join(5)

    assert signal_duration < 0.5, f'signal() blocked for {signal_duration:.2f} s.'
    assert result_a.get('success'), 'Waiter A was not woken up.'
    assert result_a['duration'] < 0.5, f'Waiter A took {result_a["duration"]:.2f} s to wake up.'

    # B must have timed out on its own, without being stuck for longer than its timeout.
    assert not result_b.get('success')
    assert result_b['duration'] < 3
