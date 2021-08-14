#include "Property.h"

using namespace std;

Property::~Property()
{
}

void Property::Get(SerializedMessage &value)
{
	throw SerializationError("Property is not readable.");
}

void Property::Set(const SerializedMessage &value)
{
	throw SerializationError("Property is not writable.");
}

PropertyFromFunctions::PropertyFromFunctions(Getter getter, Setter setter)
	: m_Getter(getter), m_Setter(setter)
{
}

void PropertyFromFunctions::Get(SerializedMessage &value)
{
	if (!m_Getter)
		throw SerializationError("Property is not readable.");
	
	m_Getter(value);
}

void PropertyFromFunctions::Set(const SerializedMessage &value)
{
	if (!m_Setter)
		throw SerializationError("Property is not writable.");
	
	if (!value.ContainsValue())
		throw SerializationError("A property setter requires a value.");
	
	m_Setter(value);
}
