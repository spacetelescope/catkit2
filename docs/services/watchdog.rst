Watchdog Service
================

The watchdog service provides system monitoring and Slack notification capabilities for catkit2 testbeds. It allows users to send informational messages, alerts, and diagnostic reports (including system metrics) to a configured Slack channel via an incoming webhook. When a Slack bot token and channel ID are also configured, the service can upload images and other files (plots, camera frames, FITS previews, log excerpts) to the same channel, either on their own or attached to an alert.

Configuration
-------------

.. code-block:: YAML

    monitoring_watchdog:
      service_type: watchdog
      requires_safety: false
      slack_webhook_url: https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

      # Optional: needed only for image/file uploads.
      slack_bot_token: null        # prefer the CATKIT2_SLACK_BOT_TOKEN environment variable
      slack_channel_id: null       # e.g. C0123456789, the channel the webhook posts to

      # Optional.
      botname: null                # sender name shown in messages; defaults to the hostname
      dry_run: false               # true -> log payloads instead of posting them to Slack

``slack_webhook_url``
    Required (unless provided through the environment, see below). The Slack incoming webhook URL used for all text messages.

``slack_bot_token``
    Optional. A Slack bot user OAuth token (``xoxb-...``) with the ``files:write`` scope. Required for uploads. The ``CATKIT2_SLACK_BOT_TOKEN`` environment variable takes precedence over this key, so the token can be kept out of version-controlled configuration files.

``slack_channel_id``
    Optional. The ID of the channel uploads are shared to (for example ``C0123456789``). Required for uploads. This is the channel *ID*, not its name; see the setup instructions below for how to find it.

``botname``
    Optional. The sender name shown in messages. Defaults to the hostname of the machine running the service.

``dry_run``
    Optional, default ``false``. When ``true``, all messages and uploads are logged (at ``INFO`` level) instead of being sent. Useful while setting up a new testbed, or in a simulated configuration.

Environment variables
^^^^^^^^^^^^^^^^^^^^^

Both secrets can be supplied through the environment of the process that starts the testbed server, which is preferable to writing them into ``services.yml``:

``CATKIT2_SLACK_WEBHOOK_URL``
    Overrides ``slack_webhook_url``.

``CATKIT2_SLACK_BOT_TOKEN``
    Overrides ``slack_bot_token``.

Setting up Slack integration
----------------------------

Text messages (webhook)
^^^^^^^^^^^^^^^^^^^^^^^

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

   - Add the webhook URL to your service configuration as shown above, or export it as ``CATKIT2_SLACK_WEBHOOK_URL``

Image and file uploads (bot token)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Incoming webhooks can only post text, so uploads use the Slack Web API with a bot token. This is optional: without it, the ``send_alert_with_image`` command still delivers the text of the alert and only the image is skipped.

1. **Add the upload scope**:

   - In the same Slack app, go to "OAuth & Permissions"
   - Under "Scopes" -> "Bot Token Scopes", add ``files:write``
   - Click "Install to Workspace" (or "Reinstall to Workspace" if the app was already installed) and approve the change
   - Copy the "Bot User OAuth Token" (it starts with ``xoxb-``)

2. **Invite the bot to the channel**:

   - In Slack, open the channel that the webhook posts to and run ``/invite @<your app name>``. Uploads to a channel the bot is not a member of are rejected by Slack with a ``not_in_channel`` error.

3. **Find the channel ID**:

   - Open the channel details (click the channel name), scroll to the bottom of the "About" tab and copy the channel ID (it starts with ``C``). Alternatively, right-click the channel and choose "Copy link"; the ID is the last part of the URL.

4. **Configure the Service**:

   - Set ``slack_channel_id`` in the service configuration
   - Export the token as ``CATKIT2_SLACK_BOT_TOKEN`` in the environment of the process that starts the testbed server, or (less preferably) set ``slack_bot_token`` in the configuration

On start-up the service logs whether uploads are enabled; the ``can_upload`` property reports the same at runtime.

Testing the integration
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Send a test info message
    testbed.monitoring_watchdog.send_info(message="Watchdog service is now online!")

    # Send an alert
    testbed.monitoring_watchdog.send_alert(message="System temperature exceeded threshold")

    # Send diagnostic info with system metrics
    testbed.monitoring_watchdog.send_diagnostic(message="Daily system health check")

    # Upload a plot (requires bot token and channel ID)
    testbed.monitoring_watchdog.send_image(image_path="/data/plots/dark_zone.png", comment="Latest dark zone")

Setting ``dry_run: true`` lets you exercise all commands and inspect the payloads in the service log without posting anything.

Properties
----------

``can_upload``
    Read-only. ``True`` if both a bot token and a channel ID are configured, i.e. whether ``send_image`` and the image part of ``send_alert_with_image`` are functional.

``dry_run``
    Read-only. ``True`` if the service is logging payloads instead of posting them.

The service automatically detects the system hostname and uses it to identify the source of messages in Slack notifications, unless ``botname`` is configured.

Commands
--------

All commands return a value so callers can react to delivery failures (for example, retry later or log locally).

``send_info(message)``
    Sends an informational message to the configured Slack channel. The message is formatted with an info icon and includes bot identification. Returns ``True`` on success.

``send_alert(message)``
    Sends an alert message to the configured Slack channel. The message is formatted with alert styling and warning icons. Returns ``True`` on success.

``send_diagnostic(message)``
    Sends a diagnostic message that includes system information along with the custom message. Returns ``True`` on success. Automatically includes:

    - CPU usage percentage
    - Memory usage percentage
    - Disk usage for primary drives (Windows: C:/ and D:/, Unix: root partition)

``send_image(image_path, comment='', title=None)``
    Uploads the file at ``image_path`` to the configured channel with an optional ``comment`` and ``title`` (defaults to the file name). Any file type is accepted; PNG and JPEG images are rendered inline by Slack. Returns ``True`` if the upload completed, ``False`` if uploads are not configured, the file does not exist or Slack rejected it.

    The path is resolved on the machine running the watchdog service, which is not necessarily the machine running the experiment script. Use paths on shared storage, or run the watchdog on the same machine as the experiment.

``send_alert_with_image(message, image_path=None, severity='alert')``
    Posts ``message`` in the ``severity`` style (``'info'``, ``'alert'`` or ``'diagnostic'``), then uploads ``image_path`` as a follow-up in the same channel. The text is always sent through the webhook first, so an alert is never lost because of a failed upload. Returns a string describing the delivery path that was used:

    - ``'upload'``: text was posted and the image was uploaded
    - ``'webhook'``: text was posted; the image was skipped (no path given, uploads not configured) or its upload failed
    - ``'dry_run'``: nothing was sent, payloads were logged
    - ``'failed'``: the text message could not be posted
    - ``'skipped'``: ``message`` was empty

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

    # Alert with a supporting image; degrades gracefully to text if uploads are not configured.
    import matplotlib.pyplot as plt
    plt.imsave('/data/plots/latest_frame.png', frame)

    delivery = testbed.monitoring_watchdog.send_alert_with_image(
        message="Unexpected speckle pattern in the dark zone",
        image_path='/data/plots/latest_frame.png',
        severity='alert')

    if delivery != 'upload':
        testbed.log.warning(f'Alert image was not attached (delivery: {delivery}).')

The diagnostic messages will automatically include current system metrics, making them useful for regular health checks and troubleshooting.

Error Handling
--------------

The service never raises on delivery problems; it logs them and reports failure through the return value of the command. This covers:

- Network connectivity issues when sending to Slack (30 s timeout for messages, 120 s for uploads)
- Slack API errors on upload, e.g. ``not_in_channel`` (bot not invited), ``invalid_auth`` (bad token), ``missing_scope`` (``files:write`` not granted)
- A missing or unreadable file passed to ``send_image``
- System monitoring failures (CPU, memory, disk usage)
- Cross-platform compatibility for hostname detection and disk monitoring

The only exceptions raised are for configuration mistakes: a missing webhook URL at start-up, and an unknown ``severity`` passed to ``send_alert_with_image``.
