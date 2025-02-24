#ifndef HASH_MAP_H
#define HASH_MAP_H

#include "Shareable.h"

#include <cstddef>
#include <cstdint>
#include <atomic>
#include <string_view>
#include <algorithm>

// MurmurHash3 32-bit version
uint32_t murmurhash3(std::string_view key, uint32_t seed = 0)
{
	const uint8_t *data = reinterpret_cast<const uint8_t *>(key.data());
	size_t len = key.size();

	uint32_t h = seed;
	const uint32_t c1 = 0xcc9e2d51;
	const uint32_t c2 = 0x1b873593;

	// Partition in blocks of 4 bytes.
	const size_t nblocks = len / 4;
	const uint32_t* blocks = reinterpret_cast<const uint32_t *>(data);
	for (size_t i = 0; i < nblocks; i++)
	{
		uint32_t k = blocks[i];
		k *= c1;
		k = (k << 15) | (k >> 17);
		k *= c2;

		h ^= k;
		h = (h << 13) | (h >> 19);
		h = h * 5 + 0xe6546b64;
	}

	// Process leftover bytes.
	const uint8_t* tail = data + nblocks * 4;
	uint32_t k1 = 0;

	switch (len & 3)
	{
		case 3:
			k1 ^= tail[2] << 16;
		case 2:
			k1 ^= tail[1] << 8;
		case 1:
			k1 ^= tail[0];
			k1 *= c1;
			k1 = (k1 << 15) | (k1 >> 17);
			k1 *= c2;
			h ^= k1;
		case 0:
			; // Do nothing.
	}

	h ^= len;
	h ^= (h >> 16);
	h *= 0x85ebca6b;
	h ^= (h >> 13);
	h *= 0xc2b2ae35;
	h ^= (h >> 16);

	return h;
}

std::size_t round_up_to_nearest_multiple_power_of_two(std::size_t value, std::size_t power_of_two)
{
	return (value + power_of_two - 1) & ~(power_of_two - 1);
}

// A hash map with the following limitations:
// * entries cannot be removed.
// * key is string type of fixed size.
class HashMap
{
private:
	enum EntryFlags : uint8_t
	{
		UNOCCUPIED = 0,
		INITIALIZING = 1,
		OCCUPIED = 2
	};

	char *m_Data;

	std::size_t m_NumEntries;
	std::size_t m_MaxKeySize;
	std::size_t m_ValueSize;
	std::size_t m_EntrySize;

	std::size_t GetIndex(std::string_view key) const
	{
		return murmurhash3(key) % m_NumEntries;
	}

	std::string_view GetKey(std::size_t entry) const
	{
		std::size_t i = entry * m_EntrySize + sizeof(EntryFlags);

		return std::string_view(m_Data + i);
	}

	void SetKey(std::size_t entry, std::string_view key)
	{
		std::size_t i = entry * m_EntrySize + sizeof(EntryFlags);

		std::fill(m_Data + i, m_Data + i + m_MaxKeySize, '\0');
		key.copy(m_Data + i, m_MaxKeySize - 1);
	}

	std::atomic<EntryFlags> *GetFlagsRef(std::size_t entry) const
	{
		std::size_t i = entry * m_EntrySize;

		return reinterpret_cast<std::atomic<EntryFlags> *>(m_Data + i);
	}

	void *GetValue(std::size_t entry) const
	{
		std::size_t i = entry * m_EntrySize + sizeof(EntryFlags) + m_MaxKeySize;

		return m_Data + i;
	}

public:
	HashMap(void *buffer, std::size_t num_entries, std::size_t max_key_size, std::size_t value_size)
		: m_Data(static_cast<char *>(buffer)),
		m_NumEntries(num_entries),
		m_MaxKeySize(max_key_size),
		m_ValueSize(value_size),
		m_EntrySize(sizeof(EntryFlags) + max_key_size + value_size)
	{
	}

	static std::size_t CalculateBufferSize(std::size_t num_entries, std::size_t max_key_size, std::size_t value_size)
	{
		auto entry_size = sizeof(EntryFlags) + max_key_size + value_size;
		entry_size = round_up_to_nearest_multiple_power_of_two(entry_size, alignof(std::atomic<EntryFlags>));

		return entry_size * num_entries;
	}

	void Initialize()
	{
		for (std::size_t i = 0; i < m_NumEntries; ++i)
		{
			*GetFlagsRef(i) = EntryFlags::UNOCCUPIED;
			SetKey(i, "");
		}
	}

	void *Insert(std::string_view key)
	{
		if (key.size() >= m_MaxKeySize)
		{
			// Key is too long to fit in the fixed-size buffer.
			return nullptr;
		}

		std::size_t index = GetIndex(key);

		for (std::size_t i = 0; i < m_NumEntries; ++i)
		{
			std::size_t probe = (index + i) % m_NumEntries;
			auto entry_flags = GetFlagsRef(probe);

			// Try to use this entry.
			EntryFlags flags = EntryFlags::UNOCCUPIED;

			bool success = entry_flags->compare_exchange_strong(flags, EntryFlags::INITIALIZING, std::memory_order_acq_rel);

			if (!success)
			{
				// The entry is either occupied or still initializing.

				// If this entry is still initializing, do a spin-wait until it's occupied.
				// This should almost never be necessary and should only last a short while if it does.
				while (flags == EntryFlags::INITIALIZING)
				{
					flags = entry_flags->load(std::memory_order_acquire);
				}

				if (flags == EntryFlags::OCCUPIED)
				{
					// Check if the key is our key.
					if (GetKey(probe) == key)
					{
						// Key already exists.
						return nullptr;
					}
				}
			}
			else
			{
				// The entry was unooccupied, so we can now use it.
				// Set the key of our entry.
				SetKey(probe, key);

				// Make occupied.
				entry_flags->store(EntryFlags::OCCUPIED, std::memory_order_release);

				return GetValue(probe);
			}
		}

		// Map is full.
		return nullptr;
	}

	void *Find(std::string_view key) const
	{
		if (key.size() >= m_MaxKeySize)
		{
			// Key is too long to fit in the fixed-size buffer.
			return nullptr;
		}

		std::size_t index = GetIndex(key);

		for (std::size_t i = 0; i < m_NumEntries; ++i)
		{
			std::size_t probe = (index + i) % m_NumEntries;
			auto entry_flags = GetFlagsRef(probe);

			EntryFlags flags = entry_flags->load(std::memory_order_acquire);

			if (flags == EntryFlags::OCCUPIED && GetKey(probe) == key)
			{
				return GetValue(probe);
			}

			if (flags != EntryFlags::OCCUPIED)
			{
				// Key not found.
				break;
			}
		}

		// Key not found.
		return nullptr;
	}
};

#endif // HASH_MAP_H
