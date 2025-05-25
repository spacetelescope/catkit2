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
	int status;
	std::vector<T> data;
	data.resize(GetSize());

	// Check data type.
	if (GetDataType() != type_to_bitpix<T>::value)
		throw std::runtime_error("Data type mismatch.");

	if (fits_read_img(m_File, , 1, data.size(), NULL, data.data(), &status))
	{
		fits_report_error(stderr, status);
		throw std::runtime_error("Failed to read image.");
	}

	return std::move(data);
}

template<typename T>
std::vector<T> FitsFile::GetDataCasted()
{
	int status;
	std::vector<T> data;
	data.resize(GetSize());

	switch (GetDataType())
	{
	case TBYTE:
		auto original_data = GetData<uint8_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TSBYTE:
		auto original_data = GetData<int8_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TSHORT:
		auto original_data = GetData<int16_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TUSHORT:
		auto original_data = GetData<uint16_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TLONG:
		auto original_data = GetData<int64_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TULONG:
		auto original_data = GetData<uint64_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TINT:
		auto original_data = GetData<int32_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TUINT:
		auto original_data = GetData<uint32_t>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TFLOAT:
		auto original_data = GetData<float>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	case TDOUBLE:
		auto original_data = GetData<double>();
		for (size_t i = 0; i < original_data.size(); ++i)
			data[i] = static_cast<T>(original_data[i]);
		break;
	default:
		throw std::runtime_error("Unsupported data type");
	}

	return std::move(data);
}
