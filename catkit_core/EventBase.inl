#include "EventBase.h"

template<enum EventImplementationType Type>
EventImpl<Type>::EventImpl()
	: m_IsOwner(false), m_SharedState(nullptr)
{
}

template<enum EventImplementationType Type>
EventImpl<Type>::~EventImpl()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
	throw std::runtime_error("This type of event implementation wasn't implemented.");
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Signal()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Lock()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Unlock()
{
}

template<enum EventImplementationType Type>
std::unique_ptr<EventImpl<Type>> EventImpl<Type>::Create(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");

	auto obj = std::unique_ptr<EventImpl<Type>>(new EventImpl<Type>());

	obj->CreateImpl(id, shared_state);

	obj->m_IsOwner = true;
	obj->m_SharedState = shared_state;

	return obj;
}

template<enum EventImplementationType Type>
std::unique_ptr<EventImpl<Type>> EventImpl<Type>::Open(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");

	auto obj = std::unique_ptr<EventImpl<Type>>(new EventImpl<Type>());

	obj->OpenImpl(id, shared_state);

	obj->m_IsOwner = false;
	obj->m_SharedState = shared_state;

	return obj;
}

template<enum EventImplementationType Type>
void EventImpl<Type>::CreateImpl(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	// Do nothing.
}

template<enum EventImplementationType Type>
void EventImpl<Type>::OpenImpl(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	// Do nothing.
}