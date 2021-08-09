#include "DataStream.h"

//#include "Log.h"
#include "TimeStamp.h"

#include <algorithm>

using namespace std;

const char *GetDataTypeAsString(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
			return "uint8";
		case DataType::DT_UINT16:
			return "uint16";
		case DataType::DT_UINT32:
			return "uint32";
		case DataType::DT_UINT64:
			return "uint64";
		case DataType::DT_INT8:
			return "int8";
		case DataType::DT_INT16:
			return "int16";
		case DataType::DT_INT32:
			return "int32";
		case DataType::DT_INT64:
			return "int64";
		case DataType::DT_FLOAT32:
			return "float32";
		case DataType::DT_FLOAT64:
			return "float64";
		case DataType::DT_FLOAT128:
			return "float128";
		case DataType::DT_COMPLEX64:
			return "complex64";
		case DataType::DT_COMPLEX128:
			return "complex128";
		default:
			return "unknown";
	}
}

DataType GetDataTypeFromString(const char *type)
{
	return GetDataTypeFromString(string(type));
}

DataType GetDataTypeFromString(string type)
{
	if (type == "uint8")
		return DataType::DT_UINT8;
	if (type == "uint16")
		return DataType::DT_UINT16;
	if (type == "uint32")
		return DataType::DT_UINT32;
	if (type == "uint64")
		return DataType::DT_UINT64;
	if (type == "int8")
		return DataType::DT_INT8;
	if (type == "int16")
		return DataType::DT_INT16;
	if (type == "int32")
		return DataType::DT_INT32;
	if (type == "int64")
		return DataType::DT_INT64;
	if (type == "float32")
		return DataType::DT_FLOAT32;
	if (type == "float64")
		return DataType::DT_FLOAT64;
	if (type == "float128")
		return DataType::DT_FLOAT128;
	if (type == "complex64")
		return DataType::DT_COMPLEX64;
	if (type == "complex128")
		return DataType::DT_COMPLEX128;
	return DataType::DT_UNKNOWN;
}

size_t GetSizeOfDataType(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
		case DataType::DT_INT8:
			return 1;
		case DataType::DT_UINT16:
		case DataType::DT_INT16:
			return 2;
		case DataType::DT_UINT32:
		case DataType::DT_INT32:
		case DataType::DT_FLOAT32:
			return 4;
		case DataType::DT_UINT64:
		case DataType::DT_INT64:
		case DataType::DT_FLOAT64:
		case DataType::DT_COMPLEX64:
			return 8;
		case DataType::DT_FLOAT128:
		case DataType::DT_COMPLEX128:
			return 16;
		default:
			return 0;
	}
}

DataStream::DataStream(HANDLE file_mapping, HANDLE frame_written)
	: m_FileMapping(file_mapping), m_FrameWritten(frame_written),
	m_Header(nullptr), m_RawData(nullptr),
	m_NextFrameIdToRead(0),
	m_BufferHandlingMode(BM_NEWEST_ONLY)
{
	void *buffer = MapViewOfFile(m_FileMapping, FILE_MAP_ALL_ACCESS, 0, 0, 0);

	if (!buffer)
	{
		// Something went wrong with the memory mapping.
		return;
	}

	m_Header = (DataStreamHeader *) buffer;
	m_RawData = ((char *)buffer) + sizeof(DataStreamHeader);
}

DataStream::~DataStream()
{
	CloseHandle(m_FrameWritten);

	UnmapViewOfFile(m_Header);
	CloseHandle(m_FileMapping);
}

std::shared_ptr<DataStream> DataStream::Create(std::string name, DataType type, std::initializer_list<size_t> dimensions, size_t num_frames_in_buffer)
{
	if (dimensions.size() > 4)
	{
		// Too many dimensions.
		return nullptr;
	}

	size_t num_elements = 1;
	for (auto d : dimensions)
	{
		num_elements *= d;
	}

	size_t num_bytes_per_frame = num_elements * GetSizeOfDataType(type) * num_frames_in_buffer;
	size_t num_bytes = sizeof(DataStreamHeader) + num_bytes_per_frame;

	HANDLE file_mapping = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, (DWORD) num_bytes, name.c_str());
	HANDLE semaphore = CreateSemaphore(NULL, 0, 9999, (name + "_sem").c_str());

	auto data_stream = std::shared_ptr<DataStream>(new DataStream(file_mapping, semaphore));
	auto header = data_stream->m_Header;

	strcpy(header->m_Version, CURRENT_VERSION);

	strcpy(header->m_Name, name.c_str());
	header->m_TimeCreated = GetTimeStamp();
	header->m_CreatorPID = GetCurrentProcessId();

	header->m_DataType = type;
	size_t *dims = header->m_Dimensions;
	fill(dims, dims + 4, 1);
	copy(dimensions.begin(), dimensions.end(), dims);

	header->m_NumBytesPerFrame = num_bytes_per_frame;
	header->m_NumBytesInBuffer = num_bytes_per_frame * GetSizeOfDataType(type);
	header->m_NumFramesInBuffer = num_frames_in_buffer;

	header->m_FirstId = 0;
	header->m_LastId = 0;
	header->m_NextRequestId = 0;

	header->m_NumReadersWaiting = 0;

	return data_stream;
}

std::shared_ptr<DataStream> DataStream::Open(std::string name)
{
	HANDLE file_mapping = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, name.c_str());
	HANDLE semaphore = OpenSemaphore(NULL, FALSE, (name + "_sem").c_str());

	auto data_stream = std::shared_ptr<DataStream>(new DataStream(file_mapping, semaphore));

	if (!strcmp(data_stream->m_Header->m_Version, CURRENT_VERSION))
	{
		// DataStreams were made with different versions.
		return nullptr;
	}

	// Don't read frames that already are available at the time the data stream is opened.
	data_stream->m_NextFrameIdToRead = data_stream->m_Header->m_LastId;

	return data_stream;
}

DataFrame *DataStream::RequestNewFrame()
{
	// If the frame buffer is full: make oldest frame unavailable.
	if ((m_Header->m_LastId - m_Header->m_FirstId) == m_Header->m_NumFramesInBuffer)
		m_Header->m_FirstId++;

	size_t new_frame_id = m_Header->m_NextRequestId++;

	// Get right frame and clean it
	DataFrame *frame = m_Header->m_Frames + (new_frame_id % m_Header->m_NumFramesInBuffer);
	frame->m_Id = new_frame_id;
	frame->m_Offset = (new_frame_id % m_Header->m_NumFramesInBuffer) * m_Header->m_NumBytesPerFrame;

	return frame;
}

void DataStream::SubmitFrame(size_t id)
{
	// Add timing information to frame.
	DataFrame *frame = m_Header->m_Frames + (id % m_Header->m_NumFramesInBuffer);
	frame->m_TimeStamp = GetTimeStamp();

	// Make frame available.
	m_Header->m_LastId++;

	// Notify waiting processes.
	size_t num_readers_waiting = m_Header->m_NumReadersWaiting.exchange(0);
	ReleaseSemaphore(m_FrameWritten, (LONG) num_readers_waiting, NULL);
}

size_t *DataStream::GetDimensions()
{
	return m_Header->m_Dimensions;
}

DataType DataStream::GetDataType()
{
	return m_Header->m_DataType;
}

size_t DataStream::GetNumFramesInBuffer()
{
	return m_Header->m_NumFramesInBuffer;
}

size_t DataStream::GetNumElementsPerFrame()
{
	return m_Header->m_NumElementsPerFrame;
}

size_t DataStream::GetNumDimensions()
{
	size_t num_dimensions = 4;

	while (m_Header->m_Dimensions[num_dimensions - 1] == 1 && num_dimensions > 1)
		num_dimensions--;

	return num_dimensions;
}

DataFrame *DataStream::GetFrame(size_t id, bool wait)
{
	if (!IsFrameAvailable(id))
	{
		if (!WillFrameBeAvailable(id))
			return nullptr;

		if (!wait)
			return nullptr;

		while (m_Header->m_LastId <= id)
		{
			m_Header->m_NumReadersWaiting++;
			WaitForSingleObject(m_FrameWritten, INFINITE);
		}
	}

	return m_Header->m_Frames + id % m_Header->m_NumFramesInBuffer;
}

bool DataStream::IsFrameAvailable(size_t id)
{
	return (id >= m_Header->m_FirstId) && (id < m_Header->m_LastId);
}

bool DataStream::WillFrameBeAvailable(size_t id)
{
	return id >= m_Header->m_FirstId;
}

size_t DataStream::GetOldestAvailableFrameId()
{
	return m_Header->m_FirstId;
}

size_t DataStream::GetNewestAvailableFrameId()
{
	return m_Header->m_LastId - 1;
}
