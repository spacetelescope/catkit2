# CATKit2 agent entry point

CATKit2 owns reusable laboratory device control and synchronization: native shared-memory/communication primitives, Python services and proxies, testbed orchestration, generic experiment bookkeeping, and simulation infrastructure. Import package: `catkit2`; native library: `catkit_core`. This is a PUBLIC repository. Ground public changes and documentation in public repository evidence; private downstream discoveries require separate review before any upstream disclosure.

This proposed guide was checked against `19023206433b14a2f0a1428129d954c5dc6433b2`. Source and configuration take precedence when the checkout changes. Read [the atlas](docs/agent/REPO_ATLAS.md) by concept; use [the derived index](docs/agent/repo_index.json) for quick path lookup. Neither replaces task-specific source inspection.

## Working defaults - PROPOSED unless noted

1. Identify the owning layer and the smallest coherent change. Keep reusable device/framework behavior here; keep an individual instrument's service instances, calibration products and operating procedure in its own package. Existing optical-model and experiment bases already live here; use the actual tree rather than an absolute "hardware only" slogan.
2. Start with the matching atlas concept, authoritative docs and a current implementation. Read its caller and test, then expand the search for a specific unresolved question. Reuse the established extension point before adding a new abstraction.
3. Keep changes focused and preserve existing working behavior. [Contribution guidance](docs/contribution.rst) explicitly documents small PR scope, separate unrelated changes and updates to tests/docs where needed. Avoid opportunistic restructuring while fixing a device or algorithm boundary.
4. Let clear code explain mechanics. Keep comments concise and concentrate on scientific intent, synchronization, hardware constraints, units, ownership and non-obvious assumptions. Existing mechanical comments are examples of current code, not a requirement to narrate every statement.
5. Leave changes uncommitted by default. Suggest a concise commit message when a coherent change is ready. Commit or push only after an explicit user request. Report the checks actually run and any remaining limitations.
6. Use the existing environment for authorized checks. Keep installation, environment changes and hardware operation within the task's explicit scope. For analysis-only work, inspect files and draft externally; leave the worktree unchanged.

## Look here first

| Task | First sources |
|---|---|
| New service | [service guide](docs/services.rst), `catkit2/testbed/service.py`, `catkit2/services/empty_service/empty_service.py`; then the relevant device implementation |
| Camera | [camera base docs](docs/services/camera.rst), `catkit2/base_services/camera.py`, `catkit2/services/zwo_camera_v2/zwo_camera_v2.py`, `catkit2/testbed/proxies/camera.py` |
| DM / channels / command shape | [DM docs](docs/services/deformable_mirror.rst), `catkit2/base_services/deformable_mirror.py`, `catkit2/testbed/proxies/deformable_mirror.py`, `tests/test_dm_commands.py` |
| Motor | [PI stage docs](docs/services/physik_stage_controller.rst), matching driver and `_sim` modules; the service guide explicitly recommends this example |
| Config / registration | [configuration docs](docs/configuration.rst), `catkit2/config.py`, `pyproject.toml`, `catkit2/testbed/testbed.py` |
| Stream / transport | `tests/test_datastream.py`, `catkit2/bindings.cpp`, `catkit_core/DataStream.h/.cpp`; for commands also `ServiceProxy.cpp`, `Service.cpp`, `LocalMessageBroker.cpp` |
| Simulation (service orchestration) vs. optical model (field propagation) | `catkit2/simulator/simulator.py` (Simulator: catkit2 service, schedules simulated time, forwards simulated-service calls to an owned OpticalModel); `catkit2/simulator/optical_model.py`, `simple_optical_model.py` (OpticalModel: plane sequence, field propagation only, no service/testbed knowledge); `tests/test_optical_model.py` |
| Experiment outputs / logging | `catkit2/testbed/experiment.py`, `catkit2/testbed/logging.py`, `catkit2/testbed/tracing.py` |
| New downstream package | [testbed guide](docs/testbed_implementation.rst), `cookiecutter-testbed/`; template tooling is scoped to that subtree |

## Actual house style

* **ENFORCED:** follow the selected checks in [.flake8](.flake8) and the [lint workflow](.github/workflows/linting.yml). This is a selective policy, not all PEP 8. Tests/docs/generated and template areas have exclusions. The command passes 127 columns but E501 is not selected. Naming codes are listed without an explicitly installed naming plugin.
* **DOCUMENTED:** snake_case service folder and same-name module; CamelCase service class; `_sim` counterpart; proxy and service documentation when appropriate. Register discoverable service modules and proxy classes in the owning distribution's entry points.
* **ESTABLISHED:** Python four-space indentation, snake_case functions/attributes, CamelCase classes, uppercase constants; mathematical variable names where they carry meaning. NumPy-style `Parameters`, `Returns`, `Raises` and `Yields` docstrings are good models in config.py and the DM/proxy code. Both quote styles occur; follow the nearby file.
* **ESTABLISHED:** Python is mostly unannotated; no root typing gate, formatter or pre-commit configuration was found. Add useful annotations locally when needed; avoid converting the project wholesale. Relative internal imports and absolute package/device imports coexist. Root exports deliberately use `__all__` and wildcard imports.
* **ESTABLISHED:** use existing `self.log`/module logging and small helpers, closures and properties. `NotImplementedError` marks extension hooks; explicit exceptions report invalid configuration and unsupported operations. Broad device/timeout catches exist; inspect their purpose before imitating them.
* **ESTABLISHED:** native code uses tabs, next-line braces, PascalCase methods and `m_` members. Match the native file and binding conventions rather than applying Python formatting rules.
* **PROPOSED:** write documentation in ASCII punctuation: straight `"` and `'` quotes, `-` or `--` for dashes, `->` for arrows. Reserve non-ASCII for content that needs it, such as accented names in citations and mathematical symbols. Any code that reads a documentation file must pass `encoding="utf-8"` explicitly: a bare `open()` uses the platform locale encoding and raises `UnicodeDecodeError` on Windows (cp1252) for typographic quotes and dashes. Packaging reads README.md through `readme` in pyproject.toml, which setuptools decodes as UTF-8, but downstream tooling and the cookiecutter template are not guaranteed to.

## Interfaces to preserve

* Python service construction is `__init__`, then `run()` invokes `open`, `main`, `close`. The service guide's `init()` name is stale. Use `should_shut_down` and bounded/cooperative waits. Native `Run` does not guarantee `close` after a failed `open`; handle partial acquisition in the relevant implementation.
* Configuration separates service ID, executable `service_type`/`simulated_service_type`, and proxy `interface`. `requires_safety` is mandatory. The server receives ordered configuration and distributes it; read `self.config` for the service and `self.testbed.config` when coordination needs the full config.
* DataStream submission requires matching dtype/shape and C-contiguous memory. Python frame waits use milliseconds. Follow CameraProxy's frame copy when keeping data beyond the current read. Properties, commands and streams are different API objects; replacing a stream with an array changes the interface.
* Preserve camera rotation/flip order, exposure units and acquisition synchronization. Current offsets remain camera coordinates; width/height use user coordinates. Preserve DM command versus map representation and channel names at the interface boundary.
* Keep property/command operations responsive; use existing worker/event patterns for ongoing work. Preserve heartbeat and safety behavior. Consult [safety docs](docs/safety.rst) before changing those paths; historical manual reports are not new validation.

## Checks and known traps

In an existing suitable environment, CI's root recipes are `flake8 . --max-line-length=127 --count --statistics` and `pytest -v`. Choose the relevant test first, e.g. `pytest -v tests/test_datastream.py`, `tests/test_service.py`, `tests/test_dm_commands.py` or `tests/test_optical_model.py`, then required broader checks. Service tests use a local testbed process; they are not plain isolated functions. Documentation CI runs `make html` in docs. Builds/tests write artifacts, so an analysis-only task should report static inspection instead of running them automatically.

Read [installation docs](docs/installation.rst), environment.yml and CMake files for build failures; empty project dependencies do not imply a dependency-free package. The checked-in conda environment pins Python 3.7.16; do not infer modern interpreter support from metadata alone.

Current caveats: old and v2 cameras coexist; `dummy_camera_v2` is incomplete; `camera_sim` still directly inherits Service; `simple_simulator` has stale callback calls. The protocol page's all-TCP description predates local-broker service communication. `CameraProxy.take_exposures` is a deprecation wrapper: use `take_raw_exposures`. Generic Experiment's `post_experiment` is a success-path hook, not guaranteed failure cleanup. Consult the atlas's caveats before choosing a template.

## Keeping navigation current - PROPOSED

If a reference is missing, search the current symbol, import and callers before adding replacement code; use git history to resolve renames. Update the affected atlas entry when canonical paths, ownership or important contracts change, then regenerate the JSON index from the atlas. Treat this guide as the stable operational entry point and load atlas sections according to the task.
