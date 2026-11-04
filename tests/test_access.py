import json
import time
from urllib.parse import urlencode

import pytest

from hivelens import access, config, store
from tests.test_web import web  # noqa: F401


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_USER', 'judge')
    monkeypatch.setattr(config, 'AUTH_PASSWORD', 'test-password-not-a-real-secret')
    monkeypatch.setattr(config, 'SECURE_COOKIES', True)
    monkeypatch.setattr(access, '_attempts', {})


def login(web, password='test-password-not-a-real-secret'):
    return web('/login', urlencode({'username': 'judge', 'password': password}).encode(),
               {'Content-Type': 'application/x-www-form-urlencoded'})


def test_every_workspace_and_file_requires_login_but_health_does_not(web):
    assert web('/')[0] == 303
    assert web('/healthz')[0] == 200
    for path in ['/api/state', '/api/workspaces/production/state', '/api/research/mustb',
                 '/api/file/hive/record/photo.jpg', '/api/export/hive.zip']:
        assert web(path)[0] == 401
    assert web('/api/hives', {'name': 'Unauthorized'})[0] == 401
    assert store.list_hives() == []
    assert b'test-password' not in web('/login')[2]


def test_cookie_login_reads_writes_and_logout(web):
    status, headers, _ = login(web)
    assert status == 303
    cookie = headers['Set-Cookie']
    assert all(flag in cookie for flag in ['Secure', 'HttpOnly', 'SameSite=Lax'])
    auth = {'Cookie': cookie, 'Content-Type': 'application/json'}
    status, _, raw = web('/api/state', headers=auth)
    assert status == 200 and json.loads(raw)['auth_enabled']
    assert b'test-password' not in raw
    assert web('/api/hives', {'name': 'Allowed'}, auth)[0] == 200
    assert web('/logout', {}, auth)[1]['Set-Cookie'].find('Max-Age=0') >= 0


def test_reject_bad_password_and_cross_site_requests(web):
    assert login(web, 'wrong')[0] == 401
    cookie = login(web)[1]['Set-Cookie']
    headers = {'Cookie': cookie, 'Origin': 'https://attacker.example', 'Content-Type': 'application/json'}
    assert web('/api/hives', {'name': 'Attack'}, headers)[0] == 403
    assert store.list_hives() == []


def test_tampered_expired_and_rotated_sessions_fail(web, monkeypatch):
    cookie = login(web)[1]['Set-Cookie'].split(';')[0]
    assert access.session_valid(cookie)
    assert not access.session_valid(cookie + 'x')
    value = f'{int(time.time()) - 1}.nonce'
    assert not access.session_valid(f'{access.COOKIE}={value}.{access._signature(value)}')
    monkeypatch.setattr(config, 'AUTH_PASSWORD', 'changed-password-not-a-real-secret')
    assert not access.session_valid(cookie)


def test_login_attempts_are_limited(web):
    for _ in range(10):
        assert login(web, 'wrong')[0] == 401
    assert login(web)[0] == 429
