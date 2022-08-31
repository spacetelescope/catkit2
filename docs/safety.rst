Safety
======

Testbed safety in catkit2 is constantly monitored while the testbed is running. The `safety_monitor` service constantly checks datastreams from other services and checks if they are within the safe range. This can include for example the temperature as measured by a temperature sensor, the humidity as measured by a humidity sensor, or if the uninterruptible power supply (UPS) is still operating normally. The `safety_monitor` service submits the results of each of these checks onto its `is_safe` datastream.

Any service that requires a safe testbed to operate, as indicated by its config section, periodically checks the `is_safe` datastream from the `safety_monitor` and will initiate shutdown if the testbed is deemed unsafe. Additionally, if the `safety_monitor` service becomes inactive, or if, for any reason, no more updates are submitted on its `is_safe` datastream, the testbed is deemed unsafe and the service will automatically shut down for safety reasons.

Finally, all services, regardless of whether they require a safe testbed, will shut down if the testbed stops submitting heartbeats. This means that even if the testbed server crashes, all services will still safely shut down.

Safety checks performed
-----------------------

