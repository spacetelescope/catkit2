#include "Shareable.h"

template<enum ShareableType Type>
ShareableImpl<Type>::ShareableImpl(SharedState *shared_state)
	: m_SharedState(shared_state)
{
}

template<enum ShareableType Type>
std::size_t ShareableImpl<Type>::GetSharedStateSize() const
{
	return sizeof(SharedStateType) + sizeof(SharedState);
}

template<enum ShareableType Type>
ShareableType ShareableImpl<Type>::GetType() const
{
	return Type;
}
