# flake8: noqa

# This module is a modified version of the original FWxC_COMMAND_LIB.py file from the Thorlabs FW102C filter wheel SDK v5.0.0

# The Thorlabs FW102C filter wheel SDK is available at https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=FW102C
# The original FWxC_COMMAND_LIB.py file is located at c://Program Files (x86)//Thorlabs//FWxC//Sample//Thorlabs_FWxC_PythonSDK
# The original FWxC_COMMAND_LIB.py file loads the FilterWheel102_win32.dll file instead of the FilterWheel102_win64.dll file
# modified by: Arnaud Sevin <Arnaud.Sevin@obspm.fr>


from ctypes import *

import os
os.add_dll_directory("c://Program Files (x86)//Thorlabs//FWxC//Sample//Thorlabs_FWxC_C++SDK")

#region import dll functions
FWxCLib = cdll.LoadLibrary("FilterWheel102_win64.dll")

"""common command
"""
List = FWxCLib.List
List.restype = c_int
List.argtypes = [c_char_p, c_uint]

Open = FWxCLib.Open
Open.restype = c_int
Open.argtypes = [c_char_p,c_int,c_int]

IsOpen = FWxCLib.IsOpen
IsOpen.restype = c_int
IsOpen.argtypes = [c_char_p]

Close = FWxCLib.Close
Close.restype = c_int
Close.argtypes = [c_int]

"""device command
"""
SetPosition = FWxCLib.SetPosition
SetPosition.restype = c_int
SetPosition.argtypes = [c_int,c_int]

SetPositionCount = FWxCLib.SetPositionCount
SetPositionCount.restype = c_int
SetPositionCount.argtypes = [c_int,c_int]

SetSpeedMode = FWxCLib.SetSpeedMode
SetSpeedMode.restype = c_int
SetSpeedMode.argtypes = [c_int,c_int]

SetTriggerMode = FWxCLib.SetTriggerMode
SetTriggerMode.restype = c_int
SetTriggerMode.argtypes = [c_int,c_int]

SetSensorMode = FWxCLib.SetSensorMode
SetSensorMode.restype = c_int
SetSensorMode.argtypes = [c_int,c_int]

Save = FWxCLib.Save
Save.restype = c_int
Save.argtypes = [c_int]

GetId = FWxCLib.GetId
GetId.restype = c_int
GetId.argtypes = [c_int,c_char_p]

GetPosition = FWxCLib.GetPosition
GetPosition.restype = c_int
GetPosition.argtypes = [c_int,POINTER(c_int)]

GetPositionCount = FWxCLib.GetPositionCount
GetPositionCount.restype = c_int
GetPositionCount.argtypes = [c_int,POINTER(c_int)]

GetSpeedMode = FWxCLib.GetSpeedMode
GetSpeedMode.restype = c_int
GetSpeedMode.argtypes = [c_int,POINTER(c_int)]

GetTriggerMode = FWxCLib.GetTriggerMode
GetTriggerMode.restype = c_int
GetTriggerMode.argtypes = [c_int,POINTER(c_int)]

GetSensorMode = FWxCLib.GetSensorMode
GetSensorMode.restype = c_int
GetSensorMode.argtypes = [c_int,POINTER(c_int)]


#region command for FWxC
def FWxCListDevices():
    """ List all connected FWxC devices
    Returns: 
       The FWxC device list, each deice item is [serialNumber, FWxCType]
    """
    str = create_string_buffer(1024, '\0') 
    result = List(str,1024)
    devicesStr = str.raw.decode("utf-8").rstrip('\x00').split(',')
    length = len(devicesStr)
    i = 0
    devices = []
    devInfo = ["",""]
    while(i < length):
        str = devicesStr[i]
        if (i % 2 == 0):
            if str != '':
                devInfo[0] = str
            else:
                i+=1
        else:
                if(str.find("FWxC") >= 0):
                    isFind = True
                devInfo[1] = str
                devices.append(devInfo.copy())
        i+=1
    return devices


def FWxCOpen(serialNo, nBaud, timeout):
    """ Open FWxC device
    Args:
        serialNo: serial number of FWxC device
        nBaud: bit per second of port
        timeout: set timeout value in (s)
    Returns: 
        non-negative number: hdl number returned Successful; negative number: failed.
    """
    return Open(serialNo.encode('utf-8'), nBaud, timeout)

def FWxCIsOpen(serialNo):
    """ Check opened status of FWxC device
    Args:
        serialNo: serial number of FWxC device
    Returns: 
        0: FWxC device is not opened; 1: FWxC device is opened.
    """
    return IsOpen(serialNo.encode('utf-8'))

def FWxCClose(hdl):
    """ Close opened FWxC device
    Args:
        hdl: the handle of opened FWxC device
    Returns: 
        0: Success; negative number: failed.
    """
    return Close(hdl)

def FWxCSetPosition(hdl, pos):
    """ set fiterwheel's position
    Args:
        hdl: the handle of opened FWxC device
        pos: fiterwheel position
    Returns: 
        0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return SetPosition(hdl,pos)

def FWxCSetPositionCount(hdl, count):
    """ set fiterwheel's position count 
    Args:
        hdl: the handle of opened FWxC device
        count: fiterwheel PositionCount
    Returns: 
       0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return SetPositionCount(hdl, count)

def FWxCSetSpeedMode(hdl, spmode):
    """ set fiterwheel's trigger mode
    Args:
        hdl: the handle of opened FWxC device
        spmode: fiterwheel speed mode
                speed=0 Sets the move profile to slow speed
                speed=1 Sets the move profile to high speed
    Returns: 
       0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return SetSpeedMode(hdl,spmode)

def FWxCSetTriggerMode(hdl, trimode):
    """ set fiterwheel's trigger mode
    Args:
        hdl: the handle of opened FWxC device
        trimode: fiterwheel's trigger mode
                 trig=0 Sets the external trigger to the input mode, Respond to an active low pulse by advancing position by 1
                 trig=1 Sets the external trigger to the output mode, Generate an active high pulse when selected position arrived at
    Returns: 
       0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return SetTriggerMode(hdl,trimode)

def FWxCSetSensorMode(hdl, senmode):
    """ set fiterwheel's sensor mode
    Args:
        hdl: the handle of opened FWxC device
        senmode: fiterwheel sensor mode
                 sensors=0 Sensors turn off when wheel is idle to eliminate stray light
                 sensors=1 Sensors remain active             
    Returns: 
       0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return SetSensorMode(hdl, senmode)

def FWxCSave(hdl):
    """ save all the settings as default on power up
    Args:
        hdl: the handle of opened FWxC device
    Returns: 
        0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    return Save(hdl)

def FWxCGetId(hdl, value):
    """ get the FWxC id
    Args:
        hdl: the handle of opened FWxC device
        value: the model number, hardware and firmware versions
    Returns: 
        0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    idStr = create_string_buffer(1024,'\0')
    ret = GetId(hdl,idStr)
    value.append(idStr.raw.decode("utf-8").rstrip('\x00'))
    return ret


def FWxCGetPosition(hdl, pos):
    """  get the fiterwheel current position
    Args:
        hdl: the handle of opened FWxC device
        pos: fiterwheel actual position
    Returns: 
         0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    val = c_int(0)
    ret = GetPosition(hdl,val)
    pos[0] = val.value
    return ret

def FWxCGetPositionCount(hdl, poscount):
    """  get the fiterwheel current position count
    Args:
        hdl: the handle of opened FWxC device
        poscount: fiterwheel actual position count
    Returns: 
         0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    val = c_int(0)
    ret = GetPositionCount(hdl,val)
    poscount[0] = val.value
    return ret

def FWxCGetSpeedMode(hdl, spemode):
    """ get the fiterwheel current speed mode
    Args:
        hdl: the handle of opened FWxC device
        spemode: 0,slow speed:1,high speed
    Returns: 
         0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    val = c_int(0)
    ret = GetSpeedMode(hdl,val)
    spemode[0] = val.value
    return ret

def FWxCGetTriggerMode(hdl, triggermode):
    """  get the fiterwheel current position count
    Args:
        hdl: the handle of opened FWxC device
        triggermode: fiterwheel actual trigger mode:0, input mode;1, output mode
    Returns: 
         0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    val = c_int(0)
    ret = GetTriggerMode(hdl,val)
    triggermode[0] = val.value
    return ret

def FWxCGetSensorMode(hdl, sensormode):
    """  get the fiterwheel current sensor mode
    Args:
        hdl: the handle of opened FWxC device
        sensormode: fiterwheel actual sensor mode:0, Sensors turn off;1, Sensors remain active
    Returns: 
         0: Success; 0xEA: CMD_NOT_DEFINED; 0xEB: time out; 0xED: invalid string buffer.
    """
    val = c_int(0)
    ret = GetSensorMode(hdl,val)
    sensormode[0] = val.value
    return ret




#endregion
