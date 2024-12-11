#ifndef FREE_LIST_ALLOCATOR_H
#define FREE_LIST_ALLOCATOR_H

#include "PoolAllocator.h"

#include <atomic>
#include <cstdint>

// A simple lock-free free list allocator.
class FreeListAllocator
{
public:
	using BlockHandle = PoolAllocator::BlockHandle;
	using Offset = std::uint32_t;
	using Size = std::uint32_t;

	static const BlockHandle INVALID_HANDLE = PoolAllocator::INVALID_HANDLE;

	FreeListAllocator(void *metadata_buffer);

	static std::size_t ComputeMetadataBufferSize(std::size_t max_num_blocks);

	void Initialize(std::size_t max_num_blocks, std::size_t alignment, std::size_t buffer_size);

	BlockHandle Allocate(std::size_t size);
	void Deallocate(BlockHandle index);

	std::size_t GetOffset(BlockHandle index);

	void PrintState();
	size_t GetNumFreeBlocks() const;

private:
	// A unique descriptor of the block.
	class BlockDescriptor
	{
	public:
		BlockDescriptor();
		BlockDescriptor(Offset offset, Size size, bool is_free);

		void Set(const Offset &offset, const Size &size, const bool &is_free);

		Offset GetOffset() const;
		void SetOffset(const Offset &new_offset);

		Size GetSize() const;
		void SetSize(const Size &new_size);

		bool IsFree() const;
		void SetFree(const bool &is_free);

	private:
		Offset m_Offset;
		Size m_SizeAndFreeFlag;

		static constexpr Offset _FREE_FLAG = Offset(1) << 31;
	};

	// Check that the BlockDescriptor is lock-free atomic.
	static_assert(std::atomic<BlockDescriptor>::is_always_lock_free);

	struct Block
	{
		std::atomic<BlockDescriptor> descriptor;
		std::atomic<BlockHandle> next;
	};

	struct Header
	{
		std::uint8_t version[4];
		std::uint32_t max_num_blocks;
		Size alignment;
		Size total_buffer_size;
		std::atomic<BlockHandle> head;
	};

	// Ensure a specific memory layout.
	static_assert(offsetof(Header, version) == 0);
	static_assert(offsetof(Header, max_num_blocks) == 4);
	static_assert(offsetof(Header, alignment) == 8);
	static_assert(offsetof(Header, total_buffer_size) == 12);
	static_assert(offsetof(Header, head) == 16);
	static_assert(sizeof(Header) == 20);

	Header &m_Header;

	std::uint32_t &m_MaxNumBlocks;
	std::uint32_t &m_Alignment;
	std::atomic<BlockHandle> &m_Head;

	PoolAllocator m_BlockAllocator;
	Block *m_Blocks;

	void *m_MetadataBuffer;

	BlockHandle FindFirstFreeBlock(Size size);

	void InsertBlockSorted(BlockHandle index);
	bool RemoveBlock(BlockHandle index);

	bool MarkBlockAsFree(BlockHandle index, bool mark_free);

	bool TryCoalesceBlocks(BlockHandle a, BlockHandle b, bool owner_of_a);
};

#endif // FREE_LIST_ALLOCATOR_H
