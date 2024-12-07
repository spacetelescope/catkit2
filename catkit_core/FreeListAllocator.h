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
	using Offset = std::uint32_t;
	using Size = std::uint32_t;

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
			m_Offset = offset;
			m_SizeAndFreeFlag = (size & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
		}

		Offset GetOffset() const
		{
			return m_Offset;
		}

		void SetOffset(const Offset &new_offset)
		{
			m_Offset = new_offset;
		}

		Size GetSize() const
		{
			return m_SizeAndFreeFlag & ~_FREE_FLAG;
		}

		void SetSize(const Size &new_size)
		{
			m_SizeAndFreeFlag = (new_size & ~_FREE_FLAG) | (m_SizeAndFreeFlag & _FREE_FLAG);
		}

		bool IsFree() const
		{
			return m_SizeAndFreeFlag & _FREE_FLAG;
		}

		void SetFree(const bool &is_free)
		{
			m_SizeAndFreeFlag = (m_SizeAndFreeFlag & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
		}

	private:
		Offset m_Offset;
		Size m_SizeAndFreeFlag;

		static const Offset _FREE_FLAG = 0x80000000;
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
