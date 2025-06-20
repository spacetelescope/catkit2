#include "Property.h"

#include <string>

Property::Property(std::string name, std::shared_ptr<DataStream> stream, Getter getter, Setter setter)
	: m_Name(name), m_DataStream(stream), m_Getter(getter), m_Setter(setter)
{
	// Check if data stream has a supported dtype.
	if (stream)
	{
		DataType stream_dtype = stream->GetDataType();

		if (stream_dtype != DataType::DT_INT64 && stream_dtype != DataType::DT_FLOAT64)
			throw std::runtime_error("The data stream has a dtype that is not support by a property.");
	}
}

Value Property::Get()
{
	Value value = m_Getter();

	// Convert the value to a buffer.
	catkit_proto::Value proto_value;
	ToProto(value, proto_value);

	std::string serialized;
	proto_value.SerializeToString(&serialized);

	// Publish the gotten value on the message broker.
	m_Broker->PublishData(m_Prefix + "/"s + m_Name + "/get"s, serialized.data(), serialized.size());

	return value;
}

void Property::Set(const Value &value)
{
	if (!m_Setter)
		throw std::runtime_error("Property is not writable.");

	// Set the property to the casted value.
	m_Setter(value);

	// Update the get channel with the newest data.
	Get();
}

std::string Property::GetName()
{
	return m_Name;
}
