import json
import time
from urllib.parse import urlencode

import pytest

from hivelens import access, config, store
from PIL import Image
from tests.test_web import web  # noqa: F401


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_USER', 'judge')
    monkeypatch.setattr(config, 'AUTH_PASSWORD', 'test-password-not-a-real-secret')
    monkeypatch.setattr(config, 'SECURE_COOKIES', True)
    monkeypatch.setattr(config, 'PUBLIC_READ', False)
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
    store.save_inspection('allowed', {'id': 'r', 'date': '2026-11-05'}, {'board': Image.new('RGB', (2, 2))}, {})
    assert web('/api/file/allowed/r/board.jpg', headers=auth)[1]['Cache-Control'] == 'no-store'
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


def test_public_preview_reads_saved_evidence_but_cannot_write_or_run_models(web, monkeypatch):
    monkeypatch.setattr(config, 'PUBLIC_READ', True)
    from hivelens import settings
    import server
    hive = store.create_hive('Public example')
    store.save_inspection(hive['id'], {'id': 'r', 'date': '2026-11-04'},
                          {'board': Image.new('RGB', (2, 2))}, {})
    monkeypatch.setattr(settings, 'load', lambda: {**settings.DEFAULTS,
        'profile': {**settings.DEFAULTS['profile'], 'email': 'owner-private@example.com'}})
    for path in ['/', '/static/app.js', '/api/state', '/api/workspaces/demo/state',
                 '/api/workspaces/production/state', '/api/research/mustb',
                 f'/api/hive/{hive["id"]}', f'/api/file/{hive["id"]}/r/board.jpg',
                 f'/api/export/{hive["id"]}.zip']:
        assert web(path)[0] == 200, path
    public_state = json.loads(web('/api/state')[2])
    assert public_state['can_write'] is False
    assert public_state['profile']['email'] == ''
    assert b'owner-private' not in web('/api/settings')[2]
    for prefix in ['/api/', '/api/workspaces/demo/', '/api/workspaces/production/']:
        for route in ['inspect', 'benchmark', 'commons', 'seed_apiary', 'hives',
                      'farms', 'settings', 'profile_photo', 'hive_layout', 'hive_style']:
            assert web(prefix + route, {})[0] == 401
    assert not server._JOBS
    assert web('/api/jobs/private/stream')[0] == 401
    assert web('/api/profile_photo')[0] == 401
    cookie = login(web)[1]['Set-Cookie']
    auth = {'Cookie': cookie}
    assert json.loads(web('/api/state', headers=auth)[2])['can_write'] is True
    assert web('/api/hives', {'name': 'Owner-created'}, auth)[0] == 200
