#ifndef FREE_LIST_ALLOCATOR_H
#define FREE_LIST_ALLOCATOR_H

#include "PoolAllocator.h"
#include "Shareable.h"

#include <atomic>
#include <cstdint>
#include <memory>
#include <cstdint>

// A simple lock-free free list allocator.
class FreeListAllocator : public Shareable
{
public:
	using BlockHandle = PoolAllocator::BlockHandle;
	using Offset = std::uint32_t;
	using Size = std::uint32_t;

	static const BlockHandle INVALID_HANDLE = PoolAllocator::INVALID_HANDLE >> 1;

	static std::size_t GetSharedStateSize(std::size_t max_num_blocks);

	static std::unique_ptr<FreeListAllocator> Create(StructStream &stream, std::size_t max_num_blocks, std::size_t alignment, std::size_t buffer_size);
	static std::unique_ptr<FreeListAllocator> Open(StructStream &stream);

	BlockHandle Allocate(std::size_t size);
	void IncrementRefCount(BlockHandle index);
	void Deallocate(BlockHandle index);

	std::size_t GetOffset(BlockHandle index);

	void PrintState();
	size_t GetNumFreeBlocks() const;

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

	class MarkedHandle
	{
	public:
		MarkedHandle();
		MarkedHandle(BlockHandle handle);

		BlockHandle GetHandle() const;
		void SetHandle(const BlockHandle &handle);

		bool IsMarked() const;
		void Mark();

	private:
		BlockHandle m_HandleAndMark;
	};

	// Check that the MarkedHandle is lock-free atomic.
	static_assert(std::atomic<BlockDescriptor>::is_always_lock_free);

	struct Block
	{
		std::atomic<BlockDescriptor> descriptor;
		std::atomic<MarkedHandle> next;
		std::atomic_size_t ref_count;
	};

	struct Header
	{
		std::uint32_t max_num_blocks;
		Size alignment;
		Size total_buffer_size;
		std::atomic<BlockHandle> head;
	};

	// Ensure a specific memory layout.
	static_assert(offsetof(Header, max_num_blocks) == 0);
	static_assert(offsetof(Header, alignment) == 4);
	static_assert(offsetof(Header, total_buffer_size) == 8);
	static_assert(offsetof(Header, head) == 12);
	static_assert(sizeof(Header) == 16);

	ShareableType GetType() const override;

private:
	FreeListAllocator(Header *header, std::unique_ptr<PoolAllocator> block_allocator, Block *blocks);

	Header &m_Header;

	std::uint32_t &m_MaxNumBlocks;
	std::uint32_t &m_Alignment;
	std::atomic<BlockHandle> &m_Head;

	std::unique_ptr<PoolAllocator> m_BlockAllocator;
	Block *m_Blocks;

	BlockHandle FindFirstFreeBlock(Size size);

	void SearchInsertPoint(Offset offset, BlockHandle &left_node_next, BlockHandle &right_node);

	//void InsertBlockSorted(BlockHandle index);
	//bool RemoveBlock(BlockHandle index);

	bool MarkBlockAsFree(BlockHandle index, bool mark_free);

	bool TryCoalesceBlocks(BlockHandle a, BlockHandle b, bool owner_of_a);

	bool CoalesceAll();
	BlockHandle Coalesce(BlockHandle a, BlockHandle b);

	std::pair<MarkedHandle, MarkedHandle> Search(Offset offset);
	bool Insert(BlockHandle block);
	bool Replace(BlockHandle old_block, BlockHandle new_block);
	bool Remove(BlockHandle block);
};

#endif // FREE_LIST_ALLOCATOR_H
