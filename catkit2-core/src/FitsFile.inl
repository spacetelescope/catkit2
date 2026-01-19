#include "FitsFile.h"

#include <stdexcept>

template<typename T>
struct type_to_bitpix
{
};

template<>
struct type_to_bitpix<std::uint8_t>
{
	static const int value = TBYTE;
};

template<>
struct type_to_bitpix<std::int8_t>
{
	static const int value = TSBYTE;
};

template<>
struct type_to_bitpix<std::int16_t>
{
	static const int value = TSHORT;
};

template<>
struct type_to_bitpix<std::uint16_t>
{
	static const int value = TUSHORT;
};

template<>
struct type_to_bitpix<std::int32_t>
{
	static const int value = TINT;
};

template<>
struct type_to_bitpix<std::uint32_t>
{
	static const int value = TUINT;
};

template<>
struct type_to_bitpix<std::int64_t>
{
	static const int value = TLONG;
};

template<>
struct type_to_bitpix<std::uint64_t>
{
	static const int value = TULONG;
};

template<>
struct type_to_bitpix<float>
{
	static const int value = TFLOAT;
};

template<>
struct type_to_bitpix<double>
{
	static const int value = TDOUBLE;
};

template<typename T>
std::vector<T> FitsFile::GetData()
{
	int status = 0;
	int anynulls;

	std::vector<T> data;
	data.resize(GetSize());

	// Check data type.
	if (GetDataType() != type_to_bitpix<T>::value)
		throw std::runtime_error("Data type mismatch.");

	if (fits_read_img(m_File, GetDataType(), 1, data.size(), NULL, data.data(), &anynulls, &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to read image.");
	}

	return std::move(data);
}

template<typename T>
std::vector<T> FitsFile::GetDataCasted()
{
	int status = 0;

	std::vector<T> data;
	data.resize(GetSize());

	// Define all possible data types.
	std::vector<uint8_t> byte_data;
	std::vector<int8_t> sbyte_data;
	std::vector<int16_t> short_data;
	std::vector<uint16_t> ushort_data;
	std::vector<int32_t> int_data;
	std::vector<uint32_t> uint_data;
	std::vector<int64_t> long_data;
	std::vector<uint64_t> ulong_data;
	std::vector<float> float_data;
	std::vector<double> double_data;

	switch (GetDataType())
	{
	case TBYTE:
		byte_data = GetData<uint8_t>();
		for (size_t i = 0; i < byte_data.size(); ++i)
			data[i] = static_cast<T>(byte_data[i]);
		break;
	case TSBYTE:
		sbyte_data = GetData<int8_t>();
		for (size_t i = 0; i < sbyte_data.size(); ++i)
			data[i] = static_cast<T>(sbyte_data[i]);
		break;
	case TSHORT:
		short_data = GetData<int16_t>();
		for (size_t i = 0; i < short_data.size(); ++i)
			data[i] = static_cast<T>(short_data[i]);
		break;
	case TUSHORT:
		ushort_data = GetData<uint16_t>();
		for (size_t i = 0; i < ushort_data.size(); ++i)
			data[i] = static_cast<T>(ushort_data[i]);
		break;
	case TLONG:
		long_data = GetData<int64_t>();
		for (size_t i = 0; i < long_data.size(); ++i)
			data[i] = static_cast<T>(long_data[i]);
		break;
	case TULONG:
		ulong_data = GetData<uint64_t>();
		for (size_t i = 0; i < ulong_data.size(); ++i)
			data[i] = static_cast<T>(ulong_data[i]);
		break;
	case TINT:
		int_data = GetData<int32_t>();
		for (size_t i = 0; i < int_data.size(); ++i)
			data[i] = static_cast<T>(int_data[i]);
		break;
	case TUINT:
		uint_data = GetData<uint32_t>();
		for (size_t i = 0; i < uint_data.size(); ++i)
			data[i] = static_cast<T>(uint_data[i]);
		break;
	case TFLOAT:
		float_data = GetData<float>();
		for (size_t i = 0; i < float_data.size(); ++i)
			data[i] = static_cast<T>(float_data[i]);
		break;
	case TDOUBLE:
		double_data = GetData<double>();
		for (size_t i = 0; i < double_data.size(); ++i)
			data[i] = static_cast<T>(double_data[i]);
		break;
	default:
		throw std::runtime_error("Unsupported data type");
	}

	return std::move(data);
}
