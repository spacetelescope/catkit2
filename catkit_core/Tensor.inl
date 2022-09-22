#include "Log.h"

#include <type_traits>

template<typename T>
constexpr DataType GetDataType()
{
    if (std::is_integral<T>())
    {
        if (sizeof(T) == 1)
        {
            if (std::is_signed<T>())
                return DataType::DT_INT8;
            else
                return DataType::DT_UINT8;
        }

        if (sizeof(T) == 2)
        {
            if (std::is_signed<T>())
                return DataType::DT_INT16;
            else
                return DataType::DT_UINT16;
        }

        if (sizeof(T) == 4)
        {
            if (std::is_signed<T>())
                return DataType::DT_INT32;
            else
                return DataType::DT_UINT32;
        }

        if (sizeof(T) == 8)
        {
            if (std::is_signed<T>())
                return DataType::DT_INT64;
            else
                return DataType::DT_UINT64;
        }
    }

    if (std::is_floating_point<T>())
    {
        if (sizeof(T) == 4)
            return DataType::DT_FLOAT32;
        if (sizeof(T) == 8)
            return DataType::DT_FLOAT64;
    }

    return DataType::DT_UNKNOWN;
}

template<>
constexpr DataType GetDataType<std::complex<float>>()
{
    return DataType::DT_COMPLEX64;
}

template<>
constexpr DataType GetDataType<std::complex<double>>()
{
    return DataType::DT_COMPLEX128;
}

template<typename T>
constexpr const char *GetDataTypeAsString()
{
    if (std::is_integral<T>())
    {
        if (sizeof(T) == 1)
        {
            if (std::is_signed<T>())
                return "int8";
            else
                return "uint8";
        }

        if (sizeof(T) == 2)
        {
            if (std::is_signed<T>())
                return "int16";
            else
                return "uint16";
        }

        if (sizeof(T) == 4)
        {
            if (std::is_signed<T>())
                return "int32";
            else
                return "uint32";
        }

        if (sizeof(T) == 8)
        {
            if (std::is_signed<T>())
                return "int64";
            else
                return "uint64";
        }
    }

    if (std::is_floating_point<T>())
    {
        if (sizeof(T) == 4)
            return "float32";
        if (sizeof(T) == 8)
            return "float64";
    }

    return "unknown";
}

template<>
constexpr const char *GetDataTypeAsString<std::complex<float>>()
{
    return "complex64";
}

template<>
constexpr const char *GetDataTypeAsString<std::complex<double>>()
{
    return "complex128";
}

template<typename EigenType>
void Tensor::CopyInto(EigenType &out)
{
	using T = typename EigenType::Scalar;

	switch (m_DataType)
	{
		case DataType::DT_UINT8:
			out = AsArray<std::uint8_t, T>();
			break;
		case DataType::DT_UINT16:
			out = AsArray<std::uint16_t, T>();
			break;
		case DataType::DT_UINT32:
			out = AsArray<std::uint32_t, T>();
			break;
		case DataType::DT_UINT64:
			out = AsArray<std::uint64_t, T>();
			break;
		case DataType::DT_INT8:
			out = AsArray<std::int8_t, T>();
			break;
		case DataType::DT_INT16:
			out = AsArray<std::int16_t, T>();
			break;
		case DataType::DT_INT32:
			out = AsArray<std::int32_t, T>();
			break;
		case DataType::DT_INT64:
			out = AsArray<std::int64_t, T>();
			break;
		case DataType::DT_FLOAT32:
			out = AsArray<float, T>();
			break;
		case DataType::DT_FLOAT64:
			out = AsArray<double, T>();
			break;
		case DataType::DT_COMPLEX64:
			out = AsArray<std::complex<float>, T>();
			break;
		case DataType::DT_COMPLEX128:
			out = AsArray<std::complex<double>, T>();
			break;
		default:
			throw std::runtime_error("Type of data frame unknown.");
	}
}

template<typename T>
Eigen::Map<Eigen::Array<T, Eigen::Dynamic, Eigen::Dynamic>> Tensor::AsArray()
{
	return AsArray<T,T>();
}

template<typename T_src, typename T_dest, typename std::enable_if<std::is_same<T_src, T_dest>::value, void>::type *dummy>
auto Tensor::AsArray()
{
	size_t d1 = m_Dimensions[0];
	size_t d2 = m_Dimensions[1];

	return Eigen::Map<Eigen::Array<T_src, Eigen::Dynamic, Eigen::Dynamic>>((T_src *) m_Data, d1, d2);
}

template<typename T_src, typename T_dest, typename std::enable_if<!std::is_same<T_src, T_dest>::value && is_complex<T_src>::value && !is_complex<T_dest>::value, void>::type *dummy>
auto Tensor::AsArray()
{
	size_t d1 = m_Dimensions[0];
	size_t d2 = m_Dimensions[1];

	LOG_WARNING("Discarding imaginary values in conversion to non-complex type.");
	return Eigen::Map<Eigen::Array<T_src, Eigen::Dynamic, Eigen::Dynamic>>((T_src *) m_Data, d1, d2).real().template cast<T_dest>();
}

template<typename T_src, typename T_dest, typename std::enable_if<!std::is_same<T_src, T_dest>::value && (!is_complex<T_src>::value || is_complex<T_dest>::value), void>::type *dummy>
auto Tensor::AsArray()
{
	size_t d1 = m_Dimensions[0];
	size_t d2 = m_Dimensions[1];

	return Eigen::Map<Eigen::Array<T_src, Eigen::Dynamic, Eigen::Dynamic>>((T_src *) m_Data, d1, d2).template cast<T_dest>();
}
