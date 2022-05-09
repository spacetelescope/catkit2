#ifndef UTIL_H
#define UTIL_H

int GetProcessId();
int GetThreadId();

template<typename ProtoRequest, typename ProtoReply>
void MakeRequest(zmq::socket_t &socket, const std::string &what, const ProtoRequest &request, ProtoReply &reply);

#include "Util.inl"

#endif // UTIL_H
