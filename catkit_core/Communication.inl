#include "Timestamp.h"
#include "Log.h"

#include <zmq_addon.hpp>

template<typename ProtoRequest, typename ProtoReply>
void Client::MakeRequest(const std::string &what, const ProtoRequest &request, ProtoReply &reply)
{
    auto socket = GetSocket();

	std::string send_string;
	request.SerializeToString(&send_string);

	zmq::multipart_t request_msg;

	request_msg.addstr(what);
	request_msg.addstr(send_string);

	request_msg.send(*socket);

	Timer timer;

	try
	{
		zmq::multipart_t reply_msg;
		auto res = zmq::recv_multipart(*socket, std::back_inserter(reply_msg));

		if (!res.has_value())
		{
			LOG_ERROR("The server took too long to respond to our request.");
			throw std::runtime_error("The server did not respond in time. Is it running?");
		}

		if (reply_msg.size() != 2)
		{
			LOG_ERROR("The server responded with " + std::to_string(reply_msg.size()) + " parts rather than 2.");
			throw std::runtime_error("The server responded in a wrong format.");
		}

		std::string reply_type = reply_msg.popstr();
		std::string reply_data = reply_msg.popstr();

		if (reply_type == "OK")
		{
			reply.ParseFromString(reply_data);
			return;
		}
		else if (reply_type == "ERROR")
		{
			throw std::runtime_error(reply_data);
		}
		else
		{
			LOG_ERROR("The server responded with \"" + reply_type + "\" rather than OK or ERROR.");
			throw std::runtime_error("The server responded in a wrong format.");
		}
	}
	catch (const zmq::error_t &e)
	{
		LOG_ERROR(std::string("ZeroMQ error: ") + e.what());
		throw;
	}
}
