#include "Tensor.h"

#include <algorithm>

using namespace std;

const char *GetDataTypeAsString(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
			return "B";
		case DataType::DT_UINT16:
			return "H";
		case DataType::DT_UINT32:
			return "L";
		case DataType::DT_UINT64:
			return "Q";
		case DataType::DT_INT8:
			return "b";
		case DataType::DT_INT16:
			return "h";
		case DataType::DT_INT32:
			return "l";
		case DataType::DT_INT64:
			return "q";
		case DataType::DT_FLOAT32:
			return "f";
		case DataType::DT_FLOAT64:
			return "d";
		case DataType::DT_COMPLEX64:
			return "Zf";
		case DataType::DT_COMPLEX128:
			return "Zd";
		default:
			return "unknown";
	}
}

DataType GetDataTypeFromString(const char *type)
{
	return GetDataTypeFromString(string(type));
}

DataType GetDataTypeFromString(string type)
{
	if (type == "B" || type == "uint8")
		return DataType::DT_UINT8;
	if (type == "H" || type == "uint16")
		return DataType::DT_UINT16;
	if (type == "L" || type == "uin32")
		return DataType::DT_UINT32;
	if (type == "Q" || type == "uint64")
		return DataType::DT_UINT64;
	if (type == "b" || type == "int8")
		return DataType::DT_INT8;
	if (type == "h" || type == "int16")
		return DataType::DT_INT16;
	if (type == "l" || type == "int32")
		return DataType::DT_INT32;
	if (type == "q" || type == "int64")
		return DataType::DT_INT64;
	if (type == "f" || type == "float32")
		return DataType::DT_FLOAT32;
	if (type == "d" || type == "float64")
		return DataType::DT_FLOAT64;
	if (type == "Zf" || type == "complex64")
		return DataType::DT_COMPLEX64;
	if (type == "Zd" || type == "complex128")
		return DataType::DT_COMPLEX128;
	return DataType::DT_UNKNOWN;
}

size_t GetSizeOfDataType(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
		case DataType::DT_INT8:
			return 1;
		case DataType::DT_UINT16:
		case DataType::DT_INT16:
			return 2;
		case DataType::DT_UINT32:
		case DataType::DT_INT32:
		case DataType::DT_FLOAT32:
			return 4;
		case DataType::DT_UINT64:
		case DataType::DT_INT64:
		case DataType::DT_FLOAT64:
		case DataType::DT_COMPLEX64:
			return 8;
		case DataType::DT_COMPLEX128:
			return 16;
		default:
			return 0;
	}
}

Tensor::Tensor()
	: m_Data(nullptr), m_DataType(DataType::DT_UNKNOWN), m_NumDimensions(0), m_IsOwner(false)
{
}

Tensor::~Tensor()
{
	if (IsOwner())
		delete[] m_Data;
}

DataType Tensor::GetDataType() const
{
	return m_DataType;
}

size_t Tensor::GetNumDimensions() const
{
	return m_NumDimensions;
}

size_t *Tensor::GetDimensions() const
{
	return (size_t *) m_Dimensions;
}

char *Tensor::GetData() const
{
	return m_Data;
}

bool Tensor::IsOwner() const
{
	return m_IsOwner;
}

void Tensor::Set(DataType data_type, size_t num_dimensions, size_t *dimensions, char *data, bool is_owner)
{
	if (m_IsOwner && m_Data)
	{
		delete[] m_Data;
	}

	m_DataType = data_type;
	m_NumDimensions = num_dimensions;
	std::copy(dimensions, dimensions + 4, m_Dimensions);

	m_Data = data;
	m_IsOwner = is_owner;
}

size_t Tensor::GetNumElements()
{
	return m_Dimensions[0] * m_Dimensions[1] * m_Dimensions[2] * m_Dimensions[3];
}

size_t Tensor::GetSizeInBytes()
{
	return GetNumElements() * GetSizeOfDataType(m_DataType);
}
