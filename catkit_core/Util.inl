#include "Util.h"

#include <limits>
#include <cstdint>
#include <type_traits>

#if __has_include(<bit>)
	#include <bit>
#endif

#if defined(_MSC_VER)
	#include <intrin.h>
#endif

#if defined(__cpp_lib_bitops) && __cpp_lib_bitops >= 201907L
	#define HAS_STD_BIT
#endif

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

template <typename T, enable_uint<T>>
constexpr T round_up_to_power_of_2(T v) noexcept
{
	v--;

	for (std::size_t i = 1; i < sizeof(v) * 8; i *= 2)
	{
		v |= v >> i;
	}

	return ++v;
}

template <typename T, enable_uint<T>>
constexpr T round_down_to_power_of_2(T v) noexcept
{
	for (size_t i = 1; i < sizeof(v) * 8; i *= 2)
		v |= v >> i;

	return v - (v >> 1);
}

// The number of bits needed to store the value x.
template <typename T, enable_uint<T>>
inline constexpr int bit_width(T x) noexcept
{
	constexpr unsigned BW = std::numeric_limits<T>::digits;
	return BW - countl_zero(x);
}

/// Count trailing zeros in the binary representation of x.
template <typename T, enable_uint<T>>
inline unsigned countr_zero(T x) noexcept
{
#ifdef HAS_STD_BIT
	return std::countr_zero(x);
#elif defined(_MSC_VER)
	unsigned long idx;
	if constexpr (sizeof(T) == 8)
	{
		return _BitScanForward64(&idx, x) ? idx : 64;
	}
	else
	{
		return _BitScanForward(&idx, static_cast<unsigned long>(x)) ? idx : 32;
	}
#elif defined(__GNUC__) || defined(__clang__)
	if constexpr (sizeof(T) == 8)
	{
		return x ? __builtin_ctzll(x) : 64;
	}
	else
	{
		return x ? __builtin_ctz(x) : 32;
	}
#else
	// Portable fallback
	if (x == 0)
		return sizeof(T) * 8;

	unsigned count = 0;
	while ((x & 1) == 0)
	{
		x >>= 1;
		++count;
	}

	return count;
#endif
}

/// Count leading zeros in the binary representation of x.
template <typename T, enable_uint<T>>
inline unsigned countl_zero(T x) noexcept
{
#ifdef HAS_STD_BIT
	return std::countl_zero(x);
#elif defined(_MSC_VER)
	unsigned long idx;
	if constexpr (sizeof(T) == 8)
	{
		return _BitScanReverse64(&idx, x) ? (63 - idx) : 64;
	}
	else
	{
		return _BitScanReverse(&idx, static_cast<unsigned long>(x)) ? (31 - idx) : 32;
	}
#elif defined(__GNUC__) || defined(__clang__)
	if constexpr (sizeof(T) == 8)
	{
		return x ? __builtin_clzll(x) : 64;
	}
	else
	{
		return x ? __builtin_clz(x) : 32;
	}
#else
	// Portable fallback
	if (x == 0)
		return sizeof(T) * 8;

	unsigned count = 0;
	T mask = T(1) << (sizeof(T) * 8 - 1);

	while ((x & mask) == 0)
	{
		mask >>= 1;
		++count;
	}

	return count;
#endif
}
