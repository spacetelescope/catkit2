#ifndef BUDDY_ALLOCATOR_H
#define BUDDY_ALLOCATOR_H

#include <cstdint>
#include <cstddef>
#include <limits>
#include <atomic>

class BuddyAllocator
{
public:
	BuddyAllocator(std::size_t max_size, std::size_t depth);
    ~BuddyAllocator();

    using Handle = std::size_t;

    static constexpr Handle INVALID_HANDLE = 0;

    Handle Allocate(std::size_t size);
    void Deallocate(Handle handle);

    std::size_t GetOffset(Handle handle) const;

private:
    Handle TryAllocate(Handle index);

    void FreeNode(Handle handle, Handle upper_bound);
    void Unmark(Handle handle, Handle upper_bound);

    std::size_t GetLevel(Handle n) const;
    std::size_t GetSize(Handle n) const;

    std::size_t m_MaxSize;
    std::size_t m_Depth;

    std::atomic_uint8_t *m_Tree;
};

#endif // BUDDY_ALLOCATOR_H
