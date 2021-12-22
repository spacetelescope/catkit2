Environment variables
---------------------

Set `FOR_DISABLE_CONSOLE_CTRL_HANDLER` to `1`. This disables the Fortran Ctrl+C hander, and avoids crashing of the Python program upon receiving on a Keyboard interrupt. This is necessary if you import scipy, which uses Fortran modules.

Shared memory configuration
---------------------------

On MacOS you need to increase the amount of shared memory that is available to programs. The default (4MB) is by far not enough for anything we do.

Installation
------------

The following will download and install all third-party C++ dependencies and create a new Conda environment with the required Python packages. The download can be performed on a separate machine with internet connectivity and the resulting folders can be copy-pasted in the extern folder on the machine without internet connectivity.

You will need to install drivers and SDKs for some devices yourself to use those devices.

```
cd catkit2
cd extern
./download.sh
./install.sh
cd ..
conda env create --file environment.yml
conda activate catkit2
python setup.py develop
cd ..
```
