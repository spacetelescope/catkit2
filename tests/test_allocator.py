from catkit2.catkit_bindings import LocalMemory, HybridPoolAllocator, BuddyAllocator, PoolAllocator
import pytest

DYNAMIC_CAPACITY = 1024 * 1024
MIN_SIZE = 16
MIN_SIZE_POOL = 1024
POOL_CAPACITY = 16

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
