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

template <typename T>
constexpr int bit_width(T x)
{
	static_assert(std::is_integral_v<T> && std::is_unsigned_v<T>, "bit_width requires an unsigned integral type");

	if (x == 0)
		return 0;

#if defined(__GNUC__) || defined(__clang__)
	return std::numeric_limits<unsigned int>::digits - __builtin_clz((unsigned int) x);
#elif defined(_MSC_VER)
	unsigned long index;
	_BitScanReverse(&index, x);
	return index + 1;
#else
	// Portable fallback
	int width = 0;

	while (x)
	{
		x >>= 1;
		++width;
	}

	return width;
#endif
}
