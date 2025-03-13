#include "Shareable.h"

#include <stdexcept>

#include "DataStream.h"
#include "Event.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "HashMap.h"

std::unique_ptr<Shareable> Shareable::Open(StructStream &stream)
{
	ShareableType type = *stream.Extract<ShareableType>();

	switch (type)
	{
	case ShareableType::DataStream:
		return DataStream::Open(stream);
	case ShareableType::Event:
		return Event::Open(stream);
	case ShareableType::FreeListAllocator:
		return FreeListAllocator::Open(stream);
	case ShareableType::PoolAllocator:
		return PoolAllocator::Open(stream);
	case ShareableType::SharedMemory:
		return SharedMemory::Open(stream);
	case ShareableType::HashMap:
		return HashMap::Open(stream);
	default:
		throw std::runtime_error("Unknown shareable type.");
	}
}
