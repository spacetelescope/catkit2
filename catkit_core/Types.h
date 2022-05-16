#ifndef TYPES_H
#define TYPES_H

#include "Tensor.h"
#include "core.pb.h"

#include <list>
#include <map>
#include <variant>
#include <string>

class Value;

class NoneValue
{
};

typedef std::list<Value> List;
typedef std::map<std::string, Value> Dict;

class Value : public std::variant<
	NoneValue,
	double,
	std::string,
	bool,
	Dict,
	List,
	Tensor>
{
};

void ToProto(const Value &value, catkit_proto::Value *proto_value);
void ToProto(const List &list, catkit_proto::List *proto_list);
void ToProto(const Dict &dict, catkit_proto::Dict *proto_dict);

void FromProto(const catkit_proto::Value *proto_value, Value &value);
void FromProto(const catkit_proto::List *proto_list, List &list);
void FromProto(const catkit_proto::Dict *proto_dict, Dict &dict);

#endif // TYPES_H
