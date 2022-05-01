#ifndef SERVICE_H
#define SERVICE_H

#include <vector>
#include <string>
#include <map>
#include <thread>

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include "Property.h"
#include "Command.h"
#include "DataStream.h"
#include "LogConsole.h"
#include "LogPublish.h"

class Service
{
public:
	Service(std::string service_name, int testbed_port);
	virtual ~Service();

	void Run();

	virtual void Open();
	virtual void Main();
	virtual void Close();

	virtual void ShutDown();

	std::shared_ptr<Property> GetProperty(const std::string &property_name) const;
	std::shared_ptr<Command> GetCommand(const std::string &command_name) const;
	std::shared_ptr<DataStream> GetDataStream(const std::string &stream_name) const;

	nlohmann::json GetConfig() const;
	const std::string &GetName() const;

	std::shared_ptr<Property> MakeProperty(std::string property_name, Property::Getter getter, Property::Setter setter = nullptr);
	std::shared_ptr<Command> MakeCommand(std::string command_name, Command::CommandFunction func);
	std::shared_ptr<DataStream> MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);
	std::shared_ptr<DataStream> ReuseDataStream(std::string stream_name, std::string stream_id);

private:
	void MonitorInterface();

	nlohmann::json OnGetPropertyRequest(const nlohmann::json &data);
	nlohmann::json OnSetPropertyRequest(const nlohmann::json &data);

	nlohmann::json OnExecuteCommandRequest(const nlohmann::json &data);

	nlohmann::json OnGetDataStreamInfoRequest(const nlohmann::json &data);

	nlohmann::json OnAllPropertiesRequest(const nlohmann::json &data);
	nlohmann::json OnAllCommandsRequest(const nlohmann::json &data);
	nlohmann::json OnAllDataStreamsRequest(const nlohmann::json &data);

	nlohmann::json OnShutdownRequest(const nlohmann::json &data);

	void SendReplyMessage(const std::string &client_identity, const nlohmann::json &reply);
	void SendReplyOk(const std::string &client_identity, const std::string &reply_type, const nlohmann::json &data);
	void SendReplyError(const std::string &client_identity, const std::string &reply_type, const std::string &error_description);

    void RegisterWithServer();
    void HandleHeartbeat();

	zmq::context_t m_Context;
	zmq::socket_t *m_ShellSocket;
	zmq::socket_t *m_ServerSocket;

	std::string m_ServiceName;
	std::string m_ServiceType;
	int m_ServerPort;
    int m_ServicePort;

	// Whether the shell interface is running.
	bool m_IsRunning;

	// Whether the service is open or not.
	bool m_IsOpened;

	nlohmann::json m_Configuration;
	bool m_HasGottenConfiguration;

	uint64_t m_LastSentHeartbeatTime;
	uint64_t m_LastReceivedHeartbeatTime;

	std::shared_ptr<DataStream> m_ServiceHeartbeat;
    std::shared_ptr<DataStream> m_ServerHeartbeat;

	std::thread m_InterfaceThread;

	typedef std::function<nlohmann::json(const nlohmann::json &)> MessageHandler;
	std::map<std::string, MessageHandler> m_RequestHandlers;

	std::map<std::string, std::shared_ptr<Property>> m_Properties;
	std::map<std::string, std::shared_ptr<Command>> m_Commands;
	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;

	LogConsole m_LoggerConsole;
	LogPublish m_LoggerPublish;
};

std::tuple<std::string, int> ParseServiceArgs(int argc, char *argv[]);

#endif // SERVICE_H
