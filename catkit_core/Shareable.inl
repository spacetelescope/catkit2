#include "Shareable.h"

template<enum ShareableType Type>
ShareableImpl<Type>::ShareableImpl(SharedState *shared_state, std::size_t dynamic_shared_state_size)
	: m_SharedState(shared_state),
	m_DynamicSharedStateSize(dynamic_shared_state_size)
{
}

template<enum ShareableType Type>
std::size_t ShareableImpl<Type>::GetSharedStateSize() const
{
	return sizeof(SharedState) + m_DynamicSharedStateSize;
}

template<enum ShareableType Type>
ShareableType ShareableImpl<Type>::GetType() const
{
	return Type;
}
