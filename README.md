Environment variables
---------------------

Set `FOR_DISABLE_CONSOLE_CTRL_HANDLER` to `1`. This disables the Fortran Ctrl+C hander, and avoids crashing of the Python program upon receiving on a Keyboard interrupt. This is necessary if you import scipy, which uses Fortran modules.

On Windows, you can set environment variables for your account only from the control panel, which doesn't require administrator rights.

On MacOS, assuming a bash shell (the standard choice for hicat work) this is done by adding the following line at the end of your .bash_profile file:
```
export FOR_DISABLE_CONSOLE_CTRL_HANDLER=1
```
The .bash_profile file is located in your home directory and can be created if it does not exist.
This line can be added using VI or a text editor like BBEdit that allows to edit hidden files.

Shared memory configuration
---------------------------

On MacOS you need to increase the amount of shared memory that is available to programs. The default (4MB) is by far not enough for anything we do.
Note: it appears that Catalina seem to allow more shared memory than what is indicated in the documentation, so no action seem to be needed.

Python permissions
---------------------------

On MacOS, even after having allowed your firewall to receive incoming connections from Python applications while running catkit2,
it might keep popping up windows asking you to accept incoming connections every single time you start a server or service.
To prevent this, you can create a self-signed certificate in your keychain. The instructions for that are below,
found on: https://stackoverflow.com/a/59186900/10112569

```
With the OS X firewall enabled, you can remove the "Do you want the application "python" to accept incoming network connections?" message.

Create a self-signed certificate.

Open Keychain Access. Applications > Utilities > Keychain Access.
Keychain Access menu > Certificate Assistant > Create a Certificate...
Enter a Name like "My Certificate".
Select Identity Type: Self Signed Root
Select Certificate Type: Code Signing
Check the Let me override defaults box
Click Continue
Enter a unique Serial Number
Enter 7300 for Validity Period.
Click Continue
Click Continue for the rest of the dialogs
Now sign your application

  codesign -s "My Certificate" -f $(which python)

In the dialog that appears, click "Allow".

Note that when using a virtual environment, you need to activate the virtual environment before running this command.
```

Installation
------------

This procedure requires a pre-installed C++ compiler.
- On Windows, you can for example install the Visual Studio Compiler, either by installing the Build Tools, or by installing the full IDE with compiler (the community edition is free).
- On MacOS, nothing should be needed, but some machines require Xcode to be installed. It does install components on first startup, so it is recommended to start XCode on your mac if you have never used it.

The following will download all third-party C++ dependencies and create a new Conda environment with the required Python packages. The download can be performed on a separate machine with internet connectivity and the resulting folders can be copy-pasted in the extern folder on the machine without internet connectivity.

You will need to install drivers and SDKs for some devices yourself to use those devices.

```
cd catkit2
cd extern
./download.sh
cd ..
conda env create --file environment.yml
conda activate catkit2
python setup.py develop
cd ..
```
