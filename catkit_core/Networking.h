#ifndef NETWORK_H
#define NETWORK_H

#include <zmq.h>
#include <vector>
#include <string>
#include <iterator>

struct socket_t
{
};

struct context_t
{
};

int zmq_recv_multipart(socket_t *socket, std::back_insert_iterator<std::vector<std::string>> inserter);

#endif // NETWORK_H
