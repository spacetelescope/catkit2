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
			return "F";  // Use Numpy format standard. PEP3118 would be "Zf".
		case DataType::DT_COMPLEX128:
			return "D";  // Use Numpy format standard. PEP3118 would be "Zd".
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
	if (type == "L" || type == "uint32")
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
	if (type == "F" || type == "complex64" || type == "Zf")  // Support both PEP3118 and Numpy formats.
		return DataType::DT_COMPLEX64;
	if (type == "D" || type == "complex128" || type == "Zd")  // Support both PEP3118 and Numpy formats.
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

Tensor::Tensor(const Tensor &other)
	: Tensor()
{
	Set(other.m_DataType, other.m_NumDimensions, (size_t *) other.m_Dimensions, (const char *) other.m_Data);
}

Tensor::Tensor(Tensor &&tensor)
{
	*this = std::move(tensor);
}

Tensor::~Tensor()
{
	if (IsOwner())
		delete[] m_Data;
}

Tensor &Tensor::operator=(const Tensor &other)
{
	Set(other.m_DataType, other.m_NumDimensions, (size_t *) other.m_Dimensions, (const char *) other.m_Data);

	return *this;
}

Tensor &Tensor::operator=(Tensor &&other)
{
	m_DataType = std::move(other.m_DataType);
	m_NumDimensions = std::move(other.m_NumDimensions);
	std::copy(other.m_Dimensions, other.m_Dimensions + 4, m_Dimensions);
	m_Data = std::move(other.m_Data);
	m_IsOwner = std::move(other.m_IsOwner);

	other.m_IsOwner = false;

	return *this;
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

void Tensor::SetCommon(DataType data_type, size_t num_dimensions, size_t *dimensions)
{
	if (m_IsOwner && m_Data)
	{
		delete[] m_Data;
		m_Data = nullptr;
	}

	m_DataType = data_type;
	m_NumDimensions = num_dimensions;
	std::copy(dimensions, dimensions + 4, m_Dimensions);
}

void Tensor::Set(DataType data_type, size_t num_dimensions, size_t *dimensions, char *data, bool copy)
{
	if (copy)
		return Set(data_type, num_dimensions, dimensions, (const char *) data);

	SetCommon(data_type, num_dimensions, dimensions);

	m_Data = data;

	m_IsOwner = false;
}

void Tensor::Set(DataType data_type, size_t num_dimensions, size_t *dimensions, const char *data)
{
	SetCommon(data_type, num_dimensions, dimensions);

	m_Data = new char[GetSizeInBytes()];
	std::copy(data, data + GetSizeInBytes(), m_Data);

	m_IsOwner = true;
}

size_t Tensor::GetNumElements() const
{
	return m_Dimensions[0] * m_Dimensions[1] * m_Dimensions[2] * m_Dimensions[3];
}

size_t Tensor::GetSizeInBytes() const
{
	return GetNumElements() * GetSizeOfDataType(m_DataType);
}

void ToProto(const Tensor &tensor, catkit_proto::Tensor *proto_tensor)
{
	proto_tensor->set_dtype(GetDataTypeAsString(tensor.GetDataType()));

	for (size_t i = 0; i < tensor.GetNumDimensions(); ++i)
		proto_tensor->add_dimensions(tensor.GetDimensions()[i]);

	proto_tensor->set_data(tensor.GetData(), tensor.GetSizeInBytes());
}

void FromProto(const catkit_proto::Tensor *proto_tensor, Tensor &tensor)
{
	auto dtype = GetDataTypeFromString(proto_tensor->dtype());
	auto num_dimensions = proto_tensor->dimensions_size();

	size_t dimensions[4];
	for (int i = 0; i < num_dimensions; ++i)
		dimensions[i] = proto_tensor->dimensions(i);
	for (size_t i = num_dimensions; i < 4; ++i)
		dimensions[i] = 1;

	tensor.Set(dtype, num_dimensions, dimensions, proto_tensor->data().c_str());
}
