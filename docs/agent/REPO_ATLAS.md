# CATKit2 repository atlas

- Repository: `catkit2`
- Visibility: `PUBLIC`
- Full-audit source commit: `19023206433b14a2f0a1428129d954c5dc6433b2`

The full forensic scan used the commit above on develop. All implementation evidence in this atlas comes from this repository. Paths are repository-relative; symbols, rather than line numbers, are the primary retrieval keys. See [AGENTS](../../AGENTS.md) for operating defaults and `repo_index.json` for a derived concept lookup.

Canonical means the best first reference for a concern, not flawless code. Source/configuration win. **ENFORCED** denotes executable contracts; **DOCUMENTED** explicit docs; **ESTABLISHED** repeated practice; **LEGACY / EXCEPTION** transitional/specialized behavior; **PROPOSED** new agent preferences.

## Orientation and ownership

Native catkit_core owns transport/shared memory/streams/runtime/proxies; bindings.cpp exposes it to Python. testbed/ adds orchestration/proxy ergonomics, base_services/ device families, services/ executables, simulator/ scheduling/models. proto/ owns serialization; tests/ correctness; benchmarks/ performance.

Downstream packages extend CATKit2 through installed service/proxy entry points and supply instance configuration. Core interfaces do not require their private internals.

| Change | Owning layer / route |
|---|---|
| Shared-memory lifetime, event wait, stream data validation | catkit_core + bindings + tests |
| Service start/stop/safety/discovery or proxy dispatch | testbed runtime and native Service/ServiceProxy |
| Generic device-family acquisition or DM channel behavior | base_services and matching proxy |
| Vendor SDK behavior | concrete services/<driver>/<driver>.py |
| Instrument-specific calibration, addresses, workflow | downstream package using CATKit2 |
| Generic simulator time/event contract, dependency-cache mechanism | simulator base and OpticalModel already in this repository |
| A sample optical train for learning infrastructure | SimpleOpticalModel / testbed template; don't mistake an example for a universal instrument model |

Routes: camera_service → public_api → configuration; datastream → native_transport → testing; launch failures → configuration → orchestration → service_lifecycle. Concept IDs are JSON keys.

## Using and maintaining this map

Use this map for everyday implementation, debugging, testing and review: find the task's concept, read its first references and relevant tests, and follow related concepts only when a dependency or behavior needs clarification. For a relocation or other cross-layer change, the same map identifies current owners, callers and contracts to check; it does not prescribe a migration plan.

“First” means read here first; “Owner” means the implementation owner at the recorded snapshot. “Current-specialized” means a current implementation with instrument- or task-specific assumptions, not a legacy designation. Missing paths are a reason for focused search, not for recreating the old implementation. Search the symbol and import name with `rg`, check re-exports and compatibility wrappers, and use read-only git history when a rename remains unclear. Confirm the active caller uses the implementation you found.

**PROPOSED maintenance default:** when a change moves a canonical implementation, changes ownership or alters an important interface, update the affected atlas entry and regenerate its derived index. Routine internal edits need no atlas update unless they invalidate a listed contract. Current source, configuration and tests take precedence; a different HEAD alone does not require a full repository rescan.

<a id="concept-service_lifecycle"></a>

## service_lifecycle — Service construction, execution and shutdown

- Summary: Native Service runtime owns state transitions and monitoring; Python subclasses implement device-specific lifecycle hooks.
- Owner: catkit2
- Status: current
- **Read first:** `Service` in `catkit2/testbed/service.py` — Python wrapper, argument parsing, logger and extended testbed proxy.
- **Read first:** `Service::Run` in `catkit_core/Service.cpp` — Authoritative lifecycle, state, safety, thread and error behavior.
- **Read first:** `EmptyService` in `catkit2/services/empty_service/empty_service.py` — Minimal executable service shape and cooperative main loop.
- Docs: `docs/services.rst`; `docs/services/empty_service.rst`; `docs/safety.rst`
- Tests: `tests/test_service.py`; `tests/services/dummy_service/dummy_service.py`; `tests/conftest.py`
- Related: orchestration, configuration, logging, camera_service

**ESTABLISHED:** super().__init__(service_type), configuration state in __init__, device resources in open, ongoing work in main and release in close. Main guard constructs and runs. Default hooks allow omission when unused; the guide’s init() spelling is stale.

**ENFORCED runtime:** `Run` checks safety/configuration, opens, publishes info/properties, starts server and monitor threads, executes main, then closes after the normal/main-error path. An exception during open returns before Close. Therefore use the actual failure paths when reasoning about partially opened devices. Run is not reusable arbitrarily on the same instance. `should_shut_down` plus `self.sleep` appears repeatedly; bounded waits let worker loops notice shutdown.

EmptyService establishes shape only; inspect a real device and TrampolineService bindings for resource/failure behavior.

<a id="concept-orchestration"></a>

## orchestration — Testbed process and service dependency management

- Summary: Testbed manages service definitions, discovery, dependency ordering, processes, startup and shutdown.
- Owner: catkit2
- Status: current
- **Read first:** `Testbed` in `catkit2/testbed/testbed.py` — Configuration intake, entry-point discovery, service process coordination and request handlers.
- **Read first:** `ServiceReference` in `catkit2/testbed/testbed.py` — State/process bookkeeping and stop/interrupt/terminate behavior.
- **Read first:** `TestbedProxy` in `catkit2/testbed/testbed_proxy.py` — Python access to service instances and testbed information.
- Docs: `docs/overview.rst`; `docs/services.rst`; `docs/testbed_implementation.rst`
- Tests: `tests/conftest.py`; `tests/test_service.py`
- Related: service_lifecycle, configuration, public_api, native_transport

Testbed owns rendezvous/configuration, not image relay. It selects simulated_service_type when supplied in simulated mode, otherwise service_type. depends_on and safety drive ordering; circular dependencies error. A per-port lock and local broker support coordination.

Read `start_service`, `resolve_service_type`, `shut_down_all_services` when changing launch or cleanup. Python service module entry points are resolved to a filesystem module location for launch. Tests register local dummy service types explicitly, demonstrating a narrow test seam without packaging fake production entry points.

**DOCUMENTED:** service access via proxy can start a closed service when attributes are requested. Crashed/failsafe services intentionally refuse ordinary automatic restart; explicit Testbed start and safety state have different semantics. Do not “repair” this by adding an unconditional restart loop.

<a id="concept-configuration"></a>

## configuration — Layered YAML and plugin registration

- Summary: Ordered YAML files become named configuration sections; service/module and proxy/class entry points provide extension discovery.
- Owner: catkit2
- Status: current
- **Read first:** `read_config_files` in `catkit2/config.py` — Small complete example of ordered merge, NumPy-style docs and filename sections.
- **Read first:** `_get_yaml_loader` in `catkit2/config.py` — SafeLoader extension for config-relative !path values.
- **Read first:** `catkit2.services / catkit2.proxies` in `pyproject.toml` — Current service-module and proxy-class registration forms.
- Docs: `docs/configuration.rst`; `docs/services.rst`; `docs/testbed_implementation.rst`
- Tests: `tests/config/services.yml`; `tests/config/testbed.yml`; `tests/conftest.py`
- Related: orchestration, public_api, service_lifecycle

`read_config_files` accepts an ordered iterable of Path-like files, not directories; directory enumeration is a caller concern. It deep-updates accumulated sections in order. Later files of the same basename can override nested keys. `_read_config_file` names a section after the filename without extension. `!path` expands home notation and resolves relative paths against the YAML's parent; plain strings remain plain strings. Preserve these semantics before replacing the loader with a generic configuration framework.

Service ID identifies an instance; service_type/simulated_service_type select executable modules; interface selects proxy class. Multiple IDs can share a type. requires_safety is mandatory. Use self.config locally or self.testbed.config for coordination; docs’ testbed.configuration is stale.

**Docs caveat:** services.rst says external registrations always go in CATKit2's pyproject. Installed distribution discovery and the repository's cookiecutter pyproject demonstrate the actual extension point: declare the entry points in the package that owns the implementation. Avoid adding imports of external private packages to core merely to register them.

<a id="concept-datastream"></a>

## datastream — Typed shared-memory rolling arrays

- Summary: DataStreams expose bounded arrays with frame IDs; binding validation and copy/lifetime semantics define safe interoperability.
- Owner: catkit2
- Status: current
- **Read first:** `test_data_stream` in `tests/test_datastream.py` — Compact behavioral specification across dtype/shape and invalid submission cases.
- **Read first:** `DataStream` in `catkit2/bindings.cpp` — Python validation, GIL handling, argument names and array conversion.
- **Read first:** `DataStream` in `catkit_core/DataStream.h` — Frame metadata, buffer modes and native API definitions.
- Docs: `docs/overview.rst`; `docs/benchmarks.rst`; `docs/catkit_core.rst`
- Tests: `tests/test_datastream.py`; `tests/test_shared_memory.py`
- Related: camera_service, deformable_mirrors, native_transport, testing

Streams carry fixed-shape/dtype frames at a given configuration; parameters may be explicitly updated through the API. Submit an array with matching dtype, dimensions and C-contiguous strides: bindings raise RuntimeError otherwise and tests exercise that contract. “Convertible to float” is not equivalent to satisfying a float32 stream. CameraService deliberately casts and makes orientation output contiguous.

Distinguish `get_latest_frame`, `get_next_frame`, `get_frame(id, wait_time_in_ms)` and convenience `get()`. They express different freshness/availability behavior. Frame IDs and finite rolling capacity mean a consumer may miss overwritten frames; inspect the selected buffer-handling mode and retry logic. Python frame-wait units are milliseconds even though other primitives may expose seconds.

`CameraProxy.take_raw_exposures` is the strongest first client example: it skips already-integrating frames where needed, retries overwritten IDs, copies frame.data before yielding and restores acquisition state. A direct frame view is not automatically an independent stored image. Inspect native DataStream.cpp and binding conversion when changing lifetime semantics rather than relying on a NumPy-looking object alone.

<a id="concept-camera_service"></a>

## camera_service — Current camera extension point

- Summary: CameraService factors acquisition/ROI/orientation/streams; current concrete v2 drivers provide vendor hooks.
- Owner: catkit2
- Status: current-transition
- **Read first:** `CameraService` in `catkit2/base_services/camera.py` — Shared acquisition loop, exposed properties, orientation and temperature stream.
- **Read first:** `StoppedAcquisition` in `catkit2/base_services/camera.py` — Temporary stop/restart around properties requiring acquisition pause.
- **Read first:** `ZwoCamera` in `catkit2/services/zwo_camera_v2/zwo_camera_v2.py` — Concrete initialized hardware, stopped-acquisition flags and base hook implementation.
- Docs: `docs/services/camera.rst`; `docs/services/zwo_camera.rst`; `docs/services/camera_sim.rst`
- Tests: None dedicated to the camera base or v2 driver in default tests; DataStream tests cover only the stream substrate.
- Related: service_lifecycle, datastream, configuration, public_api, simulation

For a new camera read those three symbols before any legacy driver. Concrete hooks include capture/start/end acquisition, ROI size and offsets, sensor dimensions, exposure/gain and temperature. Each concrete class supplies `*_requires_stopped_acquisition` flags. Device setup precedes `super().open()` because the base accesses sensor/ROI properties; teardown must respect the base's temperature-thread lifetime. Public commands toggle requested acquisition through underscored helpers; SDK start/end hooks run in the acquisition loop.

**DOCUMENTED/current:** rotate 90 degrees first, then flip_x vertically, then flip_y horizontally. width/height and sensor dimensions account for rotation; offset_x/offset_y currently pass camera coordinates. The base's introductory “all values user coordinates” comment is broader than the implementation and camera documentation. Images are submitted float32; exposure_time is in microseconds at the public camera interface.

**LEGACY / EXCEPTION:** old drivers and v2 siblings are both registered. A new extension should start from the current base, but selecting which existing hardware service type to migrate requires its own validation. `dummy_camera_v2` has missing hooks/TODOs and is not a complete tutorial. `camera_sim` still inherits Service directly. ZWO's bandwidth prints, broad catch for already-stopped SDK state and exposure discretization are device-specific context, not universal house style.

<a id="concept-deformable_mirrors"></a>

## deformable_mirrors — Channels, maps and hardware conversion

- Summary: Generic DM base owns channel aggregation; BMC factors voltage conversion; proxies convert commands/maps and apply shapes.
- Owner: catkit2
- Status: current
- **Read first:** `DeformableMirrorService` in `catkit2/base_services/deformable_mirror.py` — Shared channel creation, monitoring, lock and send_surface hook.
- **Read first:** `BmcDeformableMirror` in `catkit2/base_services/bmc_deformable_mirror.py` — Shared calibration, clipping/discretization and send_to_device seam.
- **Read first:** `DeformableMirrorProxy` in `catkit2/testbed/proxies/deformable_mirror.py` — Shape conversion, channels, apply_shape and persistence helpers.
- Docs: `docs/services/deformable_mirror.rst`; `docs/services/bmc_deformable_mirror.rst`
- Tests: `tests/test_dm_commands.py`; `tests/services/dummy_dm_service/dummy_dm_service.py`; `tests/data/dm_mask.fits`
- Related: datastream, service_lifecycle, simulation, configuration

DM commands concatenate active actuators into 1D; maps stack devices first. Proxy conversions use the device mask. Keep these separate from vendor padding/voltages. The base supports common-driver same-shaped devices, not arbitrary heterogeneous layouts.

The base initializes channels/startup maps, monitors each stream and co-adds channels under a lock before `send_surface`. BMC owns flat/gain data, normalized/clipped voltage conversion and optional DAC discretization; hardware and simulated subclasses implement `send_to_device`. See `catkit2/services/bmc_deformable_mirror_sim/bmc_deformable_mirror_sim.py:BmcDeformableMirrorSim` for a small simulation adapter calling simulator.actuate_dm.

**Tests:** flatten_channels checks previous summed commands and subsequent zero channels using a dummy service. It is a good API test, not full proof of every map layout or vendor voltage conversion. **Evolution:** lock ownership moved to the generic base in `3c3ae29` (2025); copying an earlier revision can duplicate synchronization incorrectly.

<a id="concept-motor_service"></a>

## motor_service — Configured motion and telemetry

- Summary: PI stage driver/simulator show command, property and stream interfaces around configured axes.
- Owner: catkit2
- Status: specialized-current
- **Read first:** `PhysikStageController` in `catkit2/services/physik_stage_controller/physik_stage_controller.py` — Explicitly recommended by services documentation; current axis/telemetry/worker example.
- **Read first:** `PhysikStageControllerSim` in `catkit2/services/physik_stage_controller_sim/physik_stage_controller_sim.py` — Interface counterpart with instantaneous simulated moves.
- Docs: `docs/services.rst`; `docs/services/physik_stage_controller.rst`; `docs/services/newport_xps_q8.rst`
- Tests: None dedicated to this driver in root tests.
- Related: service_lifecycle, configuration, datastream, simulation

The driver connects by configured serial/controller, maps named axes, exposes position properties and movement commands, and receives target positions through a stream worker. It serializes SDK access with a mutex and publishes telemetry on movement completion. Compare asynchronous move_to against move_and_wait rather than treating all methods as interchangeable.

This is a current/documented example even though blame credits Lane Meier and MichaelPhilbin rather than Emiel Por. Authorship was not a prerequisite for selection. Inspect sorted axis-name versus axis-number paths if generalizing beyond its current mapping, and examine the broad RuntimeError worker catch and daemon-thread cleanup. Canonical use is “how this device exposes motion,” not “copy every failure-handling choice.” Choose the existing Newport or Thorlabs family instead for a task concerning that SDK/proxy.

<a id="concept-simulation"></a>

## simulation — Time scheduler and optical dependency graph

- Summary: Simulator schedules time-dependent actions; OpticalModel registers/caches optical planes and invalidates dependent propagation.
- Owner: catkit2
- Status: current
- **Read first:** `Simulator` in `catkit2/simulator/simulator.py` — Callback, camera integration/readout and device action extension contracts.
- **Read first:** `OpticalModel` in `catkit2/simulator/optical_model.py` — register_plane, set/get_wavefronts, purge_plane and temporary propagation cache.
- **Read first:** `SimpleOpticalModel` in `catkit2/simulator/simple_optical_model.py` — Concrete small model paired with an automated propagation test.
- Docs: `docs/testbed_implementation.rst`; `docs/services/camera_sim.rst`; `docs/overview.rst`
- Tests: `tests/test_optical_model.py`
- Related: camera_service, deformable_mirrors, configuration, datastream

`Simulator.add_callback(callback_func, t=None)` schedules a callback; execution passes the scheduled time. Hooks such as get_camera_power, camera_readout, actuate_dm and move_stage separate physical modeling from generic scheduling. Simulated services can call the configured simulator, but not every simulation must: the PI simulator keeps local instantaneous position state. Avoid turning one implementation's architecture into a universal rule.

`OpticalModel.register_plane(name, dependencies)` registers propagation functions; set_wavefronts/purge_plane invalidate downstream cached results. `propagate` uses a temporary cache and restores the original cache in a context manager. `with_cached_result` and `property_with_logic` demonstrate compact cache/property helpers. Use explicit invalidation whenever a changing optical element affects propagated fields. The test deliberately advances atmosphere time and purges pre_coro before reading the camera.

**LEGACY:** SimpleSimulator is labeled example-only and contains old add_callback argument order/callback signatures. The cookiecutter simulator offers a small current get_camera_power/camera_readout example; its template variables need rendering before execution. The template and optical test are stronger starting points than assuming every “simple” executable is maintained equally.

<a id="concept-experiment"></a>

## experiment — Generic execution and output bookkeeping

- Summary: Experiment handles nested run directories, metadata/config snapshots and logging around three execution hooks.
- Owner: catkit2
- Status: current
- **Read first:** `Experiment` in `catkit2/testbed/experiment.py` — run lifecycle, output path templates and nested experiment bookkeeping.
- Docs: `docs/overview.rst`; `docs/configuration.rst`
- Tests: None direct in root tests at this snapshot.
- Related: logging, configuration, orchestration

Experiment subclasses supply name and three hooks. Base inputs are testbed, metadata and is_base_experiment; _running_experiments determines nesting. It writes metadata.asdf, config.yml and scoped experiment.log using configured parent/child output templates.

Reuse generic output/logging bookkeeping; keep local alignment/reset/scientific procedures in downstream subclasses.

**Failure caveat:** the three hooks execute sequentially; a pre/experiment exception is logged and re-raised. finally cleans logging and the running-experiment stack, not arbitrary subclass hardware state. post_experiment is not a guaranteed “always restore” hook. This distinction matters when choosing where to put a cleanup operation.

<a id="concept-logging"></a>

## logging — Python/native logs and performance tracing

- Summary: Existing handlers bridge Python logging into CATKit2; observers distribute/write/display logs and tracing captures intervals.
- Owner: catkit2
- Status: current
- **Read first:** `CatkitLogHandler` in `catkit2/testbed/logging.py` — Python LogRecord to native log entry conversion.
- **Read first:** `LogWriter` in `catkit2/testbed/logging.py` — Context-managed output target, file lock and incremental writing.
- **Read first:** `trace_interval` in `catkit2/testbed/tracing.py` — Existing timing instrumentation used by device bases.
- Docs: `docs/overview.rst`; `docs/benchmarks.rst`
- Tests: `tests/test_tracing.py`
- Related: service_lifecycle, experiment, native_transport

Service/Experiment provide loggers; Testbed distributes them. LogObserver receives, LogWriter persists and LogTerminal displays. LogObserver distinguishes ZMQ timeout from other errors—a useful narrow-handling example.

**ESTABLISHED:** module/class logging, ordinary exceptions and small context managers. Formatting is mixed: f-strings, .format and logger interpolation all occur. Reuse the existing logging path; no rule mandates one interpolation syntax. Mechanical comments and print statements remain in source. **PROPOSED:** new comments should emphasize synchronization, scientific assumptions or hardware constraints; instrumentation should clarify a relevant performance question, not decorate every helper.

<a id="concept-native_transport"></a>

## native_transport — IPC, Python bindings and build boundary

- Summary: Native core/bindings own local broker and server paths, buffer lifetime and Python/native interoperability.
- Owner: catkit2
- Status: current-transition
- **Read first:** `ServiceProxy` in `catkit_core/ServiceProxy.cpp` — Actual current property/command communication.
- **Read first:** `LocalMessageBroker` in `catkit_core/LocalMessageBroker.cpp` — Shared-memory broker implementation used by the runtime.
- **Read first:** `TrampolineService` in `catkit2/bindings.cpp` — Python override dispatch and GIL-sensitive run/cleanup bridge.
- Docs: `docs/protocol.rst`; `docs/catkit_core.rst`; `docs/installation.rst`
- Tests: `tests/test_message_broker.py`; `tests/test_server_client.py`; `tests/test_shared_memory.py`
- Related: datastream, orchestration, service_lifecycle, testing

**Docs drift:** protocol.rst describes all communication as TCP ZeroMQ REQ-REP. Native ServiceProxy/Service now use the local message broker for property/command paths and service info. Server/Client still matter for testbed and control requests; the right model is coexistence, not a total removal of TCP. Follow the actual request path when debugging a stall.

CMake requires 3.21 and C++17, and builds core, Python bindings and benchmarks; scikit-build-core drives packaging. Native APIs use PascalCase and m_ fields; Python bindings expose snake_case, explicit py::arg names and selective GIL release. `76924fc` moved cleanup handling around GIL requirements; changes involving Python callbacks/destructors need corresponding binding review. `49dd976` concerns Shareable memory lifetime; views/buffer ownership are part of correctness.

The proto directory defines serialization contracts. Avoid changing a Python-facing property name, native layout or message schema as an incidental refactor; inspect its callers and tests. No root clang-format, native style gate or independent performance pass criterion was found.

<a id="concept-testing"></a>

## testing — Check selection, coverage and build prerequisites

- Summary: Root pytest covers primitives/proxy behavior with arrays and dummy services; CI supplies a native conda build on three OSes.
- Owner: catkit2
- Status: current
- **Read first:** `testbed` in `tests/conftest.py` — Session process fixture, explicit dummy service registration and teardown.
- **Read first:** `pytest job` in `.github/workflows/testing.yml` — Actual install/test command and OS matrix.
- **Read first:** `flake8 configuration` in `.flake8` — Selective static checks and exclusions.
- Docs: `docs/contribution.rst`; `docs/installation.rst`
- Tests: `tests/test_datastream.py`; `tests/test_service.py`; `tests/test_dm_commands.py`; `tests/test_optical_model.py`
- Related: datastream, service_lifecycle, native_transport

CI root commands: `flake8 . --max-line-length=127 --count --statistics`, `pytest -v`; docs CI invokes make html under docs. pytest.ini restricts root discovery to tests. It does not include cookiecutter-testbed/tests by default. Tests use plain assertions, np.allclose, pytest.raises, parametrized dtype/shape combinations and session fixtures. They combine low-level binding checks with process-based integration. No dedicated camera-base/PI-driver test or Experiment test was found.

Lint excludes tests/docs/proto/extern/cookiecutter and build/cache directories. Selected E/W/F checks are enforced; 127-column E501 and installed naming-plugin enforcement are not established. No root formatter/type/docstring/pre-commit gate exists. Python conda pin is 3.7.16; pyproject declares >=3.7 and an empty dependency list. environment.yml and CMake are therefore necessary context for build failures. Do not change the environment to “make an audit pass.”

**PROPOSED check strategy:** validate the changed contract first, then the repository's applicable broader checks. Report which tests ran, which dependencies/hardware were available and which results are only static inspection. Numerical/performance/hardware validation are different claims. Existing random tests and manual safety reports are useful context but not a blanket assurance.

<a id="concept-public_api"></a>

## public_api — Python proxy interface and exports

- Summary: Python proxies turn named service properties, commands and streams into attributes while allowing specialized interfaces.
- Owner: catkit2
- Status: current
- **Read first:** `ServiceProxy` in `catkit2/testbed/service_proxy.py` — Dynamic get/set dispatch and installed proxy-interface lookup.
- **Read first:** `CameraProxy` in `catkit2/testbed/proxies/camera.py` — Small specialized client with copied-frame generator and compatibility wrapper.
- Docs: `docs/services.rst`; `docs/overview.rst`
- Tests: `tests/test_service.py`
- Related: configuration, orchestration, datastream, camera_service

__getattr__ dispatches property reads, named-keyword commands and stream access. __setattr__ routes property writes; commands and streams cannot be replaced by assignment. Unknown attributes use normal Python behavior or raise AttributeError. Specialized proxies inherit this contract and are selected by configured interface through installed catkit2.proxies entry points. Some internal proxy state uses object.__setattr__ to avoid remote dispatch/circular setup.

Root/export modules use wildcard imports with __all__; leaf modules usually import dependencies explicitly. Inspect exports before assuming a symbol is importable from the package root. CameraProxy.take_exposures remains a DeprecationWarning wrapper around take_raw_exposures: preserve compatibility intentionally and use the latter for new acquisition code.

## Style evidence and maintenance notes

Git supports Emiel authorship of config.py/CameraProxy and substantial DM-base/OpticalModel/camera-base work. Later maintainers matter; PI is documented/current with different authors. Blame can reflect moves/docstring edits rather than original algorithm authorship.

House style is small purpose-built classes, NumPy-style scientific docs, properties/closures for concrete repeated operations, explicit stream types, cooperative loops, and tests near runtime contracts. Sparse annotations, mixed quote/import/logging styles and lingering mechanical comments are observations. Prefer following the relevant canonical file over enforcing a generic Python style guide. The PROPOSED agent behavior in AGENTS should remain identifiable as policy proposed for adoption.

Update concept status/paths/tests from reviewed source, then regenerate JSON. Existing RST remains authoritative. AGENTS + atlas + index suffice; Sphinx lacks a Markdown parser, so adding Markdown to its toctree is separate work.

## Maintaining this atlas

Update an entry when a canonical implementation moves, its ownership changes, or an important interface, test route or documentation reference changes. Routine internal edits do not require an atlas update. Edit the Markdown first; `repo_index.json` is generated and must not be edited independently. The source snapshot records the last full forensic review, so a focused update does not need to change it.

For public CATKit2, use only evidence available in this repository and its public documentation/history. Describe generic laboratory infrastructure without importing knowledge or terminology from private downstream projects.

Use this prompt when asking an agent to refresh the map:

```text
Update the CATKit2 agent context for [change, PR, commit or commit range].
Read AGENTS.md and docs/agent/REPO_ATLAS.md. Inspect the specified diff,
current source, callers, documentation and tests. Update only concepts whose
canonical paths, ownership, interfaces or important caveats changed. Preserve
the ENFORCED, DOCUMENTED, ESTABLISHED, LEGACY / EXCEPTION and PROPOSED
distinctions. Use public CATKit2 evidence only.

Run:
python tools/agent_context.py generate
python tools/agent_context.py check

Review the Markdown and generated JSON diff, report uncertain claims, and
leave changes uncommitted unless explicitly asked to commit.
```

The generator verifies concept structure, related-concept links, referenced files, relative Markdown links and exact JSON derivation. Human review is still required for architectural meaning, canonical-example quality and whether an observed pattern deserves its classification.
