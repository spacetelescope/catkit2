#ifndef SHAREABLE_H
#define SHAREABLE_H

#include <cstddef>
#include <memory>

enum class ShareableType
{
	DataStream,
	EventSemaphore,
	EventConditionVariable,
	FreeListAllocator,
	LocalMemory,
	PoolAllocator,
	SharedMemory
};

template<enum ShareableType Type>
struct SharedState
{
};

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

	static std::unique_ptr<Shareable> Open(void *memory_block);

	virtual std::size_t GetSharedStateSize() const = 0;
	virtual ShareableType GetType() const = 0;

private:
	template <typename Derived>
	static std::unique_ptr<Derived> Open(typename Derived::SharedState *shared_state);
};

template<enum ShareableType Type>
class ShareableImpl : public Shareable
{
public:
	using SharedState = SharedState<Type>;

protected:
	ShareableImpl(SharedState *shared_state);

public:
	std::size_t GetSharedStateSize() const override;

	ShareableType GetType() const override;

protected:
	SharedState *m_SharedState;
};

#include "Shareable.inl"

#endif // SHAREABLE_H
