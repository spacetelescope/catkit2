template<typename ProtoRequest>
std::string Serialize(const ProtoRequest &request)
{
	std::string request_string;
	request.SerializeToString(&request_string);
	return request_string;
}
