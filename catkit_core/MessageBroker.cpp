#include "MessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>

TopicHeader::TopicHeader(const TopicHeader &header)
{
	CopyFrom(header);
}

TopicHeader &TopicHeader::operator=(const TopicHeader &header)
{
	CopyFrom(header);

	return *this;
}

void TopicHeader::CopyFrom(const TopicHeader &header)
{
	next_frame_id.store(header.next_frame_id.load(std::memory_order_relaxed), std::memory_order_relaxed);
	synchronization = header.synchronization;

	std::copy(header.message_offsets, header.message_offsets + TOPIC_MAX_NUM_MESSAGES, message_offsets);
	std::copy((char *)header.metadata_keys, (char *)header.metadata_keys + sizeof(metadata_keys), (char *)metadata_keys);
}
