#ifndef FREE_LIST_ALLOCATOR_H
#define FREE_LIST_ALLOCATOR_H

#include "PoolAllocator.h"

#include <atomic>
#include <cstdint>

// A simple lock-free free list allocator.
template <std::size_t MaxNumBlocks, std::size_t Alignment>
class FreeListAllocator
{
public:
	using BlockHandle = std::int32_t;
	using Offset = std::uint64_t;
	using Size = std::uint64_t;

	static const BlockHandle INVALID_HANDLE = -1;

	// A unique descriptor of the block.
	class BlockDescriptor
	{
	public:
		BlockDescriptor()
		{
		}

		BlockDescriptor(Offset offset, Size size, bool is_free)
		{
			Set(offset, size, is_free);
		}

		void Set(const Offset &offset, const Size &size, const bool &is_free)
		{
			m_OffsetAndFreeFlag = (offset & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
			m_Size = size;
		}

		Offset GetOffset() const
		{
			return m_OffsetAndFreeFlag & ~_FREE_FLAG;
		}

		void SetOffset(const Offset &new_offset)
		{
			m_OffsetAndFreeFlag = new_offset | (m_OffsetAndFreeFlag & _FREE_FLAG);
		}

		Size GetSize() const
		{
			return m_Size;
		}

		void SetSize(const Size &new_size)
		{
			m_Size = new_size;
		}

		bool IsFree() const
		{
			return m_OffsetAndFreeFlag & _FREE_FLAG;
		}

		void SetFree(const bool &is_free)
		{
			m_OffsetAndFreeFlag = (m_OffsetAndFreeFlag & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
		}

	private:
		Offset m_OffsetAndFreeFlag;
		Size m_Size;

		static const Offset _FREE_FLAG = 0x8000000000000000;
	};

	// Check that the BlockDescriptor is lock-free atomic.
	static_assert(std::atomic<BlockDescriptor>::is_always_lock_free);

	struct Block
	{
		std::atomic<BlockDescriptor> descriptor;
		std::atomic<BlockHandle> next;
	};

	FreeListAllocator(std::size_t buffer_size);
	~FreeListAllocator();

	BlockHandle Allocate(std::size_t size);
	void Deallocate(BlockHandle index);

	std::size_t GetOffset(BlockHandle index);

	void PrintState();
	size_t GetNumFreeBlocks() const;

private:
	PoolAllocator<MaxNumBlocks> m_BlockAllocator;
	Block m_Blocks[MaxNumBlocks];

	std::atomic<BlockHandle> m_Head;

	BlockHandle FindFirstFreeBlock(std::size_t size);

	void InsertBlockSorted(BlockHandle index);
	bool RemoveBlock(BlockHandle index);

	bool MarkBlockAsFree(BlockHandle index, bool mark_free);

	bool TryCoalesceBlocks(BlockHandle a, BlockHandle b, bool owner_of_a);
};

#include "FreeListAllocator.inl"

#endif // FREE_LIST_ALLOCATOR_H
