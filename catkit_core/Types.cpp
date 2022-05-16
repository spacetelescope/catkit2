#include "Types.h"

void ToProto(const Value &value, catkit_proto::Value *proto_value)
{
	if (std::holds_alternative<NoneValue>(value))
	{
		proto_value->set_none_value(catkit_proto::NoneValue());
	}
	else if (std::holds_alternative<double>(value))
	{
		proto_value->set_scalar_value(std::get<double>(value));
	}
	else if (std::holds_alternative<std::string>(value))
	{
		proto_value->set_string_value(std::get<std::string>(value));
	}
	else if (std::holds_alternative<bool>(value))
	{
		proto_value->set_bool_value(std::get<bool>(value));
	}
	else if (std::holds_alternative<Dict>(value))
	{
		ToProto(std::get<Dict>(value), proto_value->mutable_dict_value());
	}
	else if (std::holds_alternative<List>(value))
	{
		ToProto(std::get<List>(value), proto_value->mutable_list_value());
	}
	else if (std::holds_alternative<Tensor>(value))
	{
		ToProto(std::get<Tensor>(value), proto_value->mutable_tensor_value());
	}
	else
	{
		throw std::runtime_error("Unknown value type.");
	}
}

void ToProto(const List &list, catkit_proto::List *proto_list)
{
	proto_list->clear_items();

	for (auto &i : list)
	{
		auto item = proto_list->add_items();
		ToProto(i, item);
	}
}

void ToProto(const Dict &dict, catkit_proto::Dict *proto_dict)
{
	proto_dict->clear_items();
	auto d = proto_dict->mutable_items();

	for (auto& [key, value] : dict)
	{
		auto &v = (*d)[key];
		ToProto(value, &v);
	}
}

void FromProto(const catkit_proto::Value *proto_value, Value &value)
{
	if (proto_value->has_none_value())
	{
		value = Value(NoneValue());
	}
	else if (proto_value->has_scalar_value())
	{
		value = Value(proto_value->scalar_value());
	}
	else if (proto_value->has_string_value())
	{
		value = Value(proto_value->string_value());
	}
	else if (proto_value->has_bool_value())
	{
		value = Value(proto_value->bool_value());
	}
	else if (proto_value->has_dict_value())
	{
		Dict dict;
		FromProto(&proto_value->dict_value(), dict);
		value = Value(dict);
	}
	else if (proto_value->has_list_value())
	{
		List list;
		FromProto(&proto_value->list_value(), list);
		value = Value(list);
	}
	else if (proto_value->has_tensor_value())
	{
		Tensor tensor;
		FromProto(&proto_value->tensor_value(), tensor);
		value = Value(tensor);
	}
	else
	{
		throw std::runtime_error("Unknown value type.");
	}
}

void FromProto(const catkit_proto::List *proto_list, List &list)
{
	list.clear();

	for (auto &item : proto_list->items())
	{
		Value val;
		FromProto(&item, val);
		list.push_back(std::move(val));
	}
}

void FromProto(const catkit_proto::Dict *proto_dict, Dict &dict)
{
	dict.clear();

	for (auto & [key, value] : proto_dict->items())
	{
		Value val;
		FromProto(&value, val);
		dict.insert(std::make_pair(key, std::move(val)));
	}
}
