Watchdog Service
===============

The watchdog service provides system monitoring and Slack notification capabilities for catkit2 testbeds. It allows users to send informational messages, alerts, and diagnostic reports (including system metrics) to configured Slack channels via webhook URLs.

Configuration
-------------

.. code-block:: YAML

    monitoring_watchdog:
      service_type: watchdog
      slack_webhook_url: https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

The ``slack_webhook_url`` parameter is required and should point to your Slack webhook endpoint.

Setting up Slack Bot Integration
--------------------------------

To use the watchdog service with Slack notifications, you need to create a Slack webhook:

1. **Create a Slack App**:

   - Go to https://api.slack.com/apps
   - Click "Create New App" and choose "From scratch"
   - Give your app a name (e.g., "Catkit2 Watchdog") and select your workspace

2. **Enable Incoming Webhooks**:

   - In your app's settings, go to "Incoming Webhooks"
   - Toggle "Activate Incoming Webhooks" to "On"
   - Click "Add New Webhook to Workspace"
   - Choose the channel where you want notifications to appear
   - Copy the webhook URL (it should look like ``https://hooks.slack.com/services/XX/XX/XX``)

3. **Configure the Service**:

   - Add the webhook URL to your service configuration as shown above
   - Optionally customize the bot name by setting a custom hostname or modifying the SlackNotifier initialization

4. **Test the Integration**:

   .. code-block:: python

       # Send a test info message
       testbed.monitoring_watchdog.send_info(message="Watchdog service is now online!")

       # Send an alert
       testbed.monitoring_watchdog.send_alert(message="System temperature exceeded threshold")

       # Send diagnostic info with system metrics
       testbed.monitoring_watchdog.send_diagnostic(message="Daily system health check")

Properties
----------

The watchdog service automatically detects the system hostname and uses it to identify the source of messages in Slack notifications.

Commands
--------

``send_info(message)``
    Sends an informational message to the configured Slack channel. The message is formatted with an info icon and includes bot identification.

``send_alert(message)``
    Sends an alert message to the configured Slack channel. The message is formatted with alert styling and warning icons.

``send_diagnostic(message)``
    Sends a diagnostic message that includes system information along with the custom message. Automatically includes:

    - CPU usage percentage
    - Memory usage percentage
    - Disk usage for primary drives (Windows: C:/ and D:/, Unix: root partition)

Datastreams
-----------

None.

Example Usage
-------------

.. code-block:: python

    import catkit2
    # .. get <host> / <port>

    # Connect to testbed
    testbed = catkit2.TestbedProxy(host=<host>, port=<port>)

    # Send different types of notifications
    testbed.monitoring_watchdog.send_info(message="Experiment sequence started successfully")

    testbed.monitoring_watchdog.send_alert(message="Mirror temperature exceeds safe operating range")

    testbed.monitoring_watchdog.send_diagnostic(message="End of day system status report")

The diagnostic messages will automatically include current system metrics, making them useful for regular health checks and troubleshooting.

Error Handling
--------------

The service includes robust error handling for:

- Network connectivity issues when sending to Slack
- System monitoring failures (CPU, memory, disk usage)
- Cross-platform compatibility for hostname detection and disk monitoring
- Webhook timeout and retry scenarios

Failed message attempts are logged to the console with error details.