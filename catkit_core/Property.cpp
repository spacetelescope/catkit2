#include "Property.h"

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
	if (!m_Getter)
		throw std::runtime_error("Property is not readable.");

	Value value = m_Getter();

	// Submit the gotten value on the stream, if there is one.
	if (m_DataStream)
	{
		std::visit([this](auto &&arg)
		{
			m_DataStream->SubmitData(&arg);
		}, value);
	}

	return value;
}

void Property::Set(const Value &value)
{
	// If this property has a stream, we should check if the data type is compatible.
	if (m_DataStream)
	{
		DataType expected_dtype = m_DataStream->GetDataType();

		switch (expected_dtype)
		{
			case DataType::DT_INT64:
				if (std::holds_alternative<std::int64_t>(value))
					break;
			case DataType::DT_FLOAT64:
				if (std::holds_alternative<double>(value))
					break;

			throw std::runtime_error("The given value has the wrong data type.");

			default:
				// This should never happen.
				throw std::runtime_error("The datastream has a data type that is not supported by a value.");
		}
	}

	if (!m_Setter)
		throw std::runtime_error("Property is not writable.");

	m_Setter(value);

	// Submit the set value to the stream so that others know about it too.
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

std::shared_ptr<DataStream> Property::GetStream()
{
	return m_DataStream;
}
