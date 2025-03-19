#include "UuidGenerator.h"

#include <sstream>
#include <iomanip>

UuidGenerator::UuidGenerator()
{
	std::random_device random_device;

	for (size_t i = 0; i < 2; ++i)
	{
		std::seed_seq seed{random_device(), random_device()};
		m_Engines[i].seed(seed);
	}
}

void UuidGenerator::Generate(Uuid *uuid)
{
	// Fill all bytes with random data.
	for (size_t i = 0; i < 2; ++i)
	{
		std::uint64_t value = m_Engines[i]();
		*reinterpret_cast<std::uint64_t *>(uuid->data + i * 8) = value;
	}

	// Ensure we are compliant with RFC 4122.
	// Set the version and variant bits to conform to version 4.
	uuid->data[6] = (uuid->data[6] & 0x0F) | 0x40;
	uuid->data[8] = (uuid->data[8] & 0x3F) | 0x80;
}

std::string Uuid::to_string() const
{
	std::ostringstream oss;
	oss << std::hex << std::setfill('0');

	for (size_t i = 0; i < 16; ++i)
	{
		// Insert hex value of the current byte.
		oss << std::setw(2) << static_cast<int>(data[i]);

		// Insert dashes at the correct positions.
		if (i == 3 || i == 5 || i == 7 || i == 9)
			oss << '-';
	}

	return oss.str();
}
