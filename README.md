The Control and Automation for Testbeds Kit 2 (CATKit2)
---------------------
CATKit2 is a toolkit for hardware controls that has been developed at the Space Telescope Science Institute.
It provides a general infrastructure to control hardware and synchronize devices.

This package was developed for use on the High-contrast Imager for Complex Apertures Testbed (HiCAT) for
developing technologies relevant to direct imaging of exoplanets in astronomy in the laboratory.

This is an open-source package, but it is not actively supported.  Use at your own risk.

For installation instructions, see the official documentation:  
https://spacetelescope.github.io/catkit2/

## Agent coding support

Start with [AGENTS.md](AGENTS.md) for working conventions. Use the [repository atlas](docs/agent/REPO_ATLAS.md) to find implementations, interfaces, documentation and tests; the [derived index](docs/agent/repo_index.json) provides compact concept lookup. Read only the sections relevant to the task, then verify against current source.

Paste this prompt into your coding agent from the repository checkout:

```text
Task: [Describe the change, question or bug and the expected outcome.]
Constraints: [State any task-specific limits, such as analysis only.]

Read AGENTS.md first. Use docs/agent/repo_index.json or the relevant
sections of docs/agent/REPO_ATLAS.md to locate the owning implementation,
callers and tests. Read that source before making changes; expand your
search when a specific unresolved question requires it.

If a reference is missing, search current symbols and imports and, when
needed, git history and authorized dependency repositories to find its
new location. Verify the current interface before using it.

Follow the repository's conventions and keep work focused on the task.
Run relevant checks within the stated constraints. Update the affected
atlas entries and derived index if canonical locations or important
interfaces change. Report the result, checks and remaining limitations.
Leave changes uncommitted; suggest a concise commit message when ready.
Commit or push only if explicitly requested.
```

Replace the bracketed text before use. For a question or analysis-only task, the result is an explanation or findings; code changes are unnecessary.

Python permissions
------------------

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
