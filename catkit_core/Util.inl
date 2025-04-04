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

template <typename UnsignedType>
constexpr UnsignedType round_up_to_power_of_2(UnsignedType v)
{
	static_assert(std::is_unsigned_v<UnsignedType>);

	v--;

	for (std::size_t i = 1; i < sizeof(v) * 8; i *= 2)
	{
		v |= v >> i;
	}

	return ++v;
}

template <typename UnsignedType>
constexpr UnsignedType round_down_to_power_of_2(UnsignedType v)
{
	static_assert(std::is_unsigned_v<UnsignedType>);

    for (size_t i = 1; i < sizeof(v) * 8; i *= 2)
        v |= v >> i;

    return v - (v >> 1);
}
