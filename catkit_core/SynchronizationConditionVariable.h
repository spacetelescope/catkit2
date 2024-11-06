#ifndef SYNCHRONIZATION_CONDITION_VARIABLE_H
#define SYNCHRONIZATION_CONDITION_VARIABLE_H

#include "Synchronization.h"

#if defined(__linux__) || defined(__APPLE__)

#include <pthread.h>

struct SharedStateConditionVariable
{
	pthread_cond_t m_Condition;
	pthread_mutex_t m_Mutex;
};

class SynchronizationConditionVariable : public SynchronizationBase<SynchronizationConditionVariable, SharedStateConditionVariable>
{
	friend SynchronizationBase<SynchronizationConditionVariable, SharedStateConditionVariable>;
public:
	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	void Signal();

	void Lock();
	void Unlock();

protected:
	void CreateImpl(const std::string &id, SynchronizationConditionVariable::SharedState *shared_state);
};

#endif // Linux or Apple

#endif // SYNCHRONIZATION_CONDITION_VARIABLE_H
