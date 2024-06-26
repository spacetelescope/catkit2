#ifndef SYNCHRONZATION_H
#define SYNCHRONZATION_H

#include <atomic>
#include <memory>
#include <string>
#include <functional>

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#define NOMINMAX
	#include <windows.h>
#else
	#include <semaphore.h>
	#include <pthread.h>
#endif // _WIN32

class Synchronization;

struct SynchronizationSharedData
{
#ifdef _WIN32
	std::atomic_long m_NumReadersWaiting;
#else
	pthread_cond_t m_Condition;
	pthread_mutex_t m_Mutex;
#endif
};

class SynchronizationLock
{
public:
	SynchronizationLock(Synchronization *sync);
	~SynchronizationLock();

private:
	Synchronization *m_Sync;
};

class Synchronization
{
public:
	Synchronization();
	Synchronization(const Synchronization &other) = delete;
	~Synchronization();

	Synchronization &operator=(const Synchronization &other) = delete;

	void Initialize(const std::string &id, SynchronizationSharedData *shared_data, bool create);

	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	void Signal();

	void Lock();
	void Unlock();

private:
	void Create(const std::string &id, SynchronizationSharedData *shared_data);
	void Open(const std::string &id, SynchronizationSharedData *shared_data);

	bool m_IsOwner;
	SynchronizationSharedData *m_SharedData;
	std::string m_Id;

#ifdef _WIN32
	HANDLE m_Semaphore;
#endif
};

#endif // SYNCHRONIZATION_H
