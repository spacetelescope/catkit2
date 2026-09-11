"""Unit tests for the SlackNotifier used by the watchdog service.

These tests mock ``requests`` so they never talk to Slack and do not need a running testbed.
"""
import logging

import pytest

from catkit2.services.watchdog import watchdog
from catkit2.services.watchdog.watchdog import SlackNotifier

WEBHOOK = 'https://hooks.slack.com/services/T/B/X'


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
        return self._payload


class FakeRequests:
    """Records posts and returns canned responses keyed by URL."""

    class RequestException(Exception):
        pass

    def __init__(self, responses=None, raise_for=None):
        self.responses = responses or {}
        self.raise_for = raise_for or set()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url in self.raise_for:
            raise self.RequestException('boom')
        return self.responses.get(url, FakeResponse())


def upload_responses():
    return {
        f'{watchdog.SLACK_API_URL}/files.getUploadURLExternal': FakeResponse(
            payload={'ok': True, 'upload_url': 'https://files.slack.com/upload/abc', 'file_id': 'F123'}),
        'https://files.slack.com/upload/abc': FakeResponse(),
        f'{watchdog.SLACK_API_URL}/files.completeUploadExternal': FakeResponse(payload={'ok': True}),
    }


@pytest.fixture
def fake_requests(monkeypatch):
    fake = FakeRequests(responses=upload_responses())
    monkeypatch.setattr(watchdog, 'requests', fake)
    return fake


@pytest.fixture
def image_file(tmp_path):
    path = tmp_path / 'frame.png'
    path.write_bytes(b'\x89PNG fake')
    return path


def test_text_messages_post_to_webhook(fake_requests):
    bot = SlackNotifier(WEBHOOK, botname='testbed-pc')

    assert bot.send_info('hello') is True
    assert bot.send_alert('careful') is True

    urls = [url for url, _ in fake_requests.calls]
    assert urls == [WEBHOOK, WEBHOOK]

    info_payload = fake_requests.calls[0][1]['json']
    assert 'testbed-pc' in info_payload['text']
    assert 'hello' in info_payload['blocks'][0]['text']['text']


def test_diagnostic_includes_system_info(fake_requests):
    bot = SlackNotifier(WEBHOOK, botname='testbed-pc')

    assert bot.send_diagnostic('health') is True

    body = fake_requests.calls[0][1]['json']['blocks'][0]['text']['text']
    assert 'health' in body
    assert 'CPU Usage' in body


def test_webhook_failure_returns_false(monkeypatch):
    fake = FakeRequests(responses={WEBHOOK: FakeResponse(status_code=500, text='oops')})
    monkeypatch.setattr(watchdog, 'requests', fake)
    bot = SlackNotifier(WEBHOOK)

    assert bot.send_alert('x') is False


def test_network_error_returns_false(monkeypatch):
    fake = FakeRequests(raise_for={WEBHOOK})
    monkeypatch.setattr(watchdog, 'requests', fake)
    bot = SlackNotifier(WEBHOOK)

    assert bot.send_alert('x') is False


def test_dry_run_sends_nothing(fake_requests, image_file, caplog):
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1', dry_run=True)

    with caplog.at_level(logging.INFO, logger=watchdog.__name__):
        assert bot.send_info('hello') is True
        assert bot.send_image(image_file, comment='c') is True
        assert bot.send_alert_with_image('a', image_path=image_file) == 'dry_run'

    assert fake_requests.calls == []
    assert 'Dry run' in caplog.text


def test_can_upload_requires_token_and_channel():
    assert SlackNotifier(WEBHOOK).can_upload is False
    assert SlackNotifier(WEBHOOK, bot_token='xoxb-1').can_upload is False
    assert SlackNotifier(WEBHOOK, channel_id='C1').can_upload is False
    assert SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1').can_upload is True


def test_send_image_without_upload_config(fake_requests, image_file):
    bot = SlackNotifier(WEBHOOK)

    assert bot.send_image(image_file) is False
    assert fake_requests.calls == []


def test_send_image_missing_file(fake_requests, tmp_path):
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_image(tmp_path / 'nope.png') is False
    assert fake_requests.calls == []


def test_send_image_three_step_upload(fake_requests, image_file):
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_image(image_file, comment='look', title='Frame') is True

    urls = [url for url, _ in fake_requests.calls]
    assert urls == [
        f'{watchdog.SLACK_API_URL}/files.getUploadURLExternal',
        'https://files.slack.com/upload/abc',
        f'{watchdog.SLACK_API_URL}/files.completeUploadExternal',
    ]

    ticket_kwargs = fake_requests.calls[0][1]
    assert ticket_kwargs['headers']['Authorization'] == 'Bearer xoxb-1'
    assert ticket_kwargs['data'] == {'filename': 'frame.png', 'length': image_file.stat().st_size}

    upload_kwargs = fake_requests.calls[1][1]
    assert upload_kwargs['files']['file'][0] == 'frame.png'

    complete_kwargs = fake_requests.calls[2][1]
    assert complete_kwargs['json'] == {
        'files': [{'id': 'F123', 'title': 'Frame'}],
        'channel_id': 'C1',
        'initial_comment': 'look',
    }


def test_send_image_api_error(monkeypatch, image_file):
    responses = upload_responses()
    responses[f'{watchdog.SLACK_API_URL}/files.completeUploadExternal'] = FakeResponse(
        payload={'ok': False, 'error': 'not_in_channel'})
    fake = FakeRequests(responses=responses)
    monkeypatch.setattr(watchdog, 'requests', fake)
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_image(image_file) is False


def test_alert_with_image_uploads(fake_requests, image_file):
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_alert_with_image('problem', image_path=image_file) == 'upload'

    urls = [url for url, _ in fake_requests.calls]
    # Text goes out through the webhook before the upload starts.
    assert urls[0] == WEBHOOK
    assert len(urls) == 4


def test_alert_with_image_falls_back_to_text(fake_requests, image_file):
    bot = SlackNotifier(WEBHOOK)

    assert bot.send_alert_with_image('problem', image_path=image_file) == 'webhook'
    assert bot.send_alert_with_image('problem') == 'webhook'
    assert [url for url, _ in fake_requests.calls] == [WEBHOOK, WEBHOOK]


def test_alert_with_image_upload_failure_still_delivers_text(monkeypatch, image_file):
    fake = FakeRequests(responses=upload_responses(),
                        raise_for={f'{watchdog.SLACK_API_URL}/files.getUploadURLExternal'})
    monkeypatch.setattr(watchdog, 'requests', fake)
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_alert_with_image('problem', image_path=image_file) == 'webhook'
    assert fake.calls[0][0] == WEBHOOK


def test_alert_with_image_text_failure(monkeypatch, image_file):
    fake = FakeRequests(responses={WEBHOOK: FakeResponse(status_code=403)})
    monkeypatch.setattr(watchdog, 'requests', fake)
    bot = SlackNotifier(WEBHOOK, bot_token='xoxb-1', channel_id='C1')

    assert bot.send_alert_with_image('problem', image_path=image_file) == 'failed'
    # No upload is attempted when the text could not be posted.
    assert len(fake.calls) == 1


def test_alert_with_image_severity(fake_requests):
    bot = SlackNotifier(WEBHOOK, botname='pc')

    assert bot.send_alert_with_image('note', severity='info') == 'webhook'
    assert 'Information' in fake_requests.calls[0][1]['json']['blocks'][0]['text']['text']

    with pytest.raises(ValueError):
        bot.send_alert_with_image('note', severity='panic')
