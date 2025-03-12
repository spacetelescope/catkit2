#include "FreeListAllocator.h"
#include "Timing.h"

#include <iostream>
#include <algorithm>

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

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

FreeListAllocator::FreeListAllocator(Header *header, std::unique_ptr<PoolAllocator> block_allocator, Block *blocks)
	: m_Header(*header),
	m_BlockAllocator(std::move(block_allocator)),
	m_Blocks(blocks),
	m_MaxNumBlocks(m_Header.max_num_blocks),
	m_Head(m_Header.head),
	m_Alignment(m_Header.alignment)
{
}

std::size_t FreeListAllocator::GetMemorySize(std::size_t max_num_blocks)
{
	std::size_t size = sizeof(Header);
	size += PoolAllocator::GetMemorySize(max_num_blocks);
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

	blocks[header->head].descriptor = BlockDescriptor(0, buffer_size, true);
	blocks[header->head].next = INVALID_HANDLE;

	return std::unique_ptr<FreeListAllocator>(new FreeListAllocator(header, std::move(block_allocator), blocks));
}

typename FreeListAllocator::BlockHandle FreeListAllocator::Allocate(std::size_t size)
{
	// Round up the size to the nearest multiple of the alignment.
	size = (size + m_Alignment - 1) & ~(m_Alignment - 1);

	DEBUG_PRINT("Allocating " << size);

	for (size_t i = 0; i < MAX_ATTEMPTS; ++i)
	{
		BlockHandle index = FindFirstFreeBlock(size);
		Block &free_block = m_Blocks[index];

		if (index == INVALID_HANDLE)
		{
			DEBUG_PRINT("No free block found.");
			return INVALID_HANDLE;
		}

		BlockDescriptor old_descriptor;
		BlockDescriptor new_descriptor;

		// Reduce the size of the free block.
		do
		{
			old_descriptor = free_block.descriptor.load();

			// If the block is too small or not free, we need to try again.
			if (old_descriptor.GetSize() < size || !old_descriptor.IsFree())
			{
				// Break out of the nested loop and try again.
				DEBUG_PRINT("Block is too small or not free. Size of block is " << old_descriptor.GetSize());
				break;
			}

			if (old_descriptor.GetSize() == size)
			{
				// The block is exactly the right size.
				DEBUG_PRINT("Block is exactly the right size.");

				// Mark the block as allocated.
				if (MarkBlockAsFree(index, false))
				{
					// Remove the block from the free list.
					// This is guaranteed to succeed since we own the block.
					RemoveBlock(index);

					// Return the block.
					return index;
				}
				else
				{
					// Try again.
					continue;
				}
			}

			// Reduce the size of the block by the requested size.
			new_descriptor = old_descriptor;
			new_descriptor.SetSize(old_descriptor.GetSize() - size);
			new_descriptor.SetOffset(old_descriptor.GetOffset() + size);
		} while (!free_block.descriptor.compare_exchange_weak(old_descriptor, new_descriptor));

		if (old_descriptor.GetSize() < size || !old_descriptor.IsFree())
		{
			// Try again.
			continue;
		}

		DEBUG_PRINT("Reduced the size of the free block: " << old_descriptor.GetSize() << ", " << new_descriptor.GetSize());
		DEBUG_PRINT("Old descriptor offset: " << old_descriptor.GetOffset());
		DEBUG_PRINT("Old descriptor size: " << old_descriptor.GetSize());
		DEBUG_PRINT("New size: " << size);

		// We now have a block that is large enough to allocate the requested size.
		// Add a new block for the remaining free space.
		PoolAllocator::BlockHandle allocated_block_handle = m_BlockAllocator->Allocate();
		DEBUG_PRINT("Allocated block handle is " << allocated_block_handle);

		Block &allocated_block = m_Blocks[allocated_block_handle];

		allocated_block.descriptor = BlockDescriptor(old_descriptor.GetOffset(), size, false);
		allocated_block.next = INVALID_HANDLE;

		DEBUG_PRINT("Done setting the descriptor.");

		BlockDescriptor descriptor = allocated_block.descriptor.load();

		DEBUG_PRINT("Allocated block is " << descriptor.GetOffset() << ", " << descriptor.GetSize());

		// Return the allocated block.
		return allocated_block_handle;
	}

	return INVALID_HANDLE;
}

void FreeListAllocator::Deallocate(BlockHandle index)
{
	if (index == INVALID_HANDLE)
		return;

	DEBUG_PRINT("Deallocating block " << index);
	Block &block = m_Blocks[index];

	bool owns_index = true;

	// Try to coalesce the block with its neighbors.
	while (true)
	{
		BlockHandle prev = INVALID_HANDLE;
		BlockHandle next = m_Head.load();

		DEBUG_PRINT("Finding the prev and next blocks.");

		while (next != INVALID_HANDLE && m_Blocks[next].descriptor.load().GetOffset() < block.descriptor.load().GetOffset())
		{
			prev = next;
			next = m_Blocks[next].next.load();
		}

		// Prev and next are the blocks that are adjacent to the block we are deallocating.
		// Try to coalesce the block with its neighbors.

		if (TryCoalesceBlocks(index, prev, owns_index))
		{
			// The coalescense attempt was successful.
			// The index block is no longer valid. Deallocate it and set the prev block to us.

			if (!owns_index)
				RemoveBlock(index);

			m_BlockAllocator->Deallocate(index);

			index = prev;
			owns_index = false;

			continue;
		}

		if (TryCoalesceBlocks(index, next, owns_index))
		{
			// The coalescense attempt was successful.
			// The next block is no longer valid. Deallocate it.

			RemoveBlock(index);
			m_BlockAllocator->Deallocate(index);

			index = next;
			owns_index = false;

			continue;
		}

		break;
	}

	// If we didn't coalesce the block with its neighbors, add it to the free list.
	if (owns_index)
	{
		InsertBlockSorted(index);
		MarkBlockAsFree(index, true);
	}
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
	BlockHandle current = m_Head.load();

	while (current != INVALID_HANDLE)
	{
		Block &block = m_Blocks[current];
		BlockDescriptor descriptor = block.descriptor.load();

		// Also check the free flag. The block might be on the free list but temporarily reserved.
		if (descriptor.GetSize() >= size && descriptor.IsFree())
		{
			return current;
		}

		current = block.next.load();
	}

	return INVALID_HANDLE;
}

std::size_t FreeListAllocator::GetOffset(BlockHandle index)
{
	return m_Blocks[index].descriptor.load().GetOffset();
}

void FreeListAllocator::InsertBlockSorted(BlockHandle index)
{
	BlockHandle previous = INVALID_HANDLE;
	BlockHandle current;

	do
	{
		current = m_Head.load();

		while (current != INVALID_HANDLE && m_Blocks[current].descriptor.load().GetOffset() < m_Blocks[index].descriptor.load().GetOffset())
		{
			previous = current;
			current = m_Blocks[current].next;
		}

		if (current == index)
		{
			// The block is already on the free list.
			DEBUG_PRINT("Block " << index << " is already on the free list.");
			return;
		}

		m_Blocks[index].next = current;

		if (previous == INVALID_HANDLE)
		{
			DEBUG_PRINT("Attempting to insert the block at the head.");

			if (m_Head.compare_exchange_weak(current, index))
			{
				// Successfully inserted the block.
				DEBUG_PRINT("Successfully inserted the block.");
				return;
			}
		}
		else
		{
			DEBUG_PRINT("Attempting to insert the block in the middle.");

			if (m_Blocks[previous].next.compare_exchange_weak(current, index))
			{
				// Successfully inserted the block.
				DEBUG_PRINT("Successfully inserted the block.");
				return;
			}
		}
	} while (true);
}

bool FreeListAllocator::RemoveBlock(BlockHandle index)
{
	BlockHandle previous = INVALID_HANDLE;
	BlockHandle current;

	DEBUG_PRINT("Removing block " << index);

	do
	{
		current = m_Head.load();

		// Find the previous block.
		while (current != index && current != INVALID_HANDLE)
		{
			previous = current;
			current = m_Blocks[current].next;
		}

		if (current == INVALID_HANDLE)
		{
			// The block was not on the free list, even though it was supposed to be free.
			DEBUG_PRINT("Block was not on the free list.");
			return false;
		}

		if (previous == INVALID_HANDLE)
		{
			if (m_Head.compare_exchange_weak(current, m_Blocks[index].next))
			{
				// Successfully removed the block.
				return true;
			}
		}
		else
		{
			if (m_Blocks[previous].next.compare_exchange_weak(current, m_Blocks[index].next))
			{
				// Successfully removed the block.
				return true;
			}
		}
	} while (true);
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
	BlockHandle current = m_Head;

	while (current != INVALID_HANDLE)
	{
		Block &block = m_Blocks[current];
		BlockDescriptor descriptor = block.descriptor.load();

		std::cout << "Free block " << current << " has (offset, size) = (" << descriptor.GetOffset() << ", " << descriptor.GetSize() << ")." << std::endl;

		current = block.next;
	}
}

size_t FreeListAllocator::GetNumFreeBlocks() const
{
	size_t count = 0;
	BlockHandle current = m_Head;

	while (current != INVALID_HANDLE)
	{
		++count;
		current = m_Blocks[current].next;
	}

	return count;
}
