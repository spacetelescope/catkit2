#ifndef HASH_MAP_H
#define HASH_MAP_H

#include <cstddef>
#include <cstdint>
#include <atomic>
#include <string_view>

// MurmurHash3 32-bit version
uint32_t murmurhash3(const std::string_view &key, uint32_t seed = 0)
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

// A hash map with the following limitations:
// * entries cannot be removed.
// * key is string type of fixed size.
template <typename Value, std::size_t Size, std::size_t MaxKeyLength>
class HashMap
{
private:
	enum EntryFlags : uint8_t
	{
		UNOCCUPIED = 0,
		INITIALIZING = 1,
		OCCUPIED = 2
	};

	struct Entry
	{
		Value value;

		std::atomic<EntryFlags> flags = EntryFlags::UNOCCUPIED;
		char key[MaxKeyLength];
	};

	Entry *m_Data;

	size_t GetIndex(std::string_view key) const
	{
		return murmurhash3(key) % Size;
	}

public:
	HashMap(void *buffer)
		: m_Data(reinterpret_cast<Entry *>(buffer))
	{
	}

	static std::size_t CalculateBufferSize()
	{
		return sizeof(Entry) * Size;
	}

	void Initialize()
	{
		for (size_t i = 0; i < Size; ++i)
		{
			m_Data[i].flags = EntryFlags::UNOCCUPIED;

			std::fill(m_Data[i].key, m_Data[i].key + MaxKeyLength, '\0');
		}
	}

	bool Insert(std::string_view key, const Value &value)
	{
		if (key.size() >= MaxKeyLength)
		{
			// Key is too long to fit in the fixed-size buffer.
			return false;
		}

		size_t index = GetIndex(key);

		for (size_t i = 0; i < Size; ++i)
		{
			size_t probe = (index + i) % Size;

			// Try to use this entry.
			EntryFlags flags = EntryFlags::UNOCCUPIED;

			bool success = m_Data[probe].flags.compare_exchange_strong(flags, EntryFlags::INITIALIZING, std::memory_order_acq_rel);

			if (!success)
			{
				// The entry is either occupied or still initializing.

				// If this entry is still initializing, do a spin-wait until it's occupied.
				// This should almost never be necessary and should only last a short while if it does.
				while (flags == EntryFlags::INITIALIZING)
				{
					flags = m_Data[probe].flags.load(std::memory_order_acquire);
				}

				if (flags == EntryFlags::OCCUPIED)
				{
					// Check if the key is our key.
					if (key == m_Data[probe].key)
					{
						// Key already exists.
						return false;
					}
				}
			}
			else
			{
				// Copy key, ensuring null-termination.
				key.copy(m_Data[probe].key, key.size());
				m_Data[probe].key[key.size()] = '\0';

				// Copy m_Data.
				m_Data[probe].value = value;

				// Make occupied.
				m_Data[probe].flags.store(EntryFlags::OCCUPIED, std::memory_order_release);

				return true;
			}
		}

		// Map is full.
		return false;
	}

	Value *Find(std::string_view key) const
	{
		if (key.size() >= MaxKeyLength)
		{
			// Key is too long to fit in the fixed-size buffer.
			return nullptr;
		}

		size_t index = GetIndex(key);

		for (size_t i = 0; i < Size; ++i)
		{
			size_t probe = (index + i) % Size;

			EntryFlags flags = m_Data[probe].flags.load(std::memory_order_acquire);

			if (flags == EntryFlags::OCCUPIED && key == m_Data[probe].key)
			{
				return &m_Data[probe].value;
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
