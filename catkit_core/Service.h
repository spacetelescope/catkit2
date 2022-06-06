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
#include "Communication.h"

const double SERVICE_LIVELINESS = 10;

class TestbedProxy;

class Service : public Server
{
public:
	Service(std::string service_id, std::string service_type, int service_port, int testbed_port);
	virtual ~Service();

	void Run();

	virtual void Open();
	virtual void Main();
	virtual void Close();

	std::shared_ptr<Property> GetProperty(const std::string &property_name) const;
	std::shared_ptr<Command> GetCommand(const std::string &command_name) const;
	std::shared_ptr<DataStream> GetDataStream(const std::string &stream_name) const;

	nlohmann::json GetConfig() const;
	const std::string &GetId() const;

	std::shared_ptr<Property> MakeProperty(std::string property_name, Property::Getter getter, Property::Setter setter = nullptr);
	std::shared_ptr<Command> MakeCommand(std::string command_name, Command::CommandFunction func);
	std::shared_ptr<DataStream> MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);
	std::shared_ptr<DataStream> ReuseDataStream(std::string stream_name, std::string stream_id);

private:
	std::string HandleGetInfo(const std::string &data);

	std::string HandleGetProperty(const std::string &data);
	std::string HandleSetProperty(const std::string &data);

	std::string HandleExecuteCommand(const std::string &data);

	void MonitorSafety();
	bool IsSafe();

	void MonitorHeartbeats();

	std::shared_ptr<TestbedProxy> m_Testbed;

	std::string m_ServiceId;
	std::string m_ServiceType;

	nlohmann::json m_Config;

	std::shared_ptr<DataStream> m_ServiceHeartbeat;
	std::shared_ptr<DataStream> m_ServerHeartbeat;
	std::shared_ptr<DataStream> m_Safety;

	typedef std::function<std::string(const std::string &)> MessageHandler;
	std::map<std::string, MessageHandler> m_RequestHandlers;

	std::map<std::string, std::shared_ptr<Property>> m_Properties;
	std::map<std::string, std::shared_ptr<Command>> m_Commands;
	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;

	LogConsole m_LoggerConsole;
	LogPublish m_LoggerPublish;
};

std::tuple<std::string, int, int> ParseServiceArgs(int argc, char *argv[]);

#endif // SERVICE_H
