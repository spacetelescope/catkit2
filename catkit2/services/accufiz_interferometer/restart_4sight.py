import pyautogui
from time import sleep
import psutil
import win32gui
import win32com.client
import win32con
import pythoncom

def bring_window_to_foreground(window_title):
    # Find the window
    window_handle = win32gui.FindWindow(None, window_title)
    if window_handle:
        # If window is minimized, restore it
        if win32gui.IsIconic(window_handle):
            win32gui.ShowWindow(window_handle, win32con.SW_MAXIMIZE)  # SW_RESTORE = 9

        # Bring the window to the foreground
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('%')
        win32gui.SetForegroundWindow(window_handle)

        return True
    else:
        print(f"Window '{window_title}' not found.")
        return False

class Restart4SightWebService:
    def __init__(self):
        pythoncom.CoInitialize()

    def perform_restart(self):
        self.kill_app()
        self.start_app()
        # if the automatic start web listener preference is set we don't need to do this here
        # self.start_weblistener()

    def kill_app(self):
        process_name = '4Sight.exe'
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == process_name:
                try:
                    proc.kill()
                    print(f"Process {process_name} has been terminated.")
                except psutil.NoSuchProcess:
                    print(f"Process {process_name} not found.")
                except psutil.AccessDenied:
                    print(f"Access denied to kill {process_name}.")
                except Exception as e:
                    print(f"Error occurred while killing {process_name}: {e}")

    def start_app(self):
        process_name = r"C:\Program Files (x86)\4Sight2.24\4Sight.exe"
        try:
            psutil.Popen([process_name])
            print(f"Process {process_name} has been started.")
            sleep(30)
        except FileNotFoundError:
            print(f"Process {process_name} not found.")
        except PermissionError:
            print(f"Permission denied to start {process_name}.")
        except Exception as e:
            print(f"Error occurred while starting {process_name}: {e}")

    def start_weblistener(self):
        # get the 4sight window handle
        for window in pyautogui.getAllWindows():
            if '4Sight' == window.title:
                sight_app = window

        bring_window_to_foreground(sight_app.title)
        sleep(1)
        foreground = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        print('Foreground: ', foreground)
        # Bring the '4Sight' window to the foreground
        sight_app.activate()
        # Wait for the window to come to the foreground
        sleep(1)
        pyautogui.click(400, 400)
        sleep(.2)
        pyautogui.keyUp('alt')
        pyautogui.press('alt')

        sleep(.5)
        pyautogui.press('right', 7)
        sleep(.1)
        pyautogui.press('down', 1)
        foreground = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        print('Foreground: ', foreground)
        pyautogui.press('enter', 1)
