#ifndef TYPES_H
#define TYPES_H

#include "Tensor.h"
#include "proto/core.pb.h"

#include <list>
#include <map>
#include <variant>
#include <string>

class List;
class Dict;

class NoneValue
{
};

using Value = std::variant<
	NoneValue,
	int,
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

#endif // TYPES_H
