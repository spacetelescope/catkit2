#ifndef DATASTREAM_H
#define DATASTREAM_H

#include <functional>
#include <map>
#include <memory>
#include <atomic>
#include <vector>

#include "ComplexTraits.h"

const size_t MAX_NUM_FRAMES_IN_BUFFER = 20;

enum class DataType
{
	DT_UINT8 = 0,
	DT_UINT16,
	DT_UINT32,
	DT_UINT64,
	DT_INT8,
	DT_INT16,
	DT_INT32,
	DT_INT64,
	DT_FLOAT32,
	DT_FLOAT64,
	DT_FLOAT128,
	DT_COMPLEX64,
	DT_COMPLEX128,
	DT_UNKNOWN
};

template<typename T>
constexpr DataType GetDataType();

template<typename T>
constexpr const char *GetDataTypeAsString();

const char *GetDataTypeAsString(DataType type);

DataType GetDataTypeFromString(const char *type);
DataType GetDataTypeFromString(std::string type);

size_t GetSizeOfDataType(DataType type);

struct DataFrame
{
	size_t m_Id;

	std::uint64_t m_TimeStamp;
	double m_TimeDelta;

	size_t m_Offset;
};

struct DataStreamHeader
{
	char m_Version[32];

	char m_Name[256];
	std::uint64_t m_TimeCreated;
	unsigned long m_CreatorPID;

	DataType m_DataType;
	size_t m_Dimensions[4];

	size_t m_NumElementsPerFrame;
	size_t m_NumBytesPerFrame;

	size_t m_NumFramesInBuffer;
	DataFrame m_Frames[MAX_NUM_FRAMES_IN_BUFFER];

	std::atomic_size_t m_FirstId;
	std::atomic_size_t m_LastId;

	std::mutex m_FrameWrittenMutex;
	std::condition_variable m_FrameWritten;
};

class DataStream
{
private:
	DataStream(size_t num_frames_in_buffer=2);

public:
	~DataStream();

	static Create(std::string name, DataType type, std::initializer_list<size_t> dimensions, size_t num_frames_in_buffer);
	static Open(std::string name);

	DataFrame *RequestNewFrame();
	void SubmitFrame(size_t id);

	bool WouldNewFrameDestroyOldFrames();
	void MakeFrameUnavailable(size_t id);

	std::array<size_t, 4> GetDimensions();
	DataType GetDataType();

	size_t GetNumFramesInBuffer();
	size_t GetFrameSize();
	size_t GetNumDimensions();

	void SetDimensions(std::initializer_list<size_t> dimensions);
	void SetDimensions(std::array<size_t, 4> dimensions);
	void SetDimensions(size_t *dimensions);
	void SetDimensions(size_t d1, size_t d2=1, size_t d3=1, size_t d4=1);
	void SetDataType(DataType type);
	void SetNumFramesInBuffer(size_t num_frames_in_buffer);

	void UpdateBuffers(bool force=false);

	DataFrame *GetFrame(size_t id);
	DataFrame *GetLastAvailableFrame();

	bool IsFrameAvailable(size_t id);
	bool WillFrameBeAvailable(size_t id);

	size_t GetNewestAvailableFrameId();
	size_t GetOldestAvailableFrameId();

private:
	DataStreamHeader *m_Header;
	char *m_RawData;

	size_t m_NextFrameIdToRead;
	BufferReadingMode m_BufferReadingMode;
};

#include "DataStream.inl"

#endif // DATASTREAM_H
