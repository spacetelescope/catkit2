#include <iostream>

#include "MessageBroker.h"

const size_t NUM_MESSAGES = 10000000;

int main(int argc, char *argv[])
{
	char *buffer = new char[1024 * 1024 * 512];
	auto stream = StructStream(buffer);

	std::vector<std::shared_ptr<Memory>> memory_blocks;
	memory_blocks.push_back(LocalMemory::Create(stream, 1024 * 1024 * 128));

	auto message_broker = MessageBroker::Create(stream, memory_blocks);

	std::cout << "Message broker size: " << stream.GetOffset() << std::endl;

	std::cout << "Message broker created." << std::endl;

	auto start = GetTimeStamp();

	for (int i = 0; i < NUM_MESSAGES; ++i)
	{
		Message message = message_broker->PrepareMessage("abc/def/ghi/set", 16);

		message_broker->PublishMessage(message);
	}

	auto end = GetTimeStamp();

	std::cout << NUM_MESSAGES / ((end - start) * 1e-9) << " messages per second" << std::endl;

	return 0;
}
