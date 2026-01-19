Installation
============

CATKit2 consists of a core C++ library and a Python package that wraps this library. It also requires a number of C++ third party libraries to facilitate JSON encoding and decoding, Python bindings, linear algebra and high-speed communication over sockets. Compilation requires a C++ compiler conforming to the C++17 standard. CATKit2 performs installation of the core library and Python package using CMake and Conda.

Environment variables
---------------------

Set ``FOR_DISABLE_CONSOLE_CTRL_HANDLER`` to ``1``. This disables the Fortran Ctrl+C handler, and avoids crashing of the Python program upon receiving on a Keyboard interrupt. This is necessary if you import scipy, which uses Fortran modules.

- On Windows, you can set environment variables for your account only from the control panel, which doesn't require administrator rights.

- On MacOS, assuming a bash shell this is done by adding the following line at the end of your ``.bash_profile`` file, which is located in your home directory and can be created if it does not exist:

.. code-block:: bash

    export FOR_DISABLE_CONSOLE_CTRL_HANDLER=1

Shared memory configuration
---------------------------
On MacOS 15.3.1 (Sequoia) a "too many open files error" can be seen when running the testbed server due to the default resources
available to processes set by the OS. This value can be increased manually using the ``ulimit``
command that can be executed on terminal startup by adding the following line to your
``.bash_profle`` (or the profile of your terminal if not using bash). The default for Sequoia is 256
and a value of at least 2000 is recommended. Most people find 4096 to be sufficient.

.. code-block:: bash

    ulimit -n <number>

.. note::
    This issue is OS version dependent and might need to be revisited.


C++ compiler
------------
The catkit2 installation requires a pre-installed C++ compiler.

- On Windows, you can for example install the Visual Studio Compiler, either by installing the Build Tools, or by installing the full IDE with compiler (the community edition is free).
- On MacOS, nothing should be needed, but some machines require Xcode to be installed. It does install components on first startup, so it is recommended to start XCode on your Mac if you have never used it (and accept the license agreement of XCode, which is required).
- XCode 15 (Sonoma and higher) introduced some changes in the compiler location, which requires the following environment variable update:

.. code-block:: bash

    export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)


Package installation
--------------------

The following will create a new Conda environment with the required C++ and Python packages. You will need to install drivers and SDKs for some devices yourself to use those devices.

For installation with an **Apple Silicon chip with python=3.7** (current default on catkit2), you need to follow these steps:

.. code-block:: bash

    cd /path/catkit2
    conda create --name catkit2
    conda activate catkit2
    conda config --env --set subdir osx-64
    conda env update --file environment.yml

For **all other platforms**, and if running with a newer Python versions, you can use the following command:

.. code-block:: bash

    conda env create --file environment.yml
    conda activate catkit2

At this point, all C++ and Python dependencies of catkit2 should have been downloaded and installed. Now we can compile the core library and install the Python package.

.. code-block:: bash

    pip install -e .

This will use the default CMake generator to compile catkit2_core and its Python bindings. If the default generator doesn't support 64bit compilation, this step will return an error and you will need to specify a default generator to use by setting the ``CMAKE_GENERATOR`` environment variable to your preferred generator. You can list all generators installed on your machine with ``cmake --help``. You will have to restart your terminal after changing your environment variables as usual.


Some services require manual installation of their respective drivers to access the devices that they operate.
