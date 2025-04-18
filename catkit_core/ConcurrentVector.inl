#include "ConcurrentVector.h"

template <typename T, size_t MaxSegments>
ConcurrentVector<T, MaxSegments>::ConcurrentVector()
	: m_Size(0)
{
	for (size_t i = 0; i < MaxSegments; ++i)
	{
		m_Segments[i].store(nullptr, std::memory_order_relaxed);
	}
}

template <typename T, size_t MaxSegments>
ConcurrentVector<T, MaxSegments>::~ConcurrentVector()
{
	for (size_t i = 0; i < MaxSegments; ++i)
	{
		T* ptr = m_Segments[i].load(std::memory_order_relaxed);

		if (ptr)
		{
			delete[] ptr;
		}
	}
}

template <typename T, size_t MaxSegments>
size_t ConcurrentVector<T, MaxSegments>::PushBack(const T& value)
{
	size_t index = m_Size.fetch_add(1, std::memory_order_relaxed);

	auto [seg, offset] = Locate(index);
	EnsureSegmentExists(seg);

	m_Segments[seg].load(std::memory_order_relaxed)[offset] = value;

	return index;
}

template <typename T, size_t MaxSegments>
T &ConcurrentVector<T, MaxSegments>::operator[](size_t index) const
{
	auto [seg, offset] = locate(index);

	T* segment = m_Segments[seg].load(std::memory_order_relaxed);

	return segment[offset];
}

template <typename T, size_t MaxSegments>
size_t ConcurrentVector<T, MaxSegments>::Size() const
{
	return m_Size.load(std::memory_order_relaxed);
}

template <typename T, size_t MaxSegments>
void ConcurrentVector<T, MaxSegments>::EnsureSegmentExists(size_t seg)
{
	if (m_Segments[seg].load(std::memory_order_relaxed) == nullptr)
	{
		size_t seg_size = segment_size(seg);

		T* new_segment = new T[seg_size];
		T* expected = nullptr;

        // Ensure that the segment is not already created by another thread.
		if (!m_Segments[seg].compare_exchange_strong(expected, new_segment, std::memory_order_release, std::memory_order_relaxed))
			delete[] new_segment;
	}
}

template <typename T, size_t MaxSegments>
constexpr size_t ConcurrentVector<T, MaxSegments>::SegmentSize(size_t seg)
{
	return 1ull << seg;
}

template <typename T, size_t MaxSegments>
constexpr std::pair<size_t, size_t> ConcurrentVector<T, MaxSegments>::Locate(size_t index)
{
	size_t seg = bit_width(index + 1) - 1;
	size_t base = (1ull << seg) - 1;

	return {seg, index - base};
}
