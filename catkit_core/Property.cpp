#include "Property.h"

Property::Property(std::string name, std::shared_ptr<DataStream> stream, Getter getter, Setter setter)
	: m_Name(name), m_DataStream(stream), m_Getter(getter), m_Setter(setter)
{
}

Value Property::Get()
{
	if (!m_Getter)
		throw std::runtime_error("Property is not readable.");

	return m_Getter();
}

void Property::Set(const Value &value)
{
	// If this property has a stream, we should check if the data type is compatible.


	if (!m_Setter)
		throw std::runtime_error("Property is not writable.");

	m_Setter(value);

	if (m_DataStream)
	{
		std::visit([this](auto &&arg)
		{
			m_DataStream->SubmitData(&arg);
		}, value);
	}
}

std::string Property::GetName()
{
	return m_Name;
}
