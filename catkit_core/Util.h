#ifndef UTIL_H
#define UTIL_H

#include <string>
#include <functional>

int GetProcessId();
int GetThreadId();

template<typename ProtoClass>
std::string Serialize(const ProtoClass &obj);

template<typename ProtoClass>
ProtoClass Deserialize(const std::string &data);

void Sleep(double sleep_time_in_sec, std::function<bool()> cancellation_callback = nullptr);

template <typename T>
using enable_uint = std::enable_if_t<std::is_unsigned<T>::value, int>;

template <typename T, enable_uint<T> = 0>
constexpr T round_up_to_power_of_2(T v) noexcept;

template <typename T, enable_uint<T> = 0>
constexpr T round_down_to_power_of_2(T v) noexcept;

// Cross-platform implementation of std::bit_width() (in absence of C++20)
template <typename T, enable_uint<T> = 0>
inline constexpr int bit_width(T x) noexcept;

// Cross-platform implementation of std::countr_zero() (in absence of C++20)
template <typename T, enable_uint<T> = 0>
inline unsigned countr_zero(T x) noexcept;

// Cross-platform implementation of std::countl_zero() (in absence of C++20)
template <typename T, enable_uint<T> = 0>
inline unsigned countl_zero(T x) noexcept;

#include "Util.inl"

#endif // UTIL_H
