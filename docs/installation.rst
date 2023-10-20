Installation
============

Catkit2 consists of a core C++ library and a Python package that wrappes this library. It also requires a number of C++ third party libraries to facilitate JSON encoding and decoding, Python bindings, linear algebra and high-speed communication over sockets. Compilation requires a C++ compiler conforming to the C++20 standard. Catkit2 provides scripts to automate downloading and installation of its dependencies and main library.

The following will download all third-party C++ dependencies:

.. code-block:: bash

    cd catkit2
    cd extern
    ./download.sh

These downloads can be performed on a separate machine with internet connectivity, in case the machine on which the testbed is run does not have an (unfirewalled) internet connection. After downloading, the resulting folders can be copy-pasted in the extern folder on the machine without internet connectivity.

The following will install all downloaded dependencies and create the Conda environment for catkit2.

.. code-block:: bash

    ./install.sh
    cd ..
    conda env create --file environment.yml
    conda activate catkit2

At this point, all C++ and Python dependencies of catkit2 should have been downloaded and installed. Now we can compile the core library and install the Python package.

.. code-block:: bash

    python setup.py develop

This step can fail if environment variable for cmake are not well-defined. Defining `CMAKE_GENERATOR` with a value of a generator in the available generators (which can be found with `cmake --help`) should fix the error. If the error persists, try to reboot to apply the environment variable (needed on Windows).

You should see the main compilation complete in the terminal output without errors. We installed catkit2 in editable mode to make it easier to apply updates. Any updates to the core library requires recompilation of the bindings, which can be done by simply reinstalling the package:

.. code-block:: bash

    python setup.py develop

Some services require manual installation of their respective drivers to access the devices that they operate.
