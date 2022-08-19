#ifndef UTIL_H
#define UTIL_H

#include <string>

int GetProcessId();
int GetThreadId();

template<typename ProtoClass>
std::string Serialize(const ProtoClass &obj);

template<typename ProtoClass>
ProtoClass Deserialize(const std::string &data);

void Sleep(double sleep_time_in_sec, bool (*cancellation_callback)() = nullptr);

#include "Util.inl"

#endif // UTIL_H
