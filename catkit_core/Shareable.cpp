#include "Shareable.h"

#include <stdexcept>

#include "DataStream.h"
#include "Event.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "HashMap.h"

std::unique_ptr<Shareable> Shareable::Open(ShareableType type, void *memory_block)
{
	throw std::runtime_error("Unknown shareable type.");
}
