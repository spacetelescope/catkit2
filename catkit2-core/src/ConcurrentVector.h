#ifndef CONCURRENT_VECTOR_H
#define CONCURRENT_VECTOR_H

#include "Util.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <cassert>
#include <climits>

template <typename T, size_t MaxSegments = 32>
class ConcurrentVector
{
public:
	ConcurrentVector();
	~ConcurrentVector();

	size_t PushBack(const T& value);
	T &operator[](size_t index) const;

	size_t Size() const;
private:
	std::atomic<size_t> m_Size;
	std::atomic<T*> m_Segments[MaxSegments];

	void EnsureSegmentExists(size_t seg);

	static constexpr size_t SegmentSize(size_t seg);
	static constexpr std::pair<size_t, size_t> Locate(size_t index);
};

#include "ConcurrentVector.inl"

#endif // CONCURRENT_VECTOR_H
