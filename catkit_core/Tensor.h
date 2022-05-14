#ifndef TENSOR_H
#define TENSOR_H

#include "ComplexTraits.h"

#include <Eigen/Dense>

#include <string>
#include <memory>

enum class DataType
{
	DT_UINT8 = 0,
	DT_UINT16,
	DT_UINT32,
	DT_UINT64,
	DT_INT8,
	DT_INT16,
	DT_INT32,
	DT_INT64,
	DT_FLOAT32,
	DT_FLOAT64,
	DT_COMPLEX64,
	DT_COMPLEX128,
	DT_UNKNOWN
};

template<typename T>
constexpr DataType GetDataType();

template<typename T>
constexpr const char *GetDataTypeAsString();

const char *GetDataTypeAsString(DataType type);

DataType GetDataTypeFromString(const char *type);
DataType GetDataTypeFromString(std::string type);

size_t GetSizeOfDataType(DataType type);

class Tensor
{
public:
	Tensor();
	~Tensor();

	// Convenience functions.
	size_t GetNumElements();
	size_t GetSizeInBytes();

	// Accessors.
	DataType GetDataType() const;
	size_t GetNumDimensions() const;
	size_t *GetDimensions() const;
	char *GetData() const;
	bool IsOwner() const;

	void Set(DataType data_type, size_t num_dimensions, size_t *dimensions, char *data, bool is_owner=true);

	// Accessors for Eigen mapped arrays.
	template<typename EigenType>
	void CopyInto(EigenType &out);

	template<typename T>
	Eigen::Map<Eigen::Array<T, Eigen::Dynamic, Eigen::Dynamic>> AsArray();

	template<typename T_src, typename T_dest, typename std::enable_if<std::is_same<T_src, T_dest>::value, void>::type *dummy = nullptr>
	auto AsArray();

	template<typename T_src, typename T_dest, typename std::enable_if<!std::is_same<T_src, T_dest>::value && is_complex<T_src>::value && !is_complex<T_dest>::value, void>::type *dummy = nullptr>
	auto AsArray();

	template<typename T_src, typename T_dest, typename std::enable_if<!std::is_same<T_src, T_dest>::value && (!is_complex<T_src>::value || is_complex<T_dest>::value),void>::type *dummy = nullptr>
	auto AsArray();

//private: // TODO: Modify access to only use the accessors above.
	DataType m_DataType;
	size_t m_NumDimensions;
	size_t m_Dimensions[4];

	char *m_Data;
	bool m_IsOwner;
};

#endif // TENSOR_H
