#include "Log.h"

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
        if (sizeof(T) == 16)
            return DataType::DT_FLOAT128;
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
        if (sizeof(T) == 16)
            return "float128";
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
