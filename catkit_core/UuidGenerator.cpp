#include "UuidGenerator.h"

UuidGenerator::UuidGenerator()
{
	std::random_device random_device;

	for (size_t i = 0; i < 2; ++i)
	{
		std::seed_seq seed{random_device(), random_device()};
		m_Engines[i].seed(seed);
	}
}

void UuidGenerator::Generate(Uuid &uuid)
{
	for (size_t i = 0; i < 2; ++i)
	{
		std::uint64_t value = m_Engines[i]();
		*reinterpret_cast<std::uint64_t *>(uuid + i * 8) = value;
	}
}
