#ifndef SHAREABLE_H
#define SHAREABLE_H

#include <cstddef>
#include <memory>

enum class ShareableType
{
	DataStream,
	Event,
	FreeListAllocator,
	LocalMemory,
	PoolAllocator,
	SharedMemory,
	HashMap
};

template<enum ShareableType Type>
struct SharedStateInternal
{
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
	Shareable() = default;

public:
	virtual ~Shareable() = default;

	// Disallow copy and move semantics.
	Shareable(const Shareable &) = delete;
	Shareable &operator=(const Shareable &) = delete;
	Shareable(Shareable &&) = delete;
	Shareable &operator=(Shareable &&) = delete;

	static std::unique_ptr<Shareable> Open(ShareableType type, void *memory_block);

	virtual std::size_t GetSharedStateSize() const = 0;
	virtual ShareableType GetType() const = 0;
};

template<enum ShareableType Type>
class ShareableImpl : public Shareable
{
public:
	using SharedState = SharedStateInternal<Type>;

protected:
	ShareableImpl(SharedState *shared_state, std::size_t dynamic_shared_state_size = 0);

public:
	std::size_t GetSharedStateSize() const override;
	ShareableType GetType() const override;

protected:
	SharedState *m_SharedState;
	std::size_t m_DynamicSharedStateSize;
};

#include "Shareable.inl"

#endif // SHAREABLE_H
