template<typename ProtoClass>
std::string Serialize(const ProtoClass &obj)
{
	std::string data;
	obj.SerializeToString(&data);

	return data;
}

template<typename ProtoClass>
ProtoClass Deserialize(const std::string &data)
{
	ProtoClass obj;
	obj.ParseFromString(data);

	return obj;
}
