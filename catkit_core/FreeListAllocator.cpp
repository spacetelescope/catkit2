#include "FreeListAllocator.h"
#include "Timing.h"

#include <iostream>
#include <algorithm>

#define DEBUG_PRINT(a) std::cout << a << std::endl
//#define DEBUG_PRINT(a)

const std::size_t MAX_ATTEMPTS = 5;
const std::array<std::uint8_t, 4> VERSION = {0, 0, 0, 0};

FreeListAllocator::BlockDescriptor::BlockDescriptor()
{
}

FreeListAllocator::BlockDescriptor::BlockDescriptor(Offset offset, Size size, bool is_free)
{
	Set(offset, size, is_free);
}

void FreeListAllocator::BlockDescriptor::Set(const Offset &offset, const Size &size, const bool &is_free)
{
	m_Offset = offset;
	m_SizeAndFreeFlag = (size & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
}

FreeListAllocator::Offset FreeListAllocator::BlockDescriptor::GetOffset() const
{
	return m_Offset;
}

void FreeListAllocator::BlockDescriptor::SetOffset(const Offset &new_offset)
{
	m_Offset = new_offset;
}

FreeListAllocator::Size FreeListAllocator::BlockDescriptor::GetSize() const
{
	return m_SizeAndFreeFlag & ~_FREE_FLAG;
}

void FreeListAllocator::BlockDescriptor::SetSize(const Size &new_size)
{
	m_SizeAndFreeFlag = (new_size & ~_FREE_FLAG) | (m_SizeAndFreeFlag & _FREE_FLAG);
}

bool FreeListAllocator::BlockDescriptor::IsFree() const
{
	return m_SizeAndFreeFlag & _FREE_FLAG;
}

void FreeListAllocator::BlockDescriptor::SetFree(const bool &is_free)
{
	m_SizeAndFreeFlag = (m_SizeAndFreeFlag & ~_FREE_FLAG) | (_FREE_FLAG * is_free);
}

FreeListAllocator::MarkedHandle::MarkedHandle()
{
}

FreeListAllocator::MarkedHandle::MarkedHandle(BlockHandle handle)
	: m_HandleAndMark(handle << 1)
{
}

FreeListAllocator::BlockHandle FreeListAllocator::MarkedHandle::GetHandle() const
{
	return m_HandleAndMark >> 1;
}

void FreeListAllocator::MarkedHandle::SetHandle(const BlockHandle &handle)
{
	m_HandleAndMark = (handle << 1) | (m_HandleAndMark & 1);
}

bool FreeListAllocator::MarkedHandle::IsMarked() const
{
	return m_HandleAndMark & 1;
}

void FreeListAllocator::MarkedHandle::Mark()
{
	m_HandleAndMark |= 1;
}

FreeListAllocator::FreeListAllocator(Header *header, std::unique_ptr<PoolAllocator> block_allocator, Block *blocks)
	: m_Header(*header),
	m_BlockAllocator(std::move(block_allocator)),
	m_Blocks(blocks),
	m_MaxNumBlocks(m_Header.max_num_blocks),
	m_Head(m_Header.head),
	m_Alignment(m_Header.alignment)
{
}

std::size_t FreeListAllocator::GetSharedStateSize(std::size_t max_num_blocks)
{
	std::size_t size = sizeof(Header);
	size += PoolAllocator::GetSharedStateSize(max_num_blocks);
	size += sizeof(Block) * max_num_blocks;

	return size;
}

std::unique_ptr<FreeListAllocator> FreeListAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, VERSION);

	Header *header = stream.Extract<Header>();
	auto block_allocator = PoolAllocator::Open(stream);
	auto blocks = stream.Extract<Block>(header->max_num_blocks);

	return std::unique_ptr<FreeListAllocator>(new FreeListAllocator(header, std::move(block_allocator), blocks));
}

std::unique_ptr<FreeListAllocator> FreeListAllocator::Create(StructStream &stream, std::size_t max_num_blocks, std::size_t alignment, std::size_t buffer_size)
{
	// Add padding to ensure consistent alignment from object to object.
	stream.AddPadding<Block>();

	// Set the version.
	*stream.Extract<std::array<std::uint8_t, 4>>() = VERSION;

	// Create all other information.
	Header *header = stream.Extract<Header>();
	auto block_allocator = PoolAllocator::Create(stream, max_num_blocks);
	auto blocks = stream.Extract<Block>(max_num_blocks);

	// Fill in the header information.
	header->max_num_blocks = max_num_blocks;
	header->alignment = alignment;
	header->total_buffer_size = buffer_size;

	// Initialize the free list.
	header->head = block_allocator->Allocate();

	blocks[header->head.load()].descriptor = BlockDescriptor(0, buffer_size, true);
	blocks[header->head.load()].next = INVALID_HANDLE;

	for (size_t i = 0; i < max_num_blocks; ++i)
		blocks[i].ref_count.store(0, std::memory_order_relaxed);

	return std::unique_ptr<FreeListAllocator>(new FreeListAllocator(header, std::move(block_allocator), blocks));
}

FreeListAllocator::BlockHandle FreeListAllocator::Allocate(std::size_t size)
{
	if (size == 0)
		return INVALID_HANDLE;

	// Round up the size to the nearest multiple of the alignment.
	size = (size + m_Alignment - 1) & ~(m_Alignment - 1);

	DEBUG_PRINT("Allocating " << size << " bytes.");

	MarkedHandle prev = INVALID_HANDLE;
	MarkedHandle handle;
	BlockDescriptor descriptor;

	while (true)
	{
		bool successful = false;

		// Try to either remove a free block of the perfect size, or split an existing block.
		while (true)
		{
			// Re-read the handle.
			if (prev.GetHandle() == INVALID_HANDLE)
			{
				handle = m_Head.load(std::memory_order_relaxed);
			}
			else
			{
				handle = m_Blocks[prev.GetHandle()].next.load(std::memory_order_relaxed);
			}

			// Check if we reached the end of the list.
			if (handle.GetHandle() == INVALID_HANDLE)
				break;

			// Ignore blocks marked for removal.
			if (handle.IsMarked())
				break;

			Block &block = m_Blocks[handle.GetHandle()];
			descriptor = block.descriptor.load(std::memory_order_relaxed);

			// Check that the block is free and large enough.
			if (!descriptor.IsFree() || descriptor.GetSize() < size)
				break;

			DEBUG_PRINT("Found a free block of size " << descriptor.GetSize() << " > " << size << ".");

			if (descriptor.GetSize() == size)
			{
				// Block is the perfect size. Remove it from the linked list instead of replacing.
				if (!Remove(handle.GetHandle()))
				{
					DEBUG_PRINT("Failed to remove block from linked list.");
					continue;
				}
			}
			else
			{
				// Block is too large. Replace the block with a new block containing the residual size.
				BlockHandle res = m_BlockAllocator->Allocate();
				if (res == PoolAllocator::INVALID_HANDLE)
					return INVALID_HANDLE;

				BlockDescriptor res_descriptor(descriptor.GetOffset() + size, descriptor.GetSize() - size, true);
				m_Blocks[res].descriptor.store(res_descriptor, std::memory_order_relaxed);

				// Replace the found block with the new one.
				if (!Replace(handle.GetHandle(), res))
				{
					DEBUG_PRINT("Failed to replace block in linked list.");

					m_BlockAllocator->Deallocate(res);
					continue;
				}
			}

			successful = true;
			break;
		}

		if (!successful)
		{
			// Continue with the next block in the linked list.
			prev = handle;
			continue;
		}

		DEBUG_PRINT("Succesfully allocated a piece of memory.");

		m_Blocks[handle.GetHandle()].descriptor.store(BlockDescriptor(descriptor.GetOffset(), size, true));
		m_Blocks[handle.GetHandle()].ref_count.store(1, std::memory_order_relaxed);

		DEBUG_PRINT("Returning new block.");

		return handle.GetHandle();
	}

	return INVALID_HANDLE;
}

void FreeListAllocator::Deallocate(BlockHandle handle)
{
	if (handle == INVALID_HANDLE)
		return;

	size_t old_ref_count = m_Blocks[handle].ref_count.fetch_sub(1, std::memory_order_relaxed);

	if (old_ref_count != 1)
	{
		// The reference count is not yet zero, so do not deallocate.
		return;
	}

	if (old_ref_count == 0)
	{
		// Something went horribly wrong with reference counting. Reset the ref count and raise an exception.
		m_Blocks[handle].ref_count.fetch_add(1, std::memory_order_relaxed);

		throw std::runtime_error("A double-free occurred.");
	}

	DEBUG_PRINT("Deallocating block " << handle);

	// Insert the block back on the free list.
	if (!Insert(handle))
		throw std::runtime_error("The block was already on the free list.");

	DEBUG_PRINT("Deallocated block " << handle);

	// TODO: coalesce all blocks.
}

void FreeListAllocator::IncrementRefCount(BlockHandle index)
{
	if (index == INVALID_HANDLE)
	{
		return;
	}

	if (m_Blocks[index].ref_count.fetch_add(1, std::memory_order_relaxed) == 0)
	{
		// The reference count was 0, so we erroneously increased the ref count and
		// someone else is deallocating the element. Undo the increment and return.
		m_Blocks[index].ref_count.fetch_sub(1, std::memory_order_relaxed);
		return;
	};
}

// Try to coalesce two blocks, one of which is owned by us.
// Return whether the coallescing was successful.
bool FreeListAllocator::TryCoalesceBlocks(BlockHandle a, BlockHandle b, bool owner_of_a)
{
	DEBUG_PRINT("Attempting to coalesce blocks " << a << " and " << b);

	if (a == INVALID_HANDLE || b == INVALID_HANDLE)
		return false;

	BlockDescriptor descriptor_a = m_Blocks[a].descriptor.load();
	BlockDescriptor descriptor_b = m_Blocks[b].descriptor.load();

	// Perform a pre-check on the blocks.
	if (descriptor_a.GetOffset() < descriptor_b.GetOffset())
	{
		if (descriptor_a.GetOffset() + descriptor_a.GetSize() != descriptor_b.GetOffset())
		{
			// The blocks are not adjacent.
			DEBUG_PRINT("The blocks are not adjacent.");
			return false;
		}
	}
	else
	{
		if (descriptor_b.GetOffset() + descriptor_b.GetSize() != descriptor_a.GetOffset())
		{
			// The blocks are not adjacent.
			DEBUG_PRINT("The blocks are not adjacent.");
			return false;
		}
	}

	if (!descriptor_b.IsFree())
	{
		// The B block was not free and as such cannot be coalesced.
		DEBUG_PRINT("The B block was not free.");

		return false;
	}

	// We are in principle good to coallesce the blocks.
	// Start by owning the A block if we don't already.
	if (!owner_of_a)
	{
		BlockDescriptor descriptor_a_old = descriptor_a;
		descriptor_a.SetFree(false);

		// Try to own block A.
		if (!m_Blocks[a].descriptor.compare_exchange_strong(descriptor_a_old, descriptor_a))
		{
			// The block was changed by someone else. We cannot own it.
			DEBUG_PRINT("Starting to own block A failed.");
			return false;
		}
	}

	BlockDescriptor new_descriptor = descriptor_b;

	if (descriptor_a.GetOffset() < descriptor_b.GetOffset())
	{
		// The B block is after the A block.
		new_descriptor.SetOffset(descriptor_a.GetOffset());
		new_descriptor.SetSize(descriptor_a.GetSize() + descriptor_b.GetSize());
	}
	else
	{
		// The B block is before the A block.
		new_descriptor.SetSize(descriptor_a.GetSize() + descriptor_b.GetSize());
	}

	DEBUG_PRINT("Trying to set the new descriptor of the B block, with " << new_descriptor.GetOffset() << " and " << new_descriptor.GetSize());

	// Try to set the new descriptor of the B block.
	if (!m_Blocks[b].descriptor.compare_exchange_weak(descriptor_b, new_descriptor))
	{
		// The B block was changed by someone else. Return the A block to its original state and return.
		// Note: since we're the owner, this cannot fail.
		if (!owner_of_a)
			MarkBlockAsFree(a, true);

		return false;
	}

	DEBUG_PRINT("Succesfully coalesced blocks " << a << " and " << b);

	return true;
}

FreeListAllocator::BlockHandle FreeListAllocator::FindFirstFreeBlock(Size size)
{
	MarkedHandle current = m_Head.load();

	while (current.GetHandle() != INVALID_HANDLE)
	{
	 	Block &block = m_Blocks[current.GetHandle()];

		// Ignore blocks that are marked for removal.
		if (current.IsMarked())
		{
			current = block.next.load();
			continue;
		}

		BlockDescriptor descriptor = block.descriptor.load();

		// Also check the free flag. The block might be on the free list but temporarily reserved.
		if (descriptor.GetSize() >= size && descriptor.IsFree())
		{
			return current.GetHandle();
		}

		current = block.next.load();
	}

	return INVALID_HANDLE;
}

std::size_t FreeListAllocator::GetOffset(BlockHandle index)
{
	return m_Blocks[index].descriptor.load().GetOffset();
}

std::pair<FreeListAllocator::MarkedHandle, FreeListAllocator::MarkedHandle> FreeListAllocator::Search(Offset offset)
{
	DEBUG_PRINT("Searching for offset " << offset);

	while (true)
	{
		MarkedHandle t = INVALID_HANDLE;
		MarkedHandle t_next = m_Head.load();
		MarkedHandle left_node_next;

		MarkedHandle left_node;
		MarkedHandle right_node;

		// Find left_node and right_node;
		do
		{
			if (!t_next.IsMarked())
			{
				left_node = t;
				left_node_next = t_next;
			}

			t = t_next.GetHandle();

			if (t.GetHandle() == INVALID_HANDLE)
				break;

			t_next = m_Blocks[t.GetHandle()].next.load();
		} while (t_next.IsMarked() || (m_Blocks[t.GetHandle()].descriptor.load().GetOffset() < offset));

		right_node = t;

		// Check nodes are adjacent.
		if (left_node_next.GetHandle() == right_node.GetHandle())
		{
			if ((right_node.GetHandle() != INVALID_HANDLE) && (m_Blocks[right_node.GetHandle()].next.load().IsMarked()))
			{
				continue;
			}
			else
			{
				return {left_node, right_node};
			}
		}

		// Remove one or more marked nodes.
		if (left_node.GetHandle() == INVALID_HANDLE)
		{
			DEBUG_PRINT("Removing nodes from head of list. New head is " << right_node.GetHandle() << ".");

			// We are removing nodes from the head of the list.
			BlockHandle expected = left_node_next.GetHandle();
			if (!m_Head.compare_exchange_strong(expected, right_node.GetHandle()))
				continue;
		}
		else
		{
			DEBUG_PRINT("Removing nodes from middle of list. Connecting " << left_node.GetHandle() << " to " << right_node.GetHandle() << ".");

			// We are removing nodes from the middle of the list.
			if (!m_Blocks[left_node.GetHandle()].next.compare_exchange_strong(left_node_next, right_node))
				continue;
		}

		if ((right_node.GetHandle() != INVALID_HANDLE) && (m_Blocks[right_node.GetHandle()].next.load().IsMarked()))
		{
			continue;
		}
		else
		{
			return {left_node, right_node};
		}
	}
}

bool FreeListAllocator::Insert(BlockHandle handle)
{
	DEBUG_PRINT("Inserting block " << handle);

	while (true)
	{
		// Find the previous and next node.
		auto [left_node, right_node] = Search(m_Blocks[handle].descriptor.load().GetOffset());

		DEBUG_PRINT("Left node: " << left_node.GetHandle() << ", right node: " << right_node.GetHandle());

		// If the node was already on the list, we failed.
		if (right_node.GetHandle() == handle)
			return false;

		// Link the next node.
		m_Blocks[handle].next.store(right_node, std::memory_order_relaxed);

		// Insert the new node.
		if (left_node.GetHandle() == INVALID_HANDLE)
		{
			DEBUG_PRINT("Inserting at head");

			// We are inserting at the head.
			BlockHandle expected = right_node.GetHandle();
			if (m_Head.compare_exchange_strong(expected, handle))
				return true;
		}
		else
		{
			DEBUG_PRINT("Inserting in middle");
			// We are inserting in the middle.
			if (m_Blocks[left_node.GetHandle()].next.compare_exchange_strong(right_node, handle))
				return true;
		}
	}
}

bool FreeListAllocator::Replace(BlockHandle old_handle, BlockHandle new_handle)
{
	DEBUG_PRINT("Replacing block " << old_handle << " with " << new_handle);

	while (true)
	{
		// Find the previous and next node.
		auto [left_node, right_node] = Search(m_Blocks[old_handle].descriptor.load().GetOffset());

		DEBUG_PRINT("Left node: " << left_node.GetHandle() << ", right node: " << right_node.GetHandle());

		// If the node was already on the list, we failed.
		if (right_node.GetHandle() != old_handle)
		{
			DEBUG_PRINT("Old block was not on list. Failed.");
			return false;
		}

		// Link the next node.
		MarkedHandle next = m_Blocks[old_handle].next.load(std::memory_order_relaxed);

		if (next.IsMarked())
		{
			DEBUG_PRINT("Next node is marked for removal. Trying again.");
			continue;
		}

		m_Blocks[new_handle].next.store(next, std::memory_order_relaxed);
		DEBUG_PRINT("Block " << new_handle << " is now linked to block " << next.GetHandle());

		MarkedHandle new_next = new_handle;
		new_next.Mark();

		// Link the new node and logically remove the old.
		if (m_Blocks[old_handle].next.compare_exchange_strong(next, new_next))
			break;
	}

	DEBUG_PRINT("Logically replaced block " << old_handle << " with " << new_handle);

	// Physically remove the node.
	Search(m_Blocks[new_handle].descriptor.load().GetOffset());

	DEBUG_PRINT("Physically removed block " << old_handle);

	return true;
}

bool FreeListAllocator::Remove(BlockHandle handle)
{
	DEBUG_PRINT("Removing block " << handle);

	MarkedHandle next = m_Blocks[handle].next.load(std::memory_order_relaxed);

	while (true)
	{
		// If the node is already marked, we failed.
		if (next.IsMarked())
		{
			DEBUG_PRINT("Block " << handle << " is already marked for removal. Failed.");
			return false;
		}

		MarkedHandle next_marked = next;
		next_marked.Mark();

		// Logically remove the node.
		if (m_Blocks[handle].next.compare_exchange_strong(next, next_marked))
			break;

		DEBUG_PRINT("Failed to logically remove block " << handle << ". Trying again.");
	}

	DEBUG_PRINT("Logically removed block " << handle);

	// Physically remove the node.
	Search(m_Blocks[handle].descriptor.load().GetOffset());

	DEBUG_PRINT("Physically removed block " << handle);

	return true;
}

bool FreeListAllocator::MarkBlockAsFree(BlockHandle handle, bool mark_free)
{
	DEBUG_PRINT("Marking block " << handle << " as " << (mark_free ? "free" : "allocated"));

	BlockDescriptor descriptor = m_Blocks[handle].descriptor.load();

	if (descriptor.IsFree() == mark_free)
	{
		// The block is already in the desired state.
		DEBUG_PRINT("The block is already in the desired state.");
		return false;
	}

	BlockDescriptor new_descriptor = descriptor;
	new_descriptor.SetFree(mark_free);

	if (!m_Blocks[handle].descriptor.compare_exchange_strong(descriptor, new_descriptor))
	{
		// The block was changed in the meantime and we were unsuccessful.
		DEBUG_PRINT("The block was changed in the meantime.");
		return false;
	}

	DEBUG_PRINT("Successfully marked the block.");

	return true;
}

void FreeListAllocator::PrintState()
{
	MarkedHandle current = m_Head.load();

	while (current.GetHandle() != INVALID_HANDLE)
	{
		// Ignore blocks that are marked for removal.
		if (current.IsMarked())
			continue;

		Block &block = m_Blocks[current.GetHandle()];
		BlockDescriptor descriptor = block.descriptor.load();

		std::cout << "Free block " << current.GetHandle() << " has (offset, size) = (" << descriptor.GetOffset() << ", " << descriptor.GetSize() << ")." << std::endl;

		current = block.next;
	}
}

size_t FreeListAllocator::GetNumFreeBlocks() const
{
	size_t count = 0;
	MarkedHandle current = m_Head.load();

	while (current.GetHandle() != INVALID_HANDLE)
	{
		// Ignore blocks that are marked for removal.
		if (current.IsMarked())
			continue;

		++count;
		current = m_Blocks[current.GetHandle()].next;
	}

	return count;
}

ShareableType FreeListAllocator::GetType() const
{
	return ShareableType::FreeListAllocator;
}
