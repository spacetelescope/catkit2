#ifndef DATASTREAM_H
#define DATASTREAM_H

#include <functional>
#include <map>
#include <memory>
#include <atomic>
#include <vector>

#include <windows.h>

#include "ComplexTraits.h"

const char *CURRENT_VERSION = "0.1";
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

struct DataFrameMetadata
{
	std::uint64_t m_TimeStamp;
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

	size_t m_NumBytesInBuffer;

	size_t m_NumFramesInBuffer;
	DataFrameMetadata m_FrameMetadata[MAX_NUM_FRAMES_IN_BUFFER];

	std::atomic_size_t m_FirstId;
	std::atomic_size_t m_LastId;
	std::atomic_size_t m_NextRequestId;

	std::atomic_size_t m_NumReadersWaiting;
};

struct DataFrame
{
	size_t m_Id;
	std::uint64_t m_TimeStamp;

	DataType m_DataType;
	size_t m_Dimensions[4];

	char *m_Data;
};

enum BufferHandlingMode
{
	BM_NEWEST_ONLY,
	BM_OLDEST_FIRST_OVERWRITE
};

class DataStream
{
private:
	DataStream(HANDLE file_mapping, HANDLE semaphore);

public:
	~DataStream();

	static std::shared_ptr<DataStream> Create(std::string name, DataType type, std::initializer_list<size_t> dimensions, size_t num_frames_in_buffer);
	static std::shared_ptr<DataStream> Open(std::string name);

	DataFrame RequestNewFrame();
	void SubmitFrame(size_t id);

	size_t *GetDimensions();
	DataType GetDataType();

	size_t GetNumFramesInBuffer();
	size_t GetNumElementsPerFrame();
	size_t GetNumDimensions();

	DataFrame GetFrame(size_t id, bool wait=true);
	DataFrame GetNextFrame(bool wait=true);

	bool IsFrameAvailable(size_t id);
	bool WillFrameBeAvailable(size_t id);

	size_t GetNewestAvailableFrameId();
	size_t GetOldestAvailableFrameId();

private:
	HANDLE m_FileMapping;
	HANDLE m_FrameWritten;

	DataStreamHeader *m_Header;
	char *m_Buffer;

	size_t m_NextFrameIdToRead;
	BufferHandlingMode m_BufferHandlingMode;
};

#include "DataStream.inl"

#endif // DATASTREAM_H
