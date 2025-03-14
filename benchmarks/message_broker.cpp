#include <iostream>

#include "MessageBroker.h"

int main(int argc, char *argv[])
{
	char *buffer = new char[1024 * 1024 * 512];
	auto stream = StructStream(buffer);

	std::vector<std::shared_ptr<Memory>> memory_blocks;
	memory_blocks.push_back(LocalMemory::Create(stream, 1024 * 1024 * 128));

	auto message_broker = MessageBroker::Create(stream, memory_blocks);

	std::cout << "Message broker size: " << stream.GetOffset() << std::endl;

	std::cout << "Message broker created." << std::endl;

	Message message = message_broker->PrepareMessage("test", 16);

	std::cout << "Message prepared." << std::endl;

	//message_broker->PublishMessage(message);

	std::cout << "Message published." << std::endl;

	return 0;
}
