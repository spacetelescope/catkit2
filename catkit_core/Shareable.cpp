#include "Shareable.h"

#include <stdexcept>

#include "DataStream.h"
#include "Event.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "LocalMemory.h"
#include "HashMap.h"
#include "MessageBroker.h"
#include "BuddyAllocator.h"
#include "HybridPoolAllocator.h"

std::shared_ptr<Shareable> Shareable::Open(StructStream &stream)
{
	ShareableType type = *stream.Extract<ShareableType>();

	switch (type)
	{
	case ShareableType::DataStream:
		return DataStream::Open(stream);
	case ShareableType::Event:
		return Event::Open(stream);
	case ShareableType::PoolAllocator:
		return PoolAllocator::Open(stream);
	case ShareableType::SharedMemory:
		return SharedMemory::Open(stream);
	case ShareableType::LocalMemory:
		return LocalMemory::Open(stream);
	case ShareableType::HashMap:
		return HashMap::Open(stream);
	case ShareableType::MessageBroker:
		return MessageBroker::Open(stream);
	case ShareableType::BuddyAllocator:
		return BuddyAllocator::Open(stream);
	case ShareableType::HybridPoolAllocator:
		return HybridPoolAllocator::Open(stream);
	default:
		throw std::runtime_error("Unknown shareable type.");
	}
}
