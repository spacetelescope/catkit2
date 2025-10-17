#include <iostream>

#include "LocalMemory.h"
#include "LocalMessageBroker.h"
#include "benchmark_constants.h"

const size_t NUM_MESSAGES = 10000000;
const size_t BUFFER_SIZE = LARGE_BUFFER_SIZE;      // 512 MB
const size_t MEMORY_BLOCK_SIZE = MEDIUM_BUFFER_SIZE;  // 128 MB

int main(int argc, char *argv[])
{
	auto buffer = LocalMemory::Create(BUFFER_SIZE);
	auto stream = StructStream(buffer);

	std::vector<std::shared_ptr<Memory>> memory_blocks;
	memory_blocks.push_back(LocalMemory::Create(stream, MEMORY_BLOCK_SIZE));

	auto message_broker = LocalMessageBroker::Create(stream, memory_blocks);

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
	std::cout << (end - start) / NUM_MESSAGES << " ns per message" << std::endl;

	return 0;
}
