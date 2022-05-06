#ifndef TRACING_PROXY_H
#define TRACING_PROXY_H

#include <thread>

class TracingProxy
{
public:
    TracingProxy(int tracing_port, std::shared_ptr<TestbedProxy> testbed);
    ~TracingProxy();

    void TraceBegin(std::string func, std::string what);
    void TraceEnd(std::string func);

    void TraceInterval(std::string func, std::string what, uint64_t timestamp_start, uint64_t timestamp_end);

    void TraceCounter(std::string func, double counter);

    void TraceProcessName(std::string process_name);
    void TraceThreadName(std::string thread_name);

private:
    void SendTraceMessage(std::string contents);

    static std::map<std::thread::id, int> m_ThreadIds;

    zmq::context_t m_Context;

    std::string m_Host;
    int m_Port;
};

#endif // TRACING_PROXY_H
