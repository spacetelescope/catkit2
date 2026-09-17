from catkit2.catkit_bindings import LocalMemory, HybridPoolAllocator, BuddyAllocator, PoolAllocator, test_helpers
import pytest
import threading

DYNAMIC_CAPACITY = 512 * 1024 * 1024
MIN_SIZE = 16
MIN_SIZE_POOL = 1024
POOL_CAPACITY = 16

STRESS_NUM_THREADS = 8
STRESS_ITERATIONS = 20000

def _run_stress(context_class, allocator):
    params = test_helpers.default_stress_params()
    params.num_threads = STRESS_NUM_THREADS
    params.iterations = STRESS_ITERATIONS

    context = context_class(allocator, params)

    exceptions = []

    def run_with_exception_capture(tid):
        try:
            context.run_thread(tid)
        except Exception as e:
            exceptions.append(e)

    threads = []
    for i in range(params.num_threads):
        t = threading.Thread(target=run_with_exception_capture, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if exceptions:
        raise exceptions[0]

    return context

@pytest.mark.parametrize("allocator_constructor", [
    lambda header: BuddyAllocator.create(header, DYNAMIC_CAPACITY, MIN_SIZE),
    lambda header: HybridPoolAllocator.create(header, DYNAMIC_CAPACITY, MIN_SIZE, MIN_SIZE_POOL),
])
def test_dynamic_size_allocator(allocator_constructor):
    header = LocalMemory.create(1024 * 1024 * 512)
    allocator = allocator_constructor(header)

    handle = allocator.allocate(128)

    assert allocator.acquire(handle) is True, "Memory block should still be allocated."
    assert allocator.release(handle) is False, "Memory block was unexpectedly deallocated while ref count == 1."
    assert allocator.release(handle) is True, "Memory block was not deallocated when ref count == 0."

    # Allocating a block too large should raise an error.
    with pytest.raises(RuntimeError):
        allocator.allocate(1024 * 1024 * 1024)

@pytest.mark.parametrize("allocator_constructor", [
    lambda header: PoolAllocator.create(header, POOL_CAPACITY),
])
def test_fixed_size_allocator(allocator_constructor):
    header = LocalMemory.create(1024 * 1024 * 512)
    allocator = allocator_constructor(header)

    handle = allocator.allocate()

    assert allocator.acquire(handle) is True, "Memory block should still be allocated."
    assert allocator.release(handle) is False, "Memory block was unexpectedly deallocated while ref count == 1."
    assert allocator.release(handle) is True, "Memory block was not deallocated when ref count == 0."

    for _ in range(POOL_CAPACITY):
        allocator.allocate()

    # Allocating more blocks than the pool capacity should raise an error.
    with pytest.raises(RuntimeError):
        allocator.allocate()

def test_pool_allocator_stress():
    memory = LocalMemory.create(1024 * 1024 * 512)
    allocator = PoolAllocator.create(memory, 100000)

    context = _run_stress(test_helpers.PoolAllocatorStressContext, allocator)

    assert context.success, f"PoolAllocator stress test failed: double_frees={context.double_free_detected}"
    assert context.total_allocations > 0, "PoolAllocator should have allocated some blocks"
    assert context.total_releases > 0, "PoolAllocator should have released some blocks"
    assert context.total_releases + context.failed_allocations >= context.total_allocations, "PoolAllocator allocations should either succeed or fail"

def test_buddy_allocator_stress():
    memory = LocalMemory.create(1024 * 1024 * 512)
    allocator = BuddyAllocator.create(memory, DYNAMIC_CAPACITY, MIN_SIZE)

    context = _run_stress(test_helpers.BuddyAllocatorStressContext, allocator)

    assert context.success, f"BuddyAllocator stress test failed: double_frees={context.double_free_detected}"
    assert context.total_allocations > 0, "BuddyAllocator should have allocated some blocks"
    assert context.total_releases > 0, "BuddyAllocator should have released some blocks"
    assert context.total_releases + context.failed_allocations >= context.total_allocations, "BuddyAllocator allocations should either succeed or fail"

def test_hybrid_pool_allocator_stress():
    memory = LocalMemory.create(1024 * 1024 * 512)
    allocator = HybridPoolAllocator.create(memory, DYNAMIC_CAPACITY, MIN_SIZE, MIN_SIZE_POOL)

    context = _run_stress(test_helpers.HybridPoolAllocatorStressContext, allocator)

    assert context.success, f"HybridPoolAllocator stress test failed: double_frees={context.double_free_detected}"
    assert context.total_allocations > 0, "HybridPoolAllocator should have allocated some blocks"
    assert context.total_releases > 0, "HybridPoolAllocator should have released some blocks"
    assert context.total_releases + context.failed_allocations >= context.total_allocations, "HybridPoolAllocator allocations should either succeed or fail"
