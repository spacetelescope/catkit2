Environment variables
---------------------

Set `FOR_DISABLE_CONSOLE_CTRL_HANDLER` to `1`. This disables the Fortran Ctrl+C hander, and avoids crashing of the Python program upon receiving on a Keyboard interrupt. This is necessary if you import scipy, which uses Fortran modules.

Shared memory configuration
---------------------------

On MacOS you need to increase the amount of shared memory that is available to programs. The default (4MB) is by far not enough for anything we do.
