#ifndef SYNCHRONZATION_H
#define SYNCHRONZATION_H

#include <atomic>
#include <memory>
#include <string>
#include <functional>

template<typename Derived, typename SharedStateType>
class SynchronizationBase
{
public:
	using SharedState = SharedStateType;

	SynchronizationBase();
	SynchronizationBase(const SynchronizationBase &other) = delete;
	~SynchronizationBase();

	SynchronizationBase<Derived, SharedState> &operator=(const SynchronizationBase<Derived, SharedState> &other) = delete;

	void Initialize(const std::string &id, SharedState *shared_state, bool create);

	void Create(const std::string &id, SharedState *shared_state);

	void Open(const std::string &id, SharedState *shared_state);
	void Close();

	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	void Signal();

	void Lock();
	void Unlock();

protected:
	void CreateImpl(const std::string &id, SharedState *shared_state);

	void OpenImpl(const std::string &id, SharedState *shared_state);
	void CloseImpl();

	bool m_IsOwner;
	bool m_IsOpen;
	SharedState *m_SharedState;
};

template<typename T>
class SynchronizationLock
{
public:
	SynchronizationLock(T &sync);
	~SynchronizationLock();

private:
	T &m_Sync;
};

#include "Synchronization.inl"

#endif // SYNCHRONIZATION_H
