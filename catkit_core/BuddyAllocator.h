#ifndef BUDDY_ALLOCATOR_H
#define BUDDY_ALLOCATOR_H

#include "Shareable.h"

#include <cstdint>
#include <cstddef>
#include <limits>
#include <atomic>
#include <memory>

class BuddyAllocator : public Shareable
{
public:
	virtual ~BuddyAllocator() = default;

	static std::unique_ptr<BuddyAllocator> Create(StructStream &stream, std::size_t max_size, std::size_t min_size);
	static std::unique_ptr<BuddyAllocator> Open(StructStream &stream);

	ShareableType GetType() const override;
	static std::size_t GetSharedStateSize(std::size_t max_size, std::size_t min_size);

	using Handle = std::size_t;

	static constexpr Handle INVALID_HANDLE = 0;

	Handle Allocate(std::size_t size);
	bool Acquire(Handle handle);
	bool Release(Handle handle);

	std::size_t GetOffset(Handle handle) const;

	void PrintState() const;

private:
	BuddyAllocator(std::size_t capacity, std::size_t min_size, std::atomic_uint16_t *tree, std::atomic_size_t *last_success);

	Handle TryAllocate(Handle index);

	void FreeNode(Handle handle, std::size_t upper_bound);
	void Unmark(Handle handle, std::size_t upper_bound);

	std::size_t GetLevel(Handle n) const;
	std::size_t GetSize(Handle n) const;

	std::size_t m_Capacity;
	std::size_t m_MinSize;
	std::size_t m_Depth;

	std::atomic_uint16_t *m_Tree;
	std::atomic_size_t *m_LastSuccessfulAllocation;
};

#endif // BUDDY_ALLOCATOR_H
