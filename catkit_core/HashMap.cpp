#include "HashMap.h"
#include "Util.h"

#include <algorithm>
#include <cstring>
#include <iostream>

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

std::string to_hex(unsigned char c)
{
	const static char hex[] = "0123456789abcdef";

	return {hex[c >> 4], hex[c & 0x0f]};
}

std::string string_view_to_hex(std::string_view sv)
{
	std::string result;

	for (unsigned char c : sv) {
		result += to_hex(c);
	}

	return result;
}

std::size_t round_up_to_nearest_multiple_power_of_two(std::size_t value, std::size_t power_of_two)
{
	return (value + power_of_two - 1) & ~(power_of_two - 1);
}

std::uint32_t HashMap::GetHash(std::string_view key) const
{
	return murmurhash3(key);
}

std::size_t HashMap::GetIndex(std::string_view key) const
{
	return GetHash(key) % m_NumEntries;
}

std::string_view HashMap::GetKey(std::size_t entry) const
{
	std::size_t i = entry * m_EntrySize + sizeof(EntryFlags);

	return std::string_view(m_Data + i);
}

void HashMap::SetKey(std::size_t entry, std::string_view key)
{
	std::size_t i = entry * m_EntrySize + sizeof(EntryFlags);

	std::fill(m_Data + i, m_Data + i + m_MaxKeySize, '\0');
	key.copy(m_Data + i, m_MaxKeySize - 1);
}

std::atomic<HashMap::EntryFlags> *HashMap::GetFlagsRef(std::size_t entry) const
{
	std::size_t i = entry * m_EntrySize;

	return reinterpret_cast<std::atomic<EntryFlags> *>(m_Data + i);
}

void *HashMap::GetValue(std::size_t entry) const
{
	std::size_t i = entry * m_EntrySize + sizeof(EntryFlags) + m_MaxKeySize;

	return m_Data + i;
}

HashMap::HashMap(char *data, std::size_t num_entries, std::size_t max_key_size, std::size_t value_size, std::shared_ptr<Memory> memory_block)
	: Shareable(memory_block),
	m_Data(data),
	m_NumEntries(num_entries),
	m_MaxKeySize(max_key_size),
	m_ValueSize(value_size),
	m_EntrySize(CalculateEntrySize(max_key_size, value_size))
{
}

std::size_t HashMap::CalculateEntrySize(std::size_t max_key_size, std::size_t value_size)
{
	auto entry_size = sizeof(EntryFlags) + max_key_size + value_size;
	entry_size = round_up_to_nearest_multiple_power_of_two(entry_size, alignof(std::atomic<EntryFlags>));

	return entry_size;
}

std::size_t HashMap::GetSharedStateSize(std::size_t num_entries, std::size_t max_key_size, std::size_t value_size)
{
	auto entry_size = CalculateEntrySize(max_key_size, value_size);

	return sizeof(size_t) * 3 + entry_size * num_entries;
}

std::shared_ptr<HashMap> HashMap::Create(StructStream &stream, std::size_t num_entries, std::size_t max_key_size, std::size_t value_size)
{
	*stream.Extract<std::size_t>() = num_entries;
	*stream.Extract<std::size_t>() = max_key_size;
	*stream.Extract<std::size_t>() = value_size;

	auto data = stream.Extract<char>(CalculateEntrySize(max_key_size, value_size) * num_entries);

	auto map = std::shared_ptr<HashMap>(new HashMap(data, num_entries, max_key_size, value_size, stream.GetBuffer()));

	// Initialize the map.
	for (std::size_t i = 0; i < map->m_NumEntries; ++i)
	{
		map->GetFlagsRef(i)->store(EntryFlags::UNOCCUPIED);
		map->SetKey(i, "");
	}

	return map;
}

std::shared_ptr<HashMap> HashMap::Open(StructStream &stream)
{
	auto num_entries = *stream.Extract<std::size_t>();
	auto max_key_size = *stream.Extract<std::size_t>();
	auto value_size = *stream.Extract<std::size_t>();
	auto data = stream.Extract<char>(CalculateEntrySize(max_key_size, value_size) * num_entries);

	return std::shared_ptr<HashMap>(new HashMap(data, num_entries, max_key_size, value_size, stream.GetBuffer()));
}

void *HashMap::Insert(std::string_view key, const void *value)
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

			// Copy the value, if given.
			void *new_value = GetValue(probe);

			if (value)
				std::memcpy(new_value, value, m_ValueSize);

			// Make occupied.
			entry_flags->store(EntryFlags::OCCUPIED, std::memory_order_release);

			return new_value;
		}
	}

	// Map is full.
	return nullptr;
}

void *HashMap::Find(std::string_view key) const
{
	if (key.size() >= m_MaxKeySize)
	{
		DEBUG_PRINT("HashMap::Find: Key is too long");

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

	DEBUG_PRINT("HashMap::Find: Key not found: (key = \"" << key << "\", size = " << key.size() << ")");
	DEBUG_PRINT("Key in hex: " << string_view_to_hex(key));

	// Key not found.
	return nullptr;
}

std::vector<std::string> HashMap::GetAllKeys() const
{
	std::vector<std::string> res;

	for (size_t i = 0; i < m_NumEntries; ++i)
	{
		EntryFlags flags = GetFlagsRef(i)->load(std::memory_order_relaxed);

		if (flags == EntryFlags::OCCUPIED)
			res.push_back(std::string(GetKey(i)));
	}

	return res;
}

size_t HashMap::GetCapacity() const
{
	return m_NumEntries;
}

ShareableType HashMap::GetType() const
{
	return ShareableType::HashMap;
}