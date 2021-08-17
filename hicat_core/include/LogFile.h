#ifndef LOGFILE_H
#define LOGFILE_H

#include "Log.h"

#include <fstream>

class LogFile : public LogListener
{
public:
    LogFile(const char *filename);

    void AddLogEntry(const LogEntry &entry);

private:
    std::ofstream m_File;
};

#endif // LOGFILE_H