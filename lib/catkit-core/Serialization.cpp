#include "Serialization.h"

using namespace std;

SerializedMessage::SerializedMessage()
{
}

SerializedMessage::SerializedMessage(const SerializedMessage &other)
	: data(other.data), binary_data(other.binary_data)
{
}

bool SerializedMessage::ContainsValue() const
{
	return data.count("value");
}

bool SerializedMessage::ContainsArrayValue() const
{
	if (!ContainsValue())
		return false;
	
	if (!data["value"].is_null())
		return false;
	
	if (!data.count("dimensions"))
		return false;

	if (!data["dimensions"].is_array())
		return false;
	
	if (!data.count("data_type"))
		return false;

	if (binary_data.empty())
		return false;
	
	return true;
}

bool SerializedMessage::ContainsNonArrayValue() const
{
	if (!ContainsValue())
		return false;
	
	if (data["value"].is_null())
		return false;
	
	return true;
}

SerializationError::SerializationError(const string &what)
	: runtime_error(what)
{
}

SerializationError::SerializationError(const char *what)
	: runtime_error(what)
{
}