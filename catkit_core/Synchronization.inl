#include "Synchronization.h"

#include <stdexcept>
#include <algorithm>

template<typename T>
SynchronizationLock<T>::SynchronizationLock(T &sync)
	: m_Sync(sync)
{
	m_Sync.Lock();
}

template<typename T>
SynchronizationLock<T>::~SynchronizationLock()
{
	m_Sync.Unlock();
}

template<typename Derived, typename SharedState>
SynchronizationBase<Derived, SharedState>::SynchronizationBase()
	: m_IsOwner(false), m_SharedState(nullptr), m_IsOpen(false)
{
}

template<typename Derived, typename SharedState>
SynchronizationBase<Derived, SharedState>::~SynchronizationBase()
{
	Close();
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Initialize(const std::string &id, SharedState *shared_state, bool create)
{
	if (create)
	{
		Create(id, shared_state);
	}
	else
	{
		Open(id, shared_state);
	}
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Create(const std::string &id, SharedState *shared_state)
{
	if (m_IsOpen)
		throw std::runtime_error("Create called on an already initialized Synchronization object.");

	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");

	static_cast<Derived *>(this)->CreateImpl(id, shared_state);

	m_IsOpen = true;
	m_IsOwner = true;

	m_SharedState = shared_state;
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Open(const std::string &id, SharedState *shared_state)
{
	if (m_IsOpen)
		throw std::runtime_error("Open called on an already initialized Synchronization object.");

	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");


	static_cast<Derived *>(this)->CreateImpl(id, shared_state);

	m_IsOpen = true;
	m_IsOwner = false;

	m_SharedState = shared_state;
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Close()
{
	if (!m_IsOpen)
		return;

	static_cast<Derived *>(this)->CloseImpl();

	m_IsOpen = false;
	m_SharedState = nullptr;
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Signal()
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Lock()
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::Unlock()
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::CreateImpl(const std::string &id, SharedState *shared_state)
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::OpenImpl(const std::string &id, SharedState *shared_state)
{
}

template<typename Derived, typename SharedState>
void SynchronizationBase<Derived, SharedState>::CloseImpl()
{
}
