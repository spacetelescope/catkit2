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
	switch (type)
	{
	case ShareableType::DataStream:
		return DataStream::Open(reinterpret_cast<DataStream::SharedState *>(memory_block));
	case ShareableType::Event:
		return Event::Open(reinterpret_cast<Event::SharedState *>(memory_block));
	case ShareableType::FreeListAllocator:
		return FreeListAllocator::Open(reinterpret_cast<FreeListAllocator::SharedState *>(memory_block));
	case ShareableType::HashMap:
		return HashMap::Open(reinterpret_cast<HashMap::SharedState *>(memory_block));
	case ShareableType::PoolAllocator:
		return PoolAllocator::Open(reinterpret_cast<PoolAllocator::SharedState *>(memory_block));
	case ShareableType::SharedMemory:
		return SharedMemory::Open(reinterpret_cast<SharedMemory::SharedState *>(memory_block));
	default:
		throw std::runtime_error("Unknown shareable type.");
	}
}
