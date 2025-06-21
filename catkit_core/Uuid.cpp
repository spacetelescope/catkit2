#include "Uuid.h"

#include <sstream>
#include <iomanip>

class UuidGenerator
{
public:
	UuidGenerator()
	{
		std::random_device random_device;

		for (size_t i = 0; i < 2; ++i)
		{
			std::seed_seq seed{random_device(), random_device()};
			m_Engines[i].seed(seed);
		}
	}

	void Generate(Uuid *uuid)
	{
		// Fill all bytes with random data.
		for (size_t i = 0; i < 2; ++i)
		{
			std::uint64_t value = m_Engines[i]();
			std::memcpy(uuid->data.data() + i * 8, &value, sizeof(value));
		}

		// Ensure we are compliant with RFC 4122.
		// Set the version and variant bits to conform to version 4.
		uuid->data[6] = (uuid->data[6] & 0x0F) | 0x40;
		uuid->data[8] = (uuid->data[8] & 0x3F) | 0x80;
	}

private:
	std::mt19937_64 m_Engines[2];
};

void Uuid::Generate(Uuid *uuid)
{
	static thread_local UuidGenerator generator;

	generator.Generate(uuid);
}

bool Uuid::operator==(const Uuid &other) const
{
	return std::equal(data.begin(), data.end(), other.data.begin());
}

bool Uuid::operator!=(const Uuid &other) const
{
	return !(*this == other);
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
