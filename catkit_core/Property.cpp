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
	if (!m_Setter)
		throw std::runtime_error("Property is not writable.");

	if (!m_DataStream)
	{
		// This property has no datastream. Just call the setter and return.
		m_Setter(value);

		return;
	}

	// If this property has a stream, we cast the given value to the right data type.
	Value val;

	DataType stream_dtype = m_DataStream->GetDataType();

	try
	{
		switch (stream_dtype)
		{
			case DataType::DT_INT64:
				val = CastTo<std::int64_t>(value);
				break;

			case DataType::DT_FLOAT64:
				val = CastTo<double>(value);
				break;

			default:
				// This should never happen.
				throw std::runtime_error("The datastream has a data type that is not supported by a value.");
		}
	}
	catch (std::bad_variant_access)
	{
		throw std::runtime_error(std::string("Could not cast the given value to a ") + GetDataTypeAsFullString(stream_dtype));
	}

	// Set the property to the casted value.
	m_Setter(val);

	// Submit the set value to the stream so that others know about it too.
	std::visit([this](auto &&arg)
	{
		m_DataStream->SubmitData(&arg);
	}, val);
}

std::string Property::GetName()
{
	return m_Name;
}

std::shared_ptr<DataStream> Property::GetStream()
{
	return m_DataStream;
}
