Safety
======

Testbed safety in catkit2 is constantly monitored while the testbed is running. The `safety_monitor` service constantly checks datastreams from other services and checks if they are within the safe range. This can include for example the temperature as measured by a temperature sensor, the humidity as measured by a humidity sensor, or if the uninterruptible power supply (UPS) is still operating normally. The `safety_monitor` service submits the results of each of these checks onto its `is_safe` datastream.

Any service that requires a safe testbed to operate, as indicated by its config section, periodically checks the `is_safe` datastream from the `safety_monitor` and will initiate shutdown if the testbed is deemed unsafe. Additionally, if the `safety_monitor` service becomes inactive, or if, for any reason, no more updates are submitted on its `is_safe` datastream, the testbed is deemed unsafe and the service will automatically shut down for safety reasons.

Finally, all services, regardless of whether they require a safe testbed, will shut down if the testbed stops submitting heartbeats. This means that even if the testbed server crashes, all services will still safely shut down.

Safety checks performed
-----------------------

Crashing individual services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Intentionally kill a service (from the task manager).

**Check 1:** Service should be marked as CRASHED by the testbed, and should not be automatically restarted.

**Checked on:** ...

**Check 2:** If the killed service is critical for safety, the services that require safety should safely shut down themselves.

**Checked on:** ...

Interrupting individual services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Interrupt services with Ctrl+C.

**Check 1:** Service should safely shut down and be marked as CRASHED by the service itself, and should not be automatically restarted.

**Checked on:** ...

**Check 2:** If the service is critical for safety, the services that require safety should safely shut down themselves.

**Checked on:** ...

Heartbeat failure on a service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an interruption in service heartbeats (manually).

**Check 1:** Service should be marked as unresponsive by the testbed.

**Checked on:** ...

**Check 2:** ServiceProxies to that service should disconnect.

**Checked on:** ...

Heartbeat failure on a testbed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Simulate an interruption in testbed heartbeats (manually).

**Check 1:** All services should safely shut down after a leniency period.

**Checked on:** ...

**Check 2:** Services should mark themselves as CRASHED afterwards. Services should not be restarted automatically afterwards.

**Checked on:** ...

Real safety event on hardware (humidity)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Let humidity in HiCAT increase above safe levels.

**Check 1:** All services requiring safety should shut down safely.

**Checked on:** ...

**Check 2:** All services requiring safety should not be able to be restarted automatically.

**Checked on:** ...

Real safety event on hardware (UPS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the lab UPS in HiCAT. The UPS will go on battery.

**Check 1:** All services requiring safety should shut down safely.

**Checked on:** ...

**Check 2:** All services requiring safety should not be able to be restarted automatically.

**Checked on:** ...

Simulated safety sensor failure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the power on the safety temperature/humidity sensor for one of the two DMs on HiCAT.

**Check 1:** All services requiring safety should shut down safely.

**Checked on:** ...

**Check 2:** All services requiring safety should not be able to be restarted automatically.

**Checked on:** ...

Simulated network failure on a safety sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the power on the safety temperature/humidity sensor for one of the two DMs on HiCAT.

**Check 1:** All services requiring safety should shut down safely.

**Checked on:** ...

**Check 2:** All services requiring safety should not be able to be restarted automatically.

**Checked on:** ...

Simulated non-safety-related hardware event (USB).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug a USB device operated by a service.

**Check 1:** The service should crash, but should try to shut down safely.

**Checked on:** ...

**Check 2:** The service should not be able to be restarted automatically.

**Checked on:** ...

Simulated non-safety-related hardware event (power).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug power from a hardware device operated by a service.

**Check 1:** The service should crash, but should try to shut down safely.

**Checked on:** ...

**Check 2:** The service should not be able to be restarted automatically.

**Checked on:** ...

Simulated network failure on the main computer.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Test:** Unplug the network cable from hicat-deux.

**Check 1:** The safety temperature sensors should crash as they don't have connection to the sensor anymore. This should cascade to a safety warning.

**Checked on:** ...

**Check 2:** The temperature sensor should not be able to be restarted automatically.

**Checked on:** ...
