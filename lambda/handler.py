import base64
import hashlib
import hmac
import json
import logging
import os
import random
import time
import urllib.parse
import urllib.request
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ssm = boto3.client('ssm')
_PARAMETER_CACHE: Dict[str, str] = {}
_REACTIONS = [icon for icon in os.environ.get('SLACK_REACTIONS', 'thumbsup,tada,rocket').split(',') if icon]


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    logger.debug('Received event: %s', event)
    raw_body = event.get('body') or ''
    if event.get('isBase64Encoded') and raw_body:
        raw_body = base64.b64decode(raw_body).decode('utf-8')

    headers = {str(k).lower(): v for k, v in (event.get('headers') or {}).items()}

    if not verify_signature(headers, raw_body):
        logger.warning('Slack signature verification failed')
        return _response(401, {'message': 'invalid signature'})

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.exception('Failed to decode Slack payload')
        return _response(400, {'message': 'invalid payload'})

    if payload.get('type') == 'url_verification':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/plain'},
            'body': payload.get('challenge', ''),
        }

    if payload.get('type') != 'event_callback':
        logger.info('Ignoring non event_callback payload: %s', payload.get('type'))
        return _response(200, {'status': 'ignored'})

    event_body = payload.get('event') or {}
    if _should_react(event_body):
        try:
            reaction = send_reaction(event_body['channel'], event_body['ts'])
            logger.info('Added reaction %s to message %s', reaction, event_body['ts'])
        except Exception:  # pragma: no cover - Lambda logging only
            logger.exception('Failed to react to message')
            return _response(500, {'message': 'failed to call Slack'})

    return _response(200, {'status': 'ok'})


def _should_react(event_body: Dict[str, Any]) -> bool:
    if event_body.get('type') != 'message':
        return False
    if event_body.get('subtype'):
        return False
    if event_body.get('bot_id'):
        return False
    return bool(event_body.get('channel') and event_body.get('ts'))


def verify_signature(headers: Dict[str, str], raw_body: str) -> bool:
    signing_secret = _get_parameter('SLACK_SIGNING_SECRET_PARAMETER')
    timestamp = headers.get('x-slack-request-timestamp')
    slack_signature = headers.get('x-slack-signature', '')

    if not signing_secret or not timestamp or not slack_signature:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - timestamp_int) > 60 * 5:
        return False

    sig_basestring = f'v0:{timestamp}:{raw_body}'
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, slack_signature)


def send_reaction(channel: str, timestamp: str) -> str:
    token = _get_parameter('SLACK_BOT_TOKEN_PARAMETER')
    if not token:
        raise RuntimeError('Slack bot token is not configured')

    reaction = random.choice(_REACTIONS or ['thumbsup'])
    payload = urllib.parse.urlencode(
        {
            'channel': channel,
            'timestamp': timestamp,
            'name': reaction,
        }
    ).encode('utf-8')

    request = urllib.request.Request(
        'https://slack.com/api/reactions.add',
        data=payload,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Bearer {token}',
        },
        method='POST',
    )

    with urllib.request.urlopen(request, timeout=3) as response:
        response_body = response.read().decode('utf-8')
        data = json.loads(response_body)

    if not data.get('ok'):
        raise RuntimeError(f"Slack API error: {data}")

    return reaction


def _get_parameter(env_key: str) -> str:
    parameter_name = os.environ.get(env_key)
    if not parameter_name:
        raise RuntimeError(f'Missing environment variable: {env_key}')

    if parameter_name in _PARAMETER_CACHE:
        return _PARAMETER_CACHE[parameter_name]

    try:
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
    except ClientError as error:
        logger.error('Unable to read parameter %s: %s', parameter_name, error)
        raise

    value = response['Parameter']['Value']
    _PARAMETER_CACHE[parameter_name] = value
    return value


def _response(status_code: int, body: Any) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }
