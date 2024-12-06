#include "FreeListAllocator.h"
#include "Timing.h"
#include <iostream>

const std::size_t MAX_ATTEMPTS = 5;

template <std::size_t MaxNumBlocks, std::size_t Alignment>
FreeListAllocator<MaxNumBlocks, Alignment>::FreeListAllocator(std::size_t buffer_size)
{
	// Initialize the free list.
	m_Head = m_BlockAllocator.Allocate();

	m_Blocks[m_Head].descriptor = BlockDescriptor(0, buffer_size, true);
	m_Blocks[m_Head].next = -1;
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
FreeListAllocator<MaxNumBlocks, Alignment>::~FreeListAllocator()
{
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
FreeListAllocator<MaxNumBlocks, Alignment>::BlockHandle FreeListAllocator<MaxNumBlocks, Alignment>::Allocate(std::size_t size)
{
	// Round up the size to the nearest multiple of the alignment.
	size = (size + Alignment - 1) & ~(Alignment - 1);

	// std::cout << "Allocating " << size << std::endl;

	for (size_t i = 0; i < MAX_ATTEMPTS; ++i)
	{
		BlockHandle index = FindFirstFreeBlock(size);
		Block &free_block = m_Blocks[index];

		if (index == -1)
		{
			// std::cout << "No free block found." << std::endl;
			return -1;
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
				// std::cout << "Block is too small or not free. Size of block is " << old_descriptor.GetSize() << std::endl;
				break;
			}

			if (old_descriptor.GetSize() == size)
			{
				// The block is exactly the right size.
				// std::cout << "Block is exactly the right size." << std::endl;

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

		// std::cout << "Reduced the size of the free block: " << old_descriptor.GetSize() << ", " << new_descriptor.GetSize() << std::endl;
		// std::cout << "Old descriptor offset: " << old_descriptor.GetOffset() << std::endl;
		// std::cout << "Old descriptor size: " << old_descriptor.GetSize() << std::endl;
		// std::cout << "New size: " << size << std::endl;

		// We now have a block that is large enough to allocate the requested size.
		// Add a new block for the remaining free space.
		BlockHandle allocated_block_handle = m_BlockAllocator.Allocate();
		Block &allocated_block = m_Blocks[allocated_block_handle];

		allocated_block.descriptor = BlockDescriptor(old_descriptor.GetOffset(), size, false);
		allocated_block.next = -1;

		BlockDescriptor descriptor = allocated_block.descriptor.load();

		// std::cout << "Allocated block is " << descriptor.GetOffset() << ", " << descriptor.GetSize() << std::endl;

		// Return the allocated block.
		return allocated_block_handle;
	}

	return -1;
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
void FreeListAllocator<MaxNumBlocks, Alignment>::Deallocate(BlockHandle index)
{
	if (index == -1)
		return;

	// std::cout << "Deallocating block " << index << std::endl;
	Block &block = m_Blocks[index];

	bool owns_index = true;

	// Try to coalesce the block with its neighbors.
	while (true)
	{
		BlockHandle prev = -1;
		BlockHandle next = m_Head.load();

		// std::cout << "Finding the prev and next blocks." << std::endl;

		while (next != -1 && m_Blocks[next].descriptor.load().GetOffset() < block.descriptor.load().GetOffset())
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

			m_BlockAllocator.Deallocate(index);

			index = prev;
			owns_index = false;

			continue;
		}

		if (TryCoalesceBlocks(index, next, owns_index))
		{
			// The coalescense attempt was successful.
			// The next block is no longer valid. Deallocate it.

			RemoveBlock(index);
			m_BlockAllocator.Deallocate(index);

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
template <std::size_t MaxNumBlocks, std::size_t Alignment>
bool FreeListAllocator<MaxNumBlocks, Alignment>::TryCoalesceBlocks(BlockHandle a, BlockHandle b, bool owner_of_a)
{
	// std::cout << "Attempting to coalesce blocks " << a << " and " << b << std::endl;

	if (a == -1 || b == -1)
		return false;

	BlockDescriptor descriptor_a = m_Blocks[a].descriptor.load();
	BlockDescriptor descriptor_b = m_Blocks[b].descriptor.load();

	// Perform a pre-check on the blocks.
	if (descriptor_a.GetOffset() < descriptor_b.GetOffset())
	{
		if (descriptor_a.GetOffset() + descriptor_a.GetSize() != descriptor_b.GetOffset())
		{
			// The blocks are not adjacent.
			// std::cout << "The blocks are not adjacent." << std::endl;
			return false;
		}
	}
	else
	{
		if (descriptor_b.GetOffset() + descriptor_b.GetSize() != descriptor_a.GetOffset())
		{
			// The blocks are not adjacent.
			// std::cout << "The blocks are not adjacent." << std::endl;
			return false;
		}
	}

	if (!descriptor_b.IsFree())
	{
		// The B block was not free and as such cannot be coalesced.
		// std::cout << "The B block was not free." << std::endl;

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
			// std::cout << "Starting to own block A failed." << std::endl;
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

	// std::cout << "Trying to set the new descriptor of the B block, with " << new_descriptor.GetOffset() << " and " << new_descriptor.GetSize() << std::endl;

	// Try to set the new descriptor of the B block.
	if (!m_Blocks[b].descriptor.compare_exchange_weak(descriptor_b, new_descriptor))
	{
		// The B block was changed by someone else. Return the A block to its original state and return.
		// Note: since we're the owner, this cannot fail.
		if (!owner_of_a)
			MarkBlockAsFree(a, true);

		return false;
	}

	// std::cout << "Succesfully coalesced blocks " << a << " and " << b << std::endl;

	return true;
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
FreeListAllocator<MaxNumBlocks, Alignment>::BlockHandle FreeListAllocator<MaxNumBlocks, Alignment>::FindFirstFreeBlock(std::size_t size)
{
	BlockHandle current = m_Head.load();

	while (current != -1)
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

	return -1;
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
std::size_t FreeListAllocator<MaxNumBlocks, Alignment>::GetOffset(BlockHandle index)
{
	return m_Blocks[index].descriptor.load().GetOffset();
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
void FreeListAllocator<MaxNumBlocks, Alignment>::InsertBlockSorted(BlockHandle index)
{
	BlockHandle previous = -1;
	BlockHandle current;

	do
	{
		current = m_Head.load();

		while (current != -1 && m_Blocks[current].descriptor.load().GetOffset() < m_Blocks[index].descriptor.load().GetOffset())
		{
			previous = current;
			current = m_Blocks[current].next;
		}

		if (current == index)
		{
			// The block is already on the free list.
			// std::cout << "Block " << index << " is already on the free list." << std::endl;
			return;
		}

		m_Blocks[index].next = current;

		if (previous == -1)
		{
			// std::cout << "Attempting to insert the block at the head." << std::endl;

			if (m_Head.compare_exchange_weak(current, index))
			{
				// Successfully inserted the block.
				// std::cout << "Successfully inserted the block." << std::endl;
				return;
			}
		}
		else
		{
			// std::cout << "Attempting to insert the block in the middle." << std::endl;

			if (m_Blocks[previous].next.compare_exchange_weak(current, index))
			{
				// Successfully inserted the block.
				// std::cout << "Successfully inserted the block." << std::endl;
				return;
			}
		}
	} while (true);
}

template <std::size_t MaxNumBlocks, std::size_t Alignment>
bool FreeListAllocator<MaxNumBlocks, Alignment>::RemoveBlock(BlockHandle index)
{
	BlockHandle previous = -1;
	BlockHandle current;

	// std::cout << "Removing block " << index << std::endl;

	do
	{
		current = m_Head.load();

		// Find the previous block.
		while (current != index && current != -1)
		{
			previous = current;
			current = m_Blocks[current].next;
		}

		if (current == -1)
		{
			// The block was not on the free list, even though it was supposed to be free.
			// std::cout << "Block was not on the free list." << std::endl;
			return false;
		}

		if (previous == -1)
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

template <std::size_t MaxNumBlocks, std::size_t Alignment>
bool FreeListAllocator<MaxNumBlocks, Alignment>::MarkBlockAsFree(BlockHandle handle, bool mark_free)
{
	// std::cout << "Marking block " << handle << " as " << (mark_free ? "free" : "allocated") << std::endl;

	BlockDescriptor descriptor = m_Blocks[handle].descriptor.load();

	if (descriptor.IsFree() == mark_free)
	{
		// The block is already in the desired state.
		// std::cout << "The block is already in the desired state." << std::endl;
		return false;
	}

	BlockDescriptor new_descriptor = descriptor;
	new_descriptor.SetFree(mark_free);

	if (!m_Blocks[handle].descriptor.compare_exchange_strong(descriptor, new_descriptor))
	{
		// The block was changed in the meantime and we were unsuccessful.
		// std::cout << "The block was changed in the meantime." << std::endl;
		return false;
	}

	// std::cout << "Successfully marked the block." << std::endl;

	return true;
}

template<std::size_t MaxNumBlocks, std::size_t Alignment>
void FreeListAllocator<MaxNumBlocks, Alignment>::PrintState()
{
	BlockHandle current = m_Head;

	while (current != -1)
	{
		Block &block = m_Blocks[current];
		BlockDescriptor descriptor = block.descriptor.load();

		std::cout << "Free block " << current << " has (offset, size) = (" << descriptor.GetOffset() << ", " << descriptor.GetSize() << ")." << std::endl;

		current = block.next;
	}
}

template<std::size_t MaxNumBlocks, std::size_t Alignment>
size_t FreeListAllocator<MaxNumBlocks, Alignment>::GetNumFreeBlocks() const
{
	size_t count = 0;
	BlockHandle current = m_Head;

	while (current != -1)
	{
		++count;
		current = m_Blocks[current].next;
	}

	return count;
}
