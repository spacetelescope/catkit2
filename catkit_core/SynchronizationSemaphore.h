#ifndef SYNCHRONIZATION_SEMAPHORE_H
#define SYNCHRONIZATION_SEMAPHORE_H

#include "Synchronization.h"

#include <atomic>

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#define NOMINMAX
	#include <windows.h>
#endif

#ifdef _WIN32
struct SharedStateSemaphore
{
	std::atomic_long m_NumReadersWaiting;
};

class SynchronizationSemaphore : public SynchronizationBase<SynchronizationSemaphore, SharedStateSemaphore>
{
public:
	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	void Signal();

	void Lock();
	void Unlock();

protected:
	void CreateImpl(const std::string &id, SharedState *shared_state);
	void OpenImpl(const std::string &id, SharedState *shared_state);

	HANDLE m_Semaphore;
};
#endif // _WIN32

#ifdef __linux__
#endif // __linux__

#ifdef __APPLE__
#endif // __APPLE__

# endif // SYNCHRONIZATION_SEMAPHORE_H
