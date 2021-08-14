#ifndef SERIALIZATION_H
#define SERIALIZATION_H

#include <string>
#include <stdexcept>

#include <nlohmann/json.hpp>
#include <Eigen/Dense>

#include "ComplexTraits.h"

struct SerializedMessage
{
	SerializedMessage();
	SerializedMessage(const SerializedMessage &cpy);

	bool ContainsValue() const;
	bool ContainsArrayValue() const;
	bool ContainsNonArrayValue() const;

	template <typename T>
	Eigen::Array<typename std::enable_if<is_complex<T>::value, T>::type, Eigen::Dynamic, Eigen::Dynamic> GetArray() const;
	template <typename T>
	Eigen::Array<typename std::enable_if<!is_complex<T>::value, T>::type, Eigen::Dynamic, Eigen::Dynamic> GetArray() const;

	template <typename Derived>
	void SetArray(const Eigen::DenseBase<Derived> &other);

	nlohmann::json data;
	std::vector<unsigned char> binary_data;
};

class SerializationError
	: public std::runtime_error
{
public:
	SerializationError(const char *what);
	SerializationError(const std::string &what);
};

#include "Serialization.inl"

#endif // SERIALIZATION_H