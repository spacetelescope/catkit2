"""Watchdog service for system monitoring and Slack notifications.

The service posts text notifications to Slack through an incoming webhook and,
when a bot token and channel ID are configured, can additionally upload images
or other files (plots, camera frames, log excerpts) to the same channel.
"""

from catkit2.testbed.service import Service
from time import sleep

import json
import logging
import os
import pathlib
import platform
import psutil
import requests

SLACK_API_URL = 'https://slack.com/api'

# Environment variables that override the corresponding configuration keys.
# Keeping secrets in the environment avoids committing them to a configuration file.
WEBHOOK_URL_ENV = 'CATKIT2_SLACK_WEBHOOK_URL'
BOT_TOKEN_ENV = 'CATKIT2_SLACK_BOT_TOKEN'


class SlackNotifier:
    """
    A Slack notification client for sending system alerts, diagnostics and files.

    Text messages are posted through a Slack incoming webhook. File uploads use
    the Slack Web API (``files.getUploadURLExternal`` followed by
    ``files.completeUploadExternal``), which requires a bot token with the
    ``files:write`` scope and the ID of a channel the bot is a member of.

    Parameters
    ----------
    webhook_url : str
        The Slack incoming webhook URL for text messages.
    botname : str, optional
        Name used to identify the sender in messages. If None, uses the
        system's hostname (default: None).
    bot_token : str, optional
        Slack bot user OAuth token (``xoxb-...``). Required for file uploads
        (default: None).
    channel_id : str, optional
        ID of the Slack channel (for example ``C0123456789``) that uploaded files
        are shared to. Required for file uploads (default: None).
    dry_run : bool, optional
        If True, payloads are logged instead of being sent to Slack. Useful
        while setting up a testbed or running in simulation (default: False).
    logger : logging.Logger, optional
        Logger used for status and error reporting. If None, a module-level
        logger is used (default: None).

    Attributes
    ----------
    botname : str
        The name identifier for this notification bot.
    webhook_url : str
        The configured Slack webhook URL.
    bot_token : str or None
        The configured Slack bot token.
    channel_id : str or None
        The configured Slack channel ID for uploads.
    dry_run : bool
        Whether messages are logged instead of posted.
    """

    def __init__(self, webhook_url, botname=None, bot_token=None, channel_id=None, dry_run=False, logger=None):
        if botname is None:
            # Use cross-platform hostname detection instead of Windows-specific COMPUTERNAME
            self.botname = platform.node()
        else:
            self.botname = botname

        self.webhook_url = webhook_url
        self.bot_token = bot_token or None
        self.channel_id = channel_id or None
        self.dry_run = bool(dry_run)
        self.log = logger if logger is not None else logging.getLogger(__name__)

    @property
    def can_upload(self):
        """
        Whether file uploads are configured.

        Returns
        -------
        bool
            True if both a bot token and a channel ID are set.
        """
        return bool(self.bot_token and self.channel_id)

    def send_info(self, custom_message):
        """
        Send an informational message to Slack.

        Parameters
        ----------
        custom_message : str
            The information message to send.

        Returns
        -------
        bool
            True if the message was accepted by Slack (or logged in dry-run mode).
        """
        slack_data = self._build_message(
            summary=f"ℹ️ Info from {self.botname}",
            header="ℹ️ *Information* ℹ️",
            body=custom_message,
            footer=f"🤖 This is a message from {self.botname}.")

        return self._send(slack_data)

    def send_alert(self, custom_message):
        """
        Send an alert message to Slack.

        Parameters
        ----------
        custom_message : str
            The alert message to send.

        Returns
        -------
        bool
            True if the message was accepted by Slack (or logged in dry-run mode).
        """
        slack_data = self._build_message(
            summary=f"🚨 Alert from {self.botname} 🚨",
            header="🚨 *Alert Message* 🚨",
            body=custom_message,
            footer=f"🤖 This is an alert from {self.botname}.")

        return self._send(slack_data)

    def send_diagnostic(self, custom_message):
        """
        Send a diagnostic message with system information to Slack.

        This method collects current system metrics including CPU usage,
        memory usage, and disk usage, then sends them along with the
        custom message to Slack.

        Parameters
        ----------
        custom_message : str
            The diagnostic message to send.

        Returns
        -------
        bool
            True if the message was accepted by Slack (or logged in dry-run mode).
        """
        diagnostic_info = self.get_system_diagnostics()

        slack_data = self._build_message(
            summary=f"🔍 Diagnostic from {self.botname}",
            header="🔍 *Diagnostic Message* 🔍",
            body=f"{custom_message}\n\n*System Information:*\n{diagnostic_info}",
            footer=f"🤖 This is a diagnostic message from {self.botname}.")

        return self._send(slack_data)

    def send_image(self, file_path, comment='', title=None):
        """
        Upload a file (image, plot, FITS preview, ...) to the configured Slack channel.

        Any file type accepted by Slack can be uploaded; image formats such as
        PNG and JPEG are rendered inline in the channel.

        Parameters
        ----------
        file_path : str or pathlib.Path
            Path to the file to upload.
        comment : str, optional
            Message posted together with the file (default: '').
        title : str, optional
            Title shown for the file in Slack. If None, the file name is used
            (default: None).

        Returns
        -------
        bool
            True if the upload completed (or was logged in dry-run mode), False
            if uploads are not configured, the file does not exist, or Slack
            rejected the upload.
        """
        path = pathlib.Path(file_path)

        if not path.is_file():
            self.log.error(f"Cannot upload '{path}' to Slack: file does not exist.")
            return False

        if not self.can_upload:
            self.log.warning(f"Cannot upload '{path}' to Slack: bot token and/or channel ID are not configured.")
            return False

        if self.dry_run:
            self.log.info(f"Dry run: would upload '{path}' ({path.stat().st_size} bytes) to Slack channel "
                          f"{self.channel_id} with comment: {comment!r}")
            return True

        try:
            data = path.read_bytes()
        except OSError as e:
            self.log.error(f"Cannot read '{path}' for Slack upload: {e}")
            return False

        auth_header = {'Authorization': f'Bearer {self.bot_token}'}

        try:
            # Step 1: ask Slack for an upload URL.
            response = requests.post(
                f'{SLACK_API_URL}/files.getUploadURLExternal',
                headers=auth_header,
                data={'filename': path.name, 'length': len(data)},
                timeout=30)
            ticket = self._check_api_response(response, 'files.getUploadURLExternal')
            if ticket is None:
                return False

            # Step 2: send the file contents to that URL.
            response = requests.post(
                ticket['upload_url'],
                files={'file': (path.name, data)},
                timeout=120)
            if response.status_code != 200:
                self.log.error(f"Slack file upload failed. Status: {response.status_code}, Response: {response.text}")
                return False

            # Step 3: complete the upload and share the file in the channel.
            body = {
                'files': [{'id': ticket['file_id'], 'title': title or path.name}],
                'channel_id': self.channel_id,
            }
            if comment:
                body['initial_comment'] = comment

            response = requests.post(
                f'{SLACK_API_URL}/files.completeUploadExternal',
                headers={**auth_header, 'Content-Type': 'application/json; charset=utf-8'},
                json=body,
                timeout=30)
            if self._check_api_response(response, 'files.completeUploadExternal') is None:
                return False
        except requests.RequestException as e:
            self.log.error(f"Network error uploading '{path}' to Slack: {e}")
            return False

        self.log.debug(f"Uploaded '{path}' to Slack channel {self.channel_id}.")
        return True

    def send_alert_with_image(self, custom_message, image_path=None, severity='alert'):
        """
        Send a message and, if uploads are configured, attach an image to it.

        The text message is always sent through the webhook first, so an alert
        is delivered even when the upload is not configured or fails. The image
        is then uploaded as a follow-up message in the configured channel.

        Parameters
        ----------
        custom_message : str
            The message to send.
        image_path : str or pathlib.Path, optional
            Path to the image (or other file) to attach. If None, only the text
            message is sent (default: None).
        severity : {'info', 'alert', 'diagnostic'}, optional
            Which message style to use for the text (default: 'alert').

        Returns
        -------
        str
            The delivery path that was used:

            - ``'upload'``: text was posted and the image was uploaded.
            - ``'webhook'``: text was posted; the image was skipped (no path,
              uploads not configured) or its upload failed.
            - ``'dry_run'``: nothing was sent; payloads were logged.
            - ``'failed'``: the text message could not be posted.

        Raises
        ------
        ValueError
            If ``severity`` is not one of the supported values.
        """
        senders = {
            'info': self.send_info,
            'alert': self.send_alert,
            'diagnostic': self.send_diagnostic,
        }

        if severity not in senders:
            raise ValueError(f"Unknown severity '{severity}'. Expected one of {sorted(senders)}.")

        if not senders[severity](custom_message):
            return 'failed'

        if image_path is None:
            result = 'webhook'
        elif not self.can_upload:
            self.log.info(f"Image '{image_path}' not attached: Slack uploads are not configured.")
            result = 'webhook'
        elif self.send_image(image_path, comment=f"📎 Image for the {severity} above from {self.botname}."):
            result = 'upload'
        else:
            result = 'webhook'

        if self.dry_run:
            return 'dry_run'

        return result

    @staticmethod
    def get_system_diagnostics():
        """
        Collect CPU, memory and disk usage of the host.

        Returns
        -------
        str
            A human-readable, multi-line summary.
        """
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent

        # Cross-platform disk usage monitoring
        disk_info = []
        try:
            if platform.system() == "Windows":
                for drive in ['C:', 'D:']:
                    try:
                        usage = psutil.disk_usage(f'{drive}/')
                        disk_info.append(f"{drive} {usage.percent:.1f}%")
                    except (OSError, FileNotFoundError):
                        continue
            else:
                try:
                    root_usage = psutil.disk_usage('/')
                    disk_info.append(f"/ {root_usage.percent:.1f}%")
                except (OSError, FileNotFoundError):
                    pass
        except Exception:
            disk_info = ["Disk info unavailable"]

        disk_usage_str = ", ".join(disk_info) if disk_info else "No disk info"

        return f"CPU Usage: {cpu_usage}%\nMemory Usage: {memory_usage}%\nDisk Usage: {disk_usage_str}"

    @staticmethod
    def _build_message(summary, header, body, footer):
        """
        Build a Slack Block Kit payload with a header, body and context footer.

        Parameters
        ----------
        summary : str
            Plain-text fallback shown in notifications.
        header : str
            First line of the section (mrkdwn).
        body : str
            Message body (mrkdwn).
        footer : str
            Context line shown below the divider (mrkdwn).

        Returns
        -------
        dict
            The webhook payload.
        """
        return {
            'text': summary,
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"{header}\n\n{body}"
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'context',
                    'elements': [
                        {
                            'type': 'mrkdwn',
                            'text': footer
                        }
                    ]
                }
            ]
        }

    def _check_api_response(self, response, method):
        """
        Validate a Slack Web API response.

        Parameters
        ----------
        response : requests.Response
            The HTTP response.
        method : str
            The API method name, used in log messages.

        Returns
        -------
        dict or None
            The decoded JSON payload if the call succeeded, otherwise None.
        """
        if response.status_code != 200:
            self.log.error(f"Slack API {method} failed. Status: {response.status_code}, Response: {response.text}")
            return None

        try:
            payload = response.json()
        except ValueError:
            self.log.error(f"Slack API {method} returned a non-JSON response: {response.text}")
            return None

        if not payload.get('ok', False):
            self.log.error(f"Slack API {method} returned an error: {payload.get('error', 'unknown')}")
            return None

        return payload

    def _send(self, slack_data):
        """
        Send data to the Slack webhook.

        Parameters
        ----------
        slack_data : dict
            The formatted Slack message data to send.

        Returns
        -------
        bool
            True if the message was accepted by Slack (or logged in dry-run mode).
        """
        if self.dry_run:
            self.log.info(f"Dry run: would post to Slack webhook: {json.dumps(slack_data, ensure_ascii=False)}")
            return True

        try:
            response = requests.post(self.webhook_url, json=slack_data, timeout=30)
        except requests.RequestException as e:
            self.log.error(f"Network error sending Slack message: {e}")
            return False

        if response.status_code == 200:
            self.log.debug("Slack message sent successfully.")
            return True

        self.log.error(f"Failed to send Slack message. Status: {response.status_code}, Response: {response.text}")
        return False


class Watchdog(Service):
    """
    A watchdog service for system monitoring and Slack notifications.

    This service extends the catkit2 Service base class to provide system
    monitoring capabilities with Slack integration. It can send informational
    messages, alerts and system diagnostics via a Slack webhook, and upload
    images or other files when a Slack bot token and channel ID are configured.

    Configuration keys (see the service documentation for details):

    - ``slack_webhook_url``: incoming webhook URL (required unless the
      ``CATKIT2_SLACK_WEBHOOK_URL`` environment variable is set).
    - ``slack_bot_token``: bot token for uploads (optional; the
      ``CATKIT2_SLACK_BOT_TOKEN`` environment variable takes precedence).
    - ``slack_channel_id``: channel ID for uploads (optional).
    - ``botname``: sender name shown in messages (optional; defaults to hostname).
    - ``dry_run``: log payloads instead of posting them (optional; default false).

    Attributes
    ----------
    bot : SlackNotifier
        The Slack notification bot instance.
    """

    def __init__(self):
        super().__init__('watchdog')

        webhook_url = os.environ.get(WEBHOOK_URL_ENV) or self.config.get('slack_webhook_url')
        if not webhook_url:
            raise ValueError(f"The watchdog service needs a Slack webhook URL: set 'slack_webhook_url' in its "
                             f"configuration or the {WEBHOOK_URL_ENV} environment variable.")

        bot_token = os.environ.get(BOT_TOKEN_ENV) or self.config.get('slack_bot_token')
        channel_id = self.config.get('slack_channel_id')
        botname = self.config.get('botname')
        dry_run = bool(self.config.get('dry_run', False))

        self.bot = SlackNotifier(
            webhook_url=webhook_url,
            botname=botname,
            bot_token=bot_token,
            channel_id=channel_id,
            dry_run=dry_run,
            logger=self.log)

        if self.bot.can_upload:
            self.log.info("Slack file upload enabled (bot token and channel ID configured).")
        else:
            self.log.info("Slack file upload not configured; image notifications fall back to text only.")

        if dry_run:
            self.log.warning("Watchdog is in dry-run mode: nothing is posted to Slack.")

        self.make_property('can_upload', self.get_can_upload)
        self.make_property('dry_run', self.get_dry_run)

        self.make_command('send_info', self.send_info)
        self.make_command('send_alert', self.send_alert)
        self.make_command('send_diagnostic', self.send_diagnostic)
        self.make_command('send_alert_with_image', self.send_alert_with_image)
        self.make_command('send_image', self.send_image)

    def get_can_upload(self):
        """
        Whether file uploads are configured.

        Returns
        -------
        bool
        """
        return self.bot.can_upload

    def get_dry_run(self):
        """
        Whether the service is in dry-run mode.

        Returns
        -------
        bool
        """
        return self.bot.dry_run

    def send_info(self, message=None):
        """
        Send an informational message via Slack.

        Parameters
        ----------
        message : str, optional
            The information message to send. If None or empty, no message is sent.

        Returns
        -------
        bool
            True if the message was delivered (or logged in dry-run mode).
        """
        if message:
            return self.bot.send_info(message)

        return False

    def send_alert(self, message=None):
        """
        Send an alert message via Slack.

        Parameters
        ----------
        message : str, optional
            The alert message to send. If None or empty, no message is sent.

        Returns
        -------
        bool
            True if the message was delivered (or logged in dry-run mode).
        """
        if message:
            return self.bot.send_alert(message)

        return False

    def send_diagnostic(self, message=None):
        """
        Send a diagnostic message with system information via Slack.

        Parameters
        ----------
        message : str, optional
            The diagnostic message to send. If None or empty, no message is sent.

        Returns
        -------
        bool
            True if the message was delivered (or logged in dry-run mode).
        """
        if message:
            return self.bot.send_diagnostic(message)

        return False

    def send_alert_with_image(self, message=None, image_path=None, severity='alert'):
        """
        Send a message and attach an image when uploads are configured.

        Parameters
        ----------
        message : str, optional
            The message to send. If None or empty, nothing is sent.
        image_path : str, optional
            Path to the image (or other file) to attach, as seen from the
            machine running the watchdog service (default: None).
        severity : {'info', 'alert', 'diagnostic'}, optional
            Message style to use for the text (default: 'alert').

        Returns
        -------
        str
            One of ``'upload'``, ``'webhook'``, ``'dry_run'``, ``'failed'`` or
            ``'skipped'`` (empty message). See
            :meth:`SlackNotifier.send_alert_with_image`.
        """
        if not message:
            return 'skipped'

        return self.bot.send_alert_with_image(message, image_path=image_path, severity=severity)

    def send_image(self, image_path=None, comment='', title=None):
        """
        Upload a file (plot, camera frame, FITS preview, ...) with a comment.

        Parameters
        ----------
        image_path : str, optional
            Path to the file, as seen from the machine running the watchdog
            service. If None or empty, nothing is uploaded.
        comment : str, optional
            Message posted together with the file (default: '').
        title : str, optional
            Title shown for the file in Slack. Defaults to the file name.

        Returns
        -------
        bool
            True if the upload completed (or was logged in dry-run mode).
        """
        if not image_path:
            return False

        return self.bot.send_image(image_path, comment=comment, title=title)

    def main(self):
        """
        The main function of the service.

        This function is called when the service is started and runs the
        main service loop. The service will continue running until a
        shutdown signal is received.

        Returns
        -------
        None
        """
        while not self.should_shut_down:
            sleep(.1)


if __name__ == '__main__':
    service = Watchdog()
    service.run()
