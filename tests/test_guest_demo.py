"""The public live sample: one fixed photo, no uploads, a shared lifetime quota and a cooldown."""
import json
import time

import pytest

import server
from hivelens import access, config, guest_demo
from tests.test_web import web  # noqa: F401


@pytest.fixture(autouse=True)
def public_preview(monkeypatch):
    monkeypatch.setattr(config, 'AUTH_USER', 'judge')
    monkeypatch.setattr(config, 'AUTH_PASSWORD', 'test-password-not-a-real-secret')
    monkeypatch.setattr(config, 'PUBLIC_READ', True)
    monkeypatch.setattr(config, 'GUEST_DEMO_LIMIT', 2)
    monkeypatch.setattr(config, 'has_api_key', lambda: True)
    monkeypatch.setattr(access, '_attempts', {})
    monkeypatch.setattr(guest_demo, '_active_job', None)
    calls = []

    def fake_job(job_id, hive_id):
        # No model calls in tests: report one progress step and a finished record.
        calls.append(hive_id)
        server._push_job_event(job_id, {'type': 'progress', 'msg': 'Measuring', 'frac': 0.5})
        with server._JOBS_LOCK:
            server._JOBS[job_id].update(status='done', result={'id': 'r1'})
        server._push_job_event(job_id, {'type': 'done', 'result': {'id': 'r1'}})
        guest_demo.finish(job_id)

    monkeypatch.setattr(server, '_run_guest_job', fake_job)
    return calls


def state(web):
    return json.loads(web('/api/state')[2])['guest_demo']


def test_guest_sample_runs_without_login_and_streams_progress(web, public_preview):
    assert state(web) == {'enabled': True, 'limit': 2, 'remaining': 2, 'retry_after': 0,
                          'running': False, 'interval_seconds': guest_demo.INTERVAL}
    status, _, raw = web('/api/guest-inspection', {})
    assert status == 200
    job = json.loads(raw)
    assert public_preview == [job['hive_id']]
    status, _, stream = web(f"/api/jobs/{job['job_id']}/stream")
    assert status == 200 and b'"type": "done"' in stream
    after = state(web)
    assert after['remaining'] == 1 and after['retry_after'] > 0


def test_guest_sample_accepts_no_photo_or_prompt_and_does_not_spend_quota(web):
    for body in ({'image': 'data:image/png;base64,AAAA'}, {'prompt': 'count everything'}, []):
        assert web('/api/guest-inspection', body)[0] == 400
    assert web('/api/guest-inspection', b'{' + b' ' * 200 + b'}')[0] == 400
    assert state(web)['remaining'] == 2


def test_cooldown_and_lifetime_quota(web, monkeypatch):
    assert web('/api/guest-inspection', {})[0] == 200
    status, _, raw = web('/api/guest-inspection', {})
    assert status == 429 and b'again in' in raw
    monkeypatch.setattr(guest_demo, 'INTERVAL', 0)
    time.sleep(0.01)
    assert web('/api/guest-inspection', {})[0] == 200
    status, _, raw = web('/api/guest-inspection', {})
    assert status == 429 and b'quota' in raw
    assert state(web)['remaining'] == 0


def test_guest_sample_is_off_without_limit_and_cross_site_is_rejected(web, monkeypatch):
    assert web('/api/guest-inspection', {}, {'Content-Type': 'application/json', 'Origin': 'https://attacker.example'})[0] == 403
    monkeypatch.setattr(config, 'GUEST_DEMO_LIMIT', 0)
    assert state(web) == {'enabled': False}
    assert web('/api/guest-inspection', {})[0] == 401
    # Other writes and the regular inspection still need owner sign-in.
    monkeypatch.setattr(config, 'GUEST_DEMO_LIMIT', 2)
    assert web('/api/hives', {'name': 'Guest'})[0] == 401
    assert web('/api/inspect', {'hive_id': 'x'})[0] == 401


def test_private_job_streams_stay_private(web):
    with server._JOBS_LOCK:
        server._JOBS['owner1'] = {'workspace': 'demo', 'status': 'running', 'progress': 0, 'message': '', 'events': []}
    assert web('/api/jobs/owner1/stream')[0] == 401
