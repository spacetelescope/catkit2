Safety
======

Testbed safety in catkit2 is continuously monitored while the testbed is running. The `safety_monitor` service monitors data streams from other services and verifies that values remain within safe operating ranges. Monitored parameters may include temperature readings from temperature sensors, humidity levels from humidity sensors, or UPS (Uninterruptible Power Supply) operational status.

The `safety_monitor` service publishes the results of these checks to its `is_safe` data stream.

Safety Requirements
-------------------

Services that require a safe testbed environment, as specified in their configuration, periodically check the `is_safe` data stream from the `safety_monitor`. If the testbed becomes unsafe, these services initiate self-shutdown. Additionally, if the `safety_monitor` service becomes inactive or stops updating its `is_safe` data stream for any reason, the testbed is deemed unsafe and dependent services automatically shut down.

All services, regardless of whether they require a safe environment, shut down if the testbed stops sending heartbeats. This ensures that even if the testbed server crashes, all services safely terminate.

Together, these safety checks provide a robust environment for safety-critical operations.

Safety checks performed
-----------------------

For testing the safety system, we performed many tests. Below you can find all individual performed checks, performed on the HiCAT testbed at Space Telescope Science Institute. While this is a specific testbed, these checks of the safety system are valid for all testbeds using the `safety_monitor` service.

Crashing individual services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Intentionally kill a service (from the task manager).

**Check 1:** Service should be marked as CRASHED by the testbed, and should not be automatically restarted.

2022-09-09 (Emiel Por). Tested with the science_camera.

**Check 2:** If the killed service is critical for safety, the services that require safety should safely shut down themselves.

2022-09-09 (Emiel Por). Tested with omega_dm1. Both irisao_dm and boston_dm closed down safely automatically.

Interrupting individual services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Interrupt services with Ctrl+C.

**Check 1:** Service should safely shut down and be marked as CRASHED by the service itself, and should not be automatically restarted.

2022-09-09 (Emiel Por). Tested with science_camera.

**Check 2:** If the service is critical for safety, the services that require safety should safely shut down themselves.

2022-09-09 (Emiel Por). Tested with lab_ups. Both irisao_dm and boston_dm closed down safely automatically.

Heartbeat failure on a service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an interruption in service heartbeats (manually, by right-clicking on the process in Process Explorer and clicking "Suspend").

**Check 1:** Service should be marked as unresponsive by the testbed.

2022-09-09 (Emiel Por). Tested with lab_ups.
2022-09-19 (Emiel Por & Remi Soummer). Tested with omega_dm1.
2022-09-20 (Emiel Por & Remi Soummer). Tested with lab_ups.

**Check 2:** ServiceProxies to that service should time out.

2022-09-09 (Emiel Por). Checked.
2022-09-19 (Emiel Por & Remi Soummer). Tested with omega_dm1.
2022-09-20 (Emiel Por & Remi Soummer). Tested with lab_ups.

**Check 3:** If the service is critical for safety, the services that require safety should safely shut down themselves.

2022-09-09 (Emiel Por). Checked.
2022-09-19 (Emiel Por & Remi Soummer). Tested with omega_dm1.
2022-09-20 (Emiel Por & Remi Soummer). Tested with lab_ups.

**Check 4:** When heartbeats resume, service proxies should reconnect.

2022-09-09 (Emiel Por). Checked.
2022-09-19 (Emiel Por & Remi Soummer). Tested with omega_dm1. This needed a manual restart of the service, since it crashes after being suspended for more than 60secs, due to an internal timeout.
2022-09-20 (Emiel Por & Remi Soummer). Tested with lab_ups.

Heartbeat failure on safety monitor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an interruption in service heartbeats (manually) for the service monitor.

**Check 1:** Safety monitor should be marked as unresponsive.

2022-09-09 (Emiel Por). Checked.
2022-09-20 (Emiel Por & Remi Soummer). Checked.

**Check 2:** All services requiring safety should shut themselves down safely.

2022-09-09 (Emiel Por). Checked with boston_dm.
2022-09-20 (Emiel Por & Remi Soummer). Checked with both IrisAO and Boston.

Crash of the safety monitor
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an crash (manually) of the service monitor.

**Check 1:** Safety monitor should be marked as crashed.

2022-09-09 (Emiel Por). Checked.
2022-09-20 (Emiel Por & Remi Soummer). Checked.

**Check 2:** All services requiring safety should shut themselves down safely.

2022-09-09 (Emiel Por). Checked with boston_dm.
2022-09-20 (Emiel Por & Remi Soummer). Checked with both DMs.

Heartbeat failure on a testbed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an interruption in testbed heartbeats (manually).

**Check 1:** All services should safely shut down after a leniency period.

2022-09-09 (Emiel Por). Checked by suspending the testbed process with Process Explorer.
2022-09-20 (Emiel Por & Remi Soummer). Checked by suspending the testbed process with Process Explorer.

**Check 2:** Services should mark themselves as CLOSED afterwards (There is no indication of safety incident, so devices just close). After the testbed comes back online, services can be restarted automatically (e.g. upon getting a data stream) using their service proxy.

2022-09-20 (Emiel Por & Remi Soummer). Checked.

Crashed testbed
~~~~~~~~~~~~~~~

**Test:** Intentionally kill the testbed process (from the task manager).

**Check 1:** All services should safely shut down after a leniency period.

2022-09-09 (Emiel Por). Checked.
2022-09-20 (Emiel Por & Remi Soummer). Checked with almost everything on. No indication of safety failure. All services closed normally, including DMs.

Real safety event on hardware (humidity)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Let humidity in HiCAT increase above safe levels.

**Check 1:** All services requiring safety should shut down safely.

2022-09-12 (Remi Soummer).  Checked.  Both humidity sensors detected the unsafe conditions,
DMs were visibly turned off and server shut down.

**Check 2:** All services requiring safety should not be able to be restarted automatically

2022-09-12 (Remi Soummer).  Checked. Getting the messages "refusing to start a crashed service".
Nothing restarting automatically

Real safety event on hardware (UPS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** In that test the last and only safety is provided by the lab UPS battery if the DMs are connected.
If something is wrong with the lab UPS this test can destroy the DM.
This test can be done preferably with the Boston DM controller turned off (double check state of DMs before), since
the software does not know whether the control electronics is powered or not.

Unplug the lab UPS so that it will go on battery.

**Check 1:** All services requiring safety should shut down safely.

2022-09-12 (Remi Soummer).  Checked.

**Check 2:** All services requiring safety should not be able to be restarted automatically.

2022-09-20 (Emiel Por & Remi Soummer). Checked with a simulated lab_ups failure (by returning False after a certain time has expired). Services requiring safety safely closed down and showed CRASHED as their state afterwards. They could not be restarted automatically via the ServiceProxy afterwards. While the testbed was still unsafe, services requiring safety immediately shut down before even opening.


Simulated safety sensor failure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the power on the safety temperature/humidity sensor for one of the two DMs on HiCAT.

**Check 1:** All services requiring safety should shut down safely.

2022-09-12 (Remi Soummer).  Checked. Sensor error detected and DMs shutting down.

**Check 2:** All services requiring safety should not be able to be restarted automatically.

2022-09-12 (Remi Soummer).  Checked. Getting the messages "refusing to start a crashed service".
Nothing restarting automatically

Simulated network failure on a safety sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the network cable on the safety temperature/humidity sensor for one of the two DMs on HiCAT.

**Check 1:** All services requiring safety should shut down safely.

2022-09-12 (Remi Soummer).  Checked. Message that something went wrong with the sensor, then testbed unsafe and shutting down.

**Check 2:** All services requiring safety should not be able to be restarted automatically.

2022-09-12 (Remi Soummer).  Checked. Getting the messages "refusing to start a crashed service".
Nothing restarting automatically even after network replugged.

Simulated non-safety-related hardware event (USB).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug a USB device operated by a service.

**Check 1:** The service should crash, but should try to shut down safely.

2022-09-12 (Remi Soummer).  Checked with science camera.  "Service was safely closed after crash"

**Check 2:** The service should not be able to be restarted automatically.

2022-09-12 (Remi Soummer).  Checked. Nothing restarting automatically.

Simulated non-safety-related hardware event (power).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug power from a hardware device operated by a service.

**Check 1:** The service should crash, but should try to shut down safely.

2022-09-12 (Remi Soummer).  Checked with one flip mount. "Service was safely closed after crash"

**Check 2:** The service should not be able to be restarted automatically.

2022-09-12 (Remi Soummer).  Checked. Nothing restarting automatically.

Simulated network failure on the main computer.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the network cable from hicat-deux.

**Check 1:** The safety temperature sensors should crash as they don't have connection to the sensor anymore. This should cascade to a safety warning.

2022-09-12 (Remi Soummer).  Checked. noted failures of both UPS and both humidity sensors.

**Check 2:** The services should not be able to be restarted automatically.

2022-09-12 (Remi Soummer).  Checked. Nothing restarting automatically.
Getting the messages "refusing to start a crashed service" for both humidity sensors.

Simulated humidity safety violation.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Terminate omega_dm1 service while boston_dm service is running.

**Check 1:** The boston_dm service should switch to 'FAIL_SAFE' mode.

2023-05-22 (Raphael Pourcelot). Checked.

**Check 2:** The boston_dm shouldn't be able to start while omega_dm1 is crashed.

2023-05-22 (Raphael Pourcelot). Checked.
