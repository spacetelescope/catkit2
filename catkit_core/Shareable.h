#ifndef SHAREABLE_H
#define SHAREABLE_H

#include "StructStream.h"

#include <cstddef>
#include <memory>
#include <algorithm>

enum class ShareableType
{
	DataStream,
	Event,
	LocalMemory,
	PoolAllocator,
	SharedMemory,
	HashMap,
	MessageBroker,
	BuddyAllocator,
	HybridPoolAllocator
};

/*
 * A base class for all shareable objects.
 *
 * A shareable object is a object that operates on a shared memory block.
 * It can use the shared state to communicate with itself on other processes
 * or other threads. The attributes of a shareable object are stored locally.
 * A shareable object should be able to be opened from its shared state.
 */
class Shareable
{
protected:
	// Constructor. This stores a reference to the memory block,
	// ensuring it stays alive at least until this object gets deallocated.
	Shareable(std::shared_ptr<Memory> memory_block);

public:
	virtual ~Shareable() = default;

	// Disallow copy and move semantics.
	Shareable(const Shareable &) = delete;
	Shareable &operator=(const Shareable &) = delete;
	Shareable(Shareable &&) = delete;
	Shareable &operator=(Shareable &&) = delete;

	static std::shared_ptr<Shareable> Open(StructStream &stream);

	virtual ShareableType GetType() const = 0;

private:
	// The memory object containing our shared state.
	std::shared_ptr<Memory> m_MemoryBlock;
};

template <typename T, std::size_t N>
inline bool CheckVersion(StructStream &stream, const std::array<T, N> expected_version)
{
	// Get the version from the stream;
	T *our_version = stream.Extract<T>(N);

	// Return if the version strings are the same.
	return std::equal(expected_version.begin(), expected_version.end(), our_version);
}

#endif // SHAREABLE_H
