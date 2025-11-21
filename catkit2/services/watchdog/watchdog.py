"""Watchdog service for system monitoring and Slack notifications."""

from catkit2.testbed.service import Service
from time import sleep

import platform
import psutil
import requests


class SlackNotifier:
    """
    A Slack notification service for sending system alerts and diagnostics.

    This class provides methods to send formatted messages to Slack via webhooks,
    including information messages, alerts, and system diagnostic data.

    Parameters
    ----------
    webhook_url : str
        The Slack webhook URL for sending messages
    botname : str, optional
        Custom bot name for the notification source. If None, uses the
        system's hostname (default: None)

    Attributes
    ----------
    botname : str
        The name identifier for this notification bot
    webhook_url : str
        The configured Slack webhook URL
    """

    def __init__(self, webhook_url, botname=None):
        """
        Initialize the SlackNotifier.

        Parameters
        ----------
        webhook_url : str
            The Slack webhook URL for sending messages
        botname : str, optional
            Custom bot name for the notification source. If None, uses the
            system's hostname (default: None)
        """
        if botname is None:
            # Use cross-platform hostname detection instead of Windows-specific COMPUTERNAME
            self.botname = platform.node()
        else:
            self.botname = botname
        self.webhook_url = webhook_url

    def send_info(self, custom_message):
        """
        Send an informational message to Slack.

        Parameters
        ----------
        custom_message : str
            The information message to send

        Returns
        -------
        None
        """
        slack_data = {
            'text': f"ℹ️ Info from {self.botname}",
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"ℹ️ *Information* ℹ️\n\n{custom_message}"
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
                            'text': f"🤖 This is a message from {self.botname}."
                        }
                    ]
                }
            ]
        }
        self._send(slack_data)

    def send_alert(self, custom_message):
        """
        Send an alert message to Slack.

        Parameters
        ----------
        custom_message : str
            The alert message to send

        Returns
        -------
        None
        """
        slack_data = {
            'text': f"🚨 Alert from {self.botname} 🚨",
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"🚨 *Alert Message* 🚨\n\n{custom_message}"
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
                            'text': f"🤖 This is an alert from {self.botname}."
                        }
                    ]
                }
            ]
        }
        self._send(slack_data)

    def send_diagnostic(self, custom_message):
        """
        Send a diagnostic message with system information to Slack.

        This method collects current system metrics including CPU usage,
        memory usage, and disk usage, then sends them along with the
        custom message to Slack.

        Parameters
        ----------
        custom_message : str
            The diagnostic message to send

        Returns
        -------
        None
        """
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent

        # Cross-platform disk usage monitoring
        disk_info = []
        try:
            # Windows-style disk checking
            if platform.system() == "Windows":
                for drive in ['C:', 'D:']:
                    try:
                        usage = psutil.disk_usage(f'{drive}/')
                        disk_info.append(f"{drive} {usage.percent:.1f}%")
                    except (OSError, FileNotFoundError):
                        continue
            else:
                # Unix-style disk checking
                try:
                    root_usage = psutil.disk_usage('/')
                    disk_info.append(f"/ {root_usage.percent:.1f}%")
                except (OSError, FileNotFoundError):
                    pass
        except Exception:
            disk_info = ["Disk info unavailable"]

        disk_usage_str = ", ".join(disk_info) if disk_info else "No disk info"

        diagnostic_info = f"CPU Usage: {cpu_usage}%\nMemory Usage: {memory_usage}%\nDisk Usage: {disk_usage_str}"

        slack_data = {
            'text': f"🔍 Diagnostic from {self.botname}",
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"🔍 *Diagnostic Message* 🔍\n\n{custom_message}\n\n*System Information:*\n{diagnostic_info}"
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
                            'text': f"🤖 This is a diagnostic message from {self.botname}."
                        }
                    ]
                }
            ]
        }
        self._send(slack_data)

    def _send(self, slack_data):
        """
        Send data to Slack webhook.

        Parameters
        ----------
        slack_data : dict
            The formatted Slack message data to send

        Returns
        -------
        None
        """
        try:
            response = requests.post(self.webhook_url, json=slack_data, timeout=30)

            if response.status_code == 200:
                print("Message sent successfully!")
            else:
                print(f"Failed to send message. Status: {response.status_code}, Response: {response.text}")
        except requests.RequestException as e:
            print(f"Network error sending message: {e}")
        except Exception as e:
            print(f"Unexpected error sending message: {e}")


class Watchdog(Service):
    """
    A watchdog service for system monitoring and Slack notifications.

    This service extends the catkit2 Service base class to provide system
    monitoring capabilities with Slack integration. It can send informational
    messages, alerts, and system diagnostics via Slack webhooks.

    The service runs continuously and provides command interface for sending
    different types of notifications.

    Attributes
    ----------
    bot : SlackNotifier
        The Slack notification bot instance
    """

    def __init__(self):
        """
        Initialize the Watchdog service.

        Sets up the service with 'watchdog' identifier and creates a
        SlackNotifier instance using the configured webhook URL.
        """
        super().__init__('watchdog')
        webhook = self.config['slack_webhook_url']
        self.bot = SlackNotifier(webhook_url=webhook)
        self.make_command('send_info', self.send_info)
        self.make_command('send_alert', self.send_alert)
        self.make_command('send_diagnostic', self.send_diagnostic)

    def send_info(self, message=None):
        """
        Send an informational message via Slack.

        Parameters
        ----------
        message : str, optional
            The information message to send. If None or empty, no message is sent

        Returns
        -------
        None
        """
        if message:
            self.bot.send_info(message)

    def send_alert(self, message=None):
        """
        Send an alert message via Slack.

        Parameters
        ----------
        message : str, optional
            The alert message to send. If None or empty, no message is sent

        Returns
        -------
        None
        """
        if message:
            self.bot.send_alert(message)

    def send_diagnostic(self, message=None):
        """
        Send a diagnostic message with system information via Slack.

        Parameters
        ----------
        message : str, optional
            The diagnostic message to send. If None or empty, no message is sent

        Returns
        -------
        None
        """
        if message:
            self.bot.send_diagnostic(message)

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
