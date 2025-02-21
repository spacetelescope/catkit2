#include "Shareable.h"

#include <stdexcept>

#include "DataStream.h"
#include "Event.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"

std::unique_ptr<Shareable> Shareable::Open(void *memory_block)
{
	auto type = *reinterpret_cast<ShareableType *>(memory_block);
	auto ptr = (char *) memory_block + sizeof(ShareableType);

	switch (type)
	{
	case ShareableType::DataStream:
		return DataStream::Open(reinterpret_cast<DataStream::SharedState *>(ptr));
	case ShareableType::Event:
		return Event::Open(reinterpret_cast<Event::SharedState *>(ptr));
	/*case ShareableType::FreeListAllocator:
		return FreeListAllocator::Open(reinterpret_cast<FreeListAllocator::SharedState *>(ptr));
	case ShareableType::LocalMemory:
		return LocalMemory::Open(reinterpret_cast<LocalMemory::SharedState *>(ptr));
	case ShareableType::PoolAllocator:
		return PoolAllocator::Open(reinterpret_cast<PoolAllocator::SharedState *>(ptr));*/
	case ShareableType::SharedMemory:
		return SharedMemory::Open(reinterpret_cast<SharedMemory::SharedState *>(ptr));
	default:
		throw std::runtime_error("Unknown shareable type.");
	}
}
