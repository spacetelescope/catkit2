Installation
============

Catkit2 consists of a core C++ library and a Python package that wraps this library. It also requires a number of C++ third party libraries to facilitate JSON encoding and decoding, Python bindings, linear algebra and high-speed communication over sockets. Compilation requires a C++ compiler conforming to the C++20 standard. Catkit2 performs installation of the core library and Python package using CMake and Conda.

The following will install all dependencies and create the Conda environment for catkit2.

.. code-block:: bash

    cd ..
    conda env create --file environment.yml
    conda activate catkit2

At this point, all C++ and Python dependencies of catkit2 should have been downloaded and installed. Now we can compile the core library and install the Python package.

.. code-block:: bash

    pip install -e .

This will use the default CMake generator to compile catkit_core and its Python bindings. If the default generator doesn't support 64bit compilation, this step will return an error and you will need to specify a default generator to use by setting the CMAKE_GENERATOR environment variable to your preferred generator. You can list all generators installed on your machine with cmake --help. You will have to restart your terminal after changing your environment variables as usual.

On MacOS a standard way to install a C++ compiler is via XCode, which needs to be started (installation occurs on first launch as well as a required license agreement).
The newer version of XCode (v15) required for Sonoma and higher has introduced location changes, that require updating the following environment variable:

.. code-block:: bash

    export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)

You should see the main compilation complete in the terminal output without errors. We installed catkit2 in editable mode to make it easier to apply updates. Any updates to the core library requires recompilation of the bindings, which can be done by simply reinstalling the package:

.. code-block:: bash

    pip install -e .

Some services require manual installation of their respective drivers to access the devices that they operate.

On MacOS 15.3.1 (Sequoia) a "too many open files error" can be seen due to the default resources
available to processes set by the OS. This value can be increased manually using the ``ulimit``
command that can be executed on terminal startup by adding the following line to your
``.bash_profle`` (or the profile of your terminal if not using bash). The default for Sequoia is 256
and a value of at least 2000 is recommended. Most people find 4096 to be sufficient.

.. code-block:: bash

    ulimit -n <number>

Note: This issue is OS version dependent and might need to be revisited.