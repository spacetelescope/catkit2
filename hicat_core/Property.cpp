#include "Property.h"

using json = nlohmann::json;

Property::Property(std::string name, Getter getter, Setter setter)
	: m_Name(name), m_Getter(getter), m_Setter(setter)
{
}

json Property::Get()
{
	if (!m_Getter)
		throw std::runtime_error("Property is not readable.");

	return m_Getter();
}

void Property::Set(const json &value)
{
	if (!m_Setter)
		throw std::runtime_error("Property is not writable.");

	m_Setter(value);
}

std::string Property::GetName()
{
	return m_Name;
}
