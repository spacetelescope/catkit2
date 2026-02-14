#ifndef REMOTE_MESSAGE_BROKER_H
#define REMOTE_MESSAGE_BROKER_H

#include "MessageBroker.h"
#include "LocalMessageBroker.h"
#include "Client.h"
#include "Server.h"

#include <string>
#include <unordered_map>
#include <vector>
#include <memory>

struct PeerConfig
{
	std::string name;
	std::string host;
	int port;

	PeerConfig() = default;
	PeerConfig(std::string name_, std::string host_, int port_)
		: name(std::move(name_)), host(std::move(host_)), port(port_) {}
};

class RemoteMessageBroker : public MessageBroker
{
public:
	RemoteMessageBroker(std::shared_ptr<LocalMessageBroker> local_broker,
	                    const std::string& local_machine_name,
	                    const std::vector<PeerConfig>& peers);

	virtual ~RemoteMessageBroker();

	// MessageBroker interface
	virtual Message PrepareMessageImpl(std::string_view topic, size_t payload_size,
	                                   Uuid trace_id, uint8_t memory_block_id = 0) override;
	virtual Message PublishMessage(Message message, bool is_final = true) override;
	virtual std::optional<Message> GetCurrentMessage(std::string_view topic) override;
	virtual std::optional<Message> GetNextMessage(std::string_view topic,
	                                               size_t preferred_next_frame_id,
	                                               MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly,
	                                               double timeout_in_seconds = -1,
	                                               EventWaitMethod wait_type = EventWaitMethod::Default,
	                                               void (*error_check)() = nullptr) override;
	virtual std::optional<Message> TryGetNextMessage(std::string_view topic,
	                                                  size_t preferred_next_frame_id,
	                                                  MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly) override;
	virtual std::vector<std::string> GetAllMessageTopics() override;
	virtual double GetMessageRate(std::string_view topic) override;

private:
	std::shared_ptr<LocalMessageBroker> m_LocalBroker;
	std::string m_LocalMachineName;
	std::unordered_map<std::string, std::unique_ptr<Client>> m_PeerClients;

	bool IsLocalTopic(std::string_view topic);
	std::string GetMachineFromTopic(std::string_view topic);
	Client& GetClientForMachine(const std::string& machine);

	// Serialization helpers for peer communication
	std::string SerializeMessage(const Message& msg);
	std::string SerializeGetNextRequest(const std::string& topic, uint64_t frame_id,
	                                    int mode, double timeout);
};

class RemoteBrokerServer
{
public:
	RemoteBrokerServer(std::shared_ptr<LocalMessageBroker> broker, uint16_t port, int num_workers = 4);
	~RemoteBrokerServer();

	void Start();
	void Stop();

	bool IsRunning() const;

private:
	std::shared_ptr<LocalMessageBroker> m_Broker;
	Server m_Server;

	// Request handlers
	std::string HandlePublish(const std::string& request_data);
	std::string HandleGetNext(const std::string& request_data);
	std::string HandleGetCurrent(const std::string& request_data);
	std::string HandleGetRate(const std::string& request_data);
	std::string HandleListTopics(const std::string& request_data);
};

#endif // REMOTE_MESSAGE_BROKER_H
