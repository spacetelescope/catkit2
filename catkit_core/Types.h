#ifndef TYPES_H
#define TYPES_H

#include "Tensor.h"
#include "proto/core.pb.h"

#include <list>
#include <map>
#include <variant>
#include <string>
#include <cstdint>

class List;
class Dict;

class NoneValue
{
};

using Value = std::variant<
	NoneValue,
	std::int64_t,
	double,
	std::string,
	bool,
	Dict,
	List,
	Tensor>;

class List : public std::list<Value>
{
};

class Dict : public std::map<std::string, Value>
{
};

void ToProto(const Value &value, catkit_proto::Value *proto_value);
void ToProto(const List &list, catkit_proto::List *proto_list);
void ToProto(const Dict &dict, catkit_proto::Dict *proto_dict);

void FromProto(const catkit_proto::Value *proto_value, Value &value);
void FromProto(const catkit_proto::List *proto_list, List &list);
void FromProto(const catkit_proto::Dict *proto_dict, Dict &dict);

template <typename T>
T CastTo(const Value &val)
{
	return std::visit([](auto &&val)
	{
		if constexpr(std::is_convertible_v<decltype(val), T>)
		{
			return T(val);
		}
		else
		{
			throw std::bad_variant_access{};
			return T{};
		}
	}, val);
}

#endif // TYPES_H
