#include "Property.h"

Property::Property(std::string name, Getter getter, Setter setter)
	: m_Name(name), m_Getter(getter), m_Setter(setter)
{
}

Property::~Property()
{
}

std::string Property::GetName()
{
	return m_Name;
}

void Property::Get(SerializedMessage &value)
{
	if (!m_Getter)
		throw SerializationError("Property is not readable.");

	m_Getter(value);
}

void Property::Set(const SerializedMessage &value)
{
	if (!m_Setter)
		throw SerializationError("Property is not writable.");

	if (!value.ContainsValue())
		throw SerializationError("A property setter requires a value.");

	m_Setter(value);
}
