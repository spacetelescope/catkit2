#include "Shareable.h"

#include <stdexcept>

#include "DataStream.h"
#include "EventConditionVariable.h"
#include "EventSemaphore.h"
#include "FreeListAllocator.h"
#include "LocalMemory.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"

std::unique_ptr<Shareable> Open(void *memory_block)
{
	auto type = *reinterpret_cast<ShareableType *>(memory_block);
	auto ptr = memory_block + sizeof(ShareableType);

	switch (type)
	{
	case ShareableType::DataStream:
		return DataStream::Open(reinterpret_cast<DataStream::SharedState *>(ptr));
	case ShareableType::EventConditionVariable:
		return EventConditionVariable::Open(reinterpret_cast<EventConditionVariable::SharedState *>(ptr));
	case ShareableType::EventSemaphore:
		return EventSemaphore::Open(reinterpret_cast<EventSemaphore::SharedState *>(ptr));
	case ShareableType::FreeListAllocator:
		return FreeListAllocator::Open(reinterpret_cast<FreeListAllocator::SharedState *>(ptr));
	case ShareableType::LocalMemory:
		return LocalMemory::Open(reinterpret_cast<LocalMemory::SharedState *>(ptr));
	case ShareableType::PoolAllocator:
		return PoolAllocator::Open(reinterpret_cast<PoolAllocator::SharedState *>(ptr));
	case ShareableType::SharedMemory:
		return SharedMemory::Open(reinterpret_cast<SharedMemory::SharedState *>(ptr));
	default:
		throw std::runtime_error("Unknown shareable type.");
	}
}
