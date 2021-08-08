#include "DataStream.h"

#include "Log.h"
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

size_t DataFrame::GetSize()
{
	return dimensions[0] * dimensions[1] * dimensions[2] * dimensions[3];
}

size_t DataFrame::GetSizeInBytes()
{
	return GetSize() * GetSizeOfDataType(type);
}

size_t DataFrame::GetNumDimensions()
{
	size_t num_dimensions = 4;

	while (dimensions[num_dimensions - 1] == 1 && num_dimensions > 1)
		num_dimensions--;

	return num_dimensions;
}

DataStream::DataStream(size_t num_frames_in_buffer)
	: m_RawData(nullptr), m_Frames(nullptr),
	m_FirstId(0), m_LastId(0), m_NumFramesInBuffer(num_frames_in_buffer),
	m_Dimensions({1,1,1,1}), m_DataType(DataType::DT_UINT8)
{
	UpdateBuffers(true);
}

DataStream::~DataStream()
{
	for (auto &link : m_Links)
	{
		if (link->GetInputPort())
			link->GetInputPort()->RemoveLink(link);
	}

	if (m_RawData)
		delete[] m_RawData;

	if (m_Frames)
		delete[] m_Frames;
}

std::array<size_t, 4> DataStream::GetDimensions()
{
	return m_Dimensions;
}

DataType DataStream::GetDataType()
{
	return m_DataType;
}

size_t DataStream::GetFrameSize()
{
	return m_Dimensions[0] * m_Dimensions[1] * m_Dimensions[2] * m_Dimensions[3];
}

size_t DataStream::GetNumDimensions()
{
	size_t num_dimensions = m_Dimensions.size();

	while (m_Dimensions[num_dimensions - 1] == 1 && num_dimensions > 1)
		num_dimensions--;

	return num_dimensions;
}

void DataStream::SetDimensions(initializer_list<size_t> dimensions)
{
	auto last = copy(dimensions.begin(), dimensions.end(), m_Dimensions.begin());
	fill(last, m_Dimensions.end(), 1);

	UpdateBuffers();
}

void DataStream::SetDimensions(array<size_t, 4> dimensions)
{
	m_Dimensions = dimensions;

	UpdateBuffers();
}

void DataStream::SetDimensions(size_t *dimensions)
{
	copy(dimensions, dimensions + 4, m_Dimensions.begin());

	UpdateBuffers();
}

void DataStream::SetDimensions(size_t d1, size_t d2, size_t d3, size_t d4)
{
	m_Dimensions[0] = d1;
	m_Dimensions[1] = d2;
	m_Dimensions[2] = d3;
	m_Dimensions[3] = d4;

	UpdateBuffers();
}

void DataStream::SetDataType(DataType type)
{
	m_DataType = type;

	UpdateBuffers();
}

void DataStream::UpdateBuffers(bool force)
{
	// Check if buffer update is necessary
	size_t num_bytes_per_frame = GetFrameSize() * GetSizeOfDataType(m_DataType);
	if (num_bytes_per_frame == m_NumBytesPerFrame)
		return;

	if (num_bytes_per_frame <= m_NumBytesPerFrame
		&& num_bytes_per_frame >= m_NumBytesPerFrame / 4
		&& !force)
	{
		// Update is not needed; do nothing.
		return;
	}

	// Delete all frames
	m_FirstId = m_LastId.load();

	// Deallocate memory
	if (m_Frames)
		delete[] m_Frames;

	if (m_RawData)
		delete[] m_RawData;

	// Allocate memory
	m_RawData = new char[num_bytes_per_frame * m_NumFramesInBuffer];
	m_Frames = new DataFrame[m_NumFramesInBuffer];

	// Add data to frames
	for (size_t i = 0; i < m_NumFramesInBuffer; ++i)
		m_Frames[i].raw_data = m_RawData + num_bytes_per_frame * i;

	m_NumBytesPerFrame = num_bytes_per_frame;
}

// TODO: potential race condition: submitframe during request new frame may duplicate frames
DataFrame *DataStream::RequestNewFrame()
{
	if (!m_Frames)
	{
		LOG_ERROR("Frame buffer is empty.");
		return nullptr;
	}

	// Make old frame unavailable if frame buffer is full
	if ((m_LastId - m_FirstId) == m_NumFramesInBuffer)
		m_FirstId++;

	// Get right frame and clean it
	DataFrame *frame = m_Frames + (m_LastId % m_NumFramesInBuffer);
	frame->id = m_LastId;

	// Set frame data
	frame->type = m_DataType;
	copy(m_Dimensions.begin(), m_Dimensions.end(), frame->dimensions);

	return frame;
}

void DataStream::SubmitFrame(size_t id)
{
	static TimeDelta time_delta;

	// Get timing of this frame.
	uint64_t time_stamp = GetTimeStamp();
	double time_since_last_frame = time_delta.GetTimeDelta();

	// Add timing information to frame.
	DataFrame *frame = m_Frames + (id % m_NumFramesInBuffer);
	frame->time_stamp = time_stamp;
	frame->time_delta = time_since_last_frame;

	// Make frame available.
	m_LastId++;
}

bool DataStream::WouldNewFrameDestroyOldFrames()
{
	return (m_LastId - m_FirstId) == m_NumFramesInBuffer;
}

void DataStream::MakeFrameUnavailable(size_t id)
{
	if (!IsFrameAvailable(id))
		return;

	m_FirstId = id + 1;
}

size_t DataStream::GetNumFramesInBuffer()
{
	return m_NumFramesInBuffer;
}

DataFrame *DataStream::GetFrame(size_t id)
{
	if (!IsFrameAvailable(id))
		return nullptr;

	return m_Frames + id % m_NumFramesInBuffer;
}

DataFrame *DataStream::GetLastAvailableFrame()
{
	size_t id = GetLastAvailableFrameId();
	return GetFrame(id);
}

bool DataStream::IsFrameAvailable(size_t id)
{
	return (id >= m_FirstId) && (id < m_LastId);
}

bool DataStream::WillFrameBeAvailable(size_t id)
{
	return id >= m_FirstId;
}

size_t DataStream::GetLastAvailableFrameId()
{
	return m_LastId - 1;
}