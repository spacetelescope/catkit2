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

template <typename UnsignedType>
constexpr UnsignedType round_up_to_power_of_2(UnsignedType v);

template <typename UnsignedType>
constexpr UnsignedType round_down_to_power_of_2(UnsignedType v);

// Cross-platform implementation of std::bit_width() (in absence of C++20)
template <typename T>
constexpr int bit_width(T x);

#include "Util.inl"

#endif // UTIL_H
