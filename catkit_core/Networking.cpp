#include "Networking.h"

int zmq_recv_multipart(socket_t *socket, std::back_insert_iterator<std::vector<std::string>> inserter)
{
	while (true)
	{
		zmq_msg_t msg;
		zmq_msg_init(&msg);

		if (zmq_msg_recv(&msg, socket, 0) < 0)
		{
			// Clean up state.
			zmq_msg_close(&msg);

			return -1;
		}

		// Insert into the inserter.
		std::string part_str(static_cast<char*>(zmq_msg_data(&msg)), zmq_msg_size(&msg));
		inserter = std::move(part_str);

		bool more = zmq_msg_more(&msg);

		zmq_msg_close(&msg);

		if (!more)
			break;
	}

	// All parts received successfully.
	return 0;
}
