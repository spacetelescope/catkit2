#include <string>

#include "DataStream.h"

template <typename T>
Eigen::Array<typename std::enable_if<is_complex<T>::value, T>::type, Eigen::Dynamic, Eigen::Dynamic> SerializedMessage::GetArray() const
{
	if (!ContainsArrayValue())
		throw SerializationError("The message does not contain an array.");

	auto dimensions = data["dimensions"];
	std::string data_type = data["data_type"];

	if (dimensions.size() == 1)
	{
		if (data_type == "uint8")
			return Eigen::Map<Eigen::Array<std::uint8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint8_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint16")
			return Eigen::Map<Eigen::Array<std::uint16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint16_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint32")
			return Eigen::Map<Eigen::Array<std::uint32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint32_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint64")
			return Eigen::Map<Eigen::Array<std::uint64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint64_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int8")
			return Eigen::Map<Eigen::Array<std::int8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int8_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int16")
			return Eigen::Map<Eigen::Array<std::int16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int16_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int32")
			return Eigen::Map<Eigen::Array<std::int32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int32_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int64")
			return Eigen::Map<Eigen::Array<std::int64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int64_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "float32")
			return Eigen::Map<Eigen::Array<float, Eigen::Dynamic, Eigen::Dynamic>>((float *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "float64")
			return Eigen::Map<Eigen::Array<double, Eigen::Dynamic, Eigen::Dynamic>>((double *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "complex64")
			return Eigen::Map<Eigen::Array<std::complex<float>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<float> *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "complex128")
			return Eigen::Map<Eigen::Array<std::complex<double>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<double> *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
	}
	else if (dimensions.size() == 2)
	{
		if (data_type == "uint8")
			return Eigen::Map<Eigen::Array<std::uint8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint8_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint16")
			return Eigen::Map<Eigen::Array<std::uint16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint16_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint32")
			return Eigen::Map<Eigen::Array<std::uint32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint32_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint64")
			return Eigen::Map<Eigen::Array<std::uint64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint64_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int8")
			return Eigen::Map<Eigen::Array<std::int8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int8_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int16")
			return Eigen::Map<Eigen::Array<std::int16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int16_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int32")
			return Eigen::Map<Eigen::Array<std::int32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int32_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int64")
			return Eigen::Map<Eigen::Array<std::int64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int64_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "float32")
			return Eigen::Map<Eigen::Array<float, Eigen::Dynamic, Eigen::Dynamic>>((float *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "float64")
			return Eigen::Map<Eigen::Array<double, Eigen::Dynamic, Eigen::Dynamic>>((double *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "complex64")
			return Eigen::Map<Eigen::Array<std::complex<float>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<float> *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "complex128")
			return Eigen::Map<Eigen::Array<std::complex<double>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<double> *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
	}
}

template <typename T>
Eigen::Array<typename std::enable_if<!is_complex<T>::value, T>::type, Eigen::Dynamic, Eigen::Dynamic> SerializedMessage::GetArray() const
{
	if (!ContainsArrayValue())
		throw SerializationError("The message does not contain an array.");

	auto dimensions = data["dimensions"];
	std::string data_type = data["data_type"];

	if (dimensions.size() == 1)
	{
		if (data_type == "uint8")
			return Eigen::Map<Eigen::Array<std::uint8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint8_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint16")
			return Eigen::Map<Eigen::Array<std::uint16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint16_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint32")
			return Eigen::Map<Eigen::Array<std::uint32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint32_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "uint64")
			return Eigen::Map<Eigen::Array<std::uint64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint64_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int8")
			return Eigen::Map<Eigen::Array<std::int8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int8_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int16")
			return Eigen::Map<Eigen::Array<std::int16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int16_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int32")
			return Eigen::Map<Eigen::Array<std::int32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int32_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "int64")
			return Eigen::Map<Eigen::Array<std::int64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int64_t *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "float32")
			return Eigen::Map<Eigen::Array<float, Eigen::Dynamic, Eigen::Dynamic>>((float *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "float64")
			return Eigen::Map<Eigen::Array<double, Eigen::Dynamic, Eigen::Dynamic>>((double *) binary_data.data(), dimensions[0].get<size_t>(), 1).cast<T>();
		else if (data_type == "complex64")
			return Eigen::Map<Eigen::Array<std::complex<float>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<float> *) binary_data.data(), dimensions[0].get<size_t>(), 1).real().cast<T>();
		else if (data_type == "complex128")
			return Eigen::Map<Eigen::Array<std::complex<double>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<double> *) binary_data.data(), dimensions[0].get<size_t>(), 1).real().cast<T>();
	}
	else if (dimensions.size() == 2)
	{
		if (data_type == "uint8")
			return Eigen::Map<Eigen::Array<std::uint8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint8_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint16")
			return Eigen::Map<Eigen::Array<std::uint16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint16_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint32")
			return Eigen::Map<Eigen::Array<std::uint32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint32_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "uint64")
			return Eigen::Map<Eigen::Array<std::uint64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::uint64_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int8")
			return Eigen::Map<Eigen::Array<std::int8_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int8_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int16")
			return Eigen::Map<Eigen::Array<std::int16_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int16_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int32")
			return Eigen::Map<Eigen::Array<std::int32_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int32_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "int64")
			return Eigen::Map<Eigen::Array<std::int64_t, Eigen::Dynamic, Eigen::Dynamic>>((std::int64_t *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "float32")
			return Eigen::Map<Eigen::Array<float, Eigen::Dynamic, Eigen::Dynamic>>((float *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "float64")
			return Eigen::Map<Eigen::Array<double, Eigen::Dynamic, Eigen::Dynamic>>((double *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).cast<T>();
		else if (data_type == "complex64")
			return Eigen::Map<Eigen::Array<std::complex<float>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<float> *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).real().cast<T>();
		else if (data_type == "complex128")
			return Eigen::Map<Eigen::Array<std::complex<double>, Eigen::Dynamic, Eigen::Dynamic>>((std::complex<double> *) binary_data.data(), dimensions[0].get<size_t>(), dimensions[1].get<size_t>()).real().cast<T>();
	}
}

template <typename Derived>
void SerializedMessage::SetArray(const Eigen::DenseBase<Derived> &array)
{
	using T = typename Eigen::DenseBase<Derived>::Scalar;

	// Set descriptive info
	if (array.cols() == 1)
		data["dimensions"] = {array.rows()};
	else
		data["dimensions"] = {array.rows(), array.cols()};

	data["data_type"] = GetDataTypeAsString<T>();
	data["value"] = nlohmann::json::object();

	// Resize binary data
	size_t num_bytes = sizeof(T) * array.size();
	binary_data.resize(num_bytes);

	// Copy raw array data into binary_data
	Eigen::Map<Eigen::Array<T, Eigen::Dynamic, Eigen::Dynamic>> map((T *)binary_data.data(), array.rows(), array.cols());
	map = array;
}