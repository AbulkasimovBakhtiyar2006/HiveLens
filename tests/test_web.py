"""HTTP contract checks for the dependency-free web workspace (no model calls)."""
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import server
from hivelens import config, store


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'HIVES_DIR', tmp_path / 'hives')
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(server, '_JOBS', {})
    monkeypatch.setattr(server, 'get_samples', lambda: {
        'boards': [{'name': 'sample.jpg', 'experts': 3}], 'frames': []
    })
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.HiveLensHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def request(path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=5)
        try:
            conn.request('GET' if body is None else 'POST', path,
                         None if body is None else json.dumps(body),
                         headers or {'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()
    yield request
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def test_local_assets_and_allowlist(web):
    for path, content_type in [('/', 'text/html'), ('/static/app.css', 'text/css'),
                               ('/static/app.js', 'text/javascript'), ('/static/mark.svg', 'image/svg+xml')]:
        status, headers, body = web(path)
        assert status == 200 and content_type in headers['Content-Type']
        assert len(body) == int(headers['Content-Length'])
    assert b'cdn.tailwindcss.com' not in web('/')[2]
    assert web('/static/../server.py')[0] == 404
    assert web('/static/.env')[0] == 404


def test_create_hive_and_read_empty_history(web):
    status, _, raw = web('/api/hives', {'name': 'Meadow 01', 'location': 'Orchard'})
    data = json.loads(raw)
    assert status == 200
    hive_id = data['hive']['id']
    state = json.loads(web('/api/state')[2])
    assert state['apiary']['hives'][0]['synthetic'] is False
    assert state['hives'][0]['name'] == 'Meadow 01'
    assert json.loads(web(f'/api/hive/{hive_id}')[2])['inspections'] == []


@pytest.mark.parametrize('change', [
    {'hive_id': '../outside'}, {'date': 'invalid'}, {'days_on_board': 0},
    {'days_on_board': float('nan')}, {'frames_in_hive': 2.5},
    {'board_sample': 'missing.jpg'}, {'board_sample': None},
    {'frame_samples': ['x'] * 9}, {'note': 'x' * 4001},
])
def test_invalid_inspection_never_starts_job(web, change):
    hive = store.create_hive('Test hive')
    payload = {'hive_id': hive['id'], 'date': '2026-11-04', 'board_sample': 'sample.jpg'}
    payload.update(change)
    status, _, body = web('/api/inspect', payload)
    assert status == 400 and json.loads(body)['error']
    assert not server._JOBS


def test_synthetic_provenance_is_in_overview(web):
    hive = store.create_hive('Demo colony')
    store.save_inspection(hive['id'], {'date': '2026-11-04', 'synthetic': True,
                                      'metrics': {}, 'status': {'overall': 'unknown'}}, {}, {})
    data = json.loads(web('/api/state')[2])
    assert data['apiary']['hives'][0]['synthetic'] is True


def test_sse_resumes_after_last_event_without_replaying(web):
    server._JOBS['example'] = {'status': 'done', 'events': [
        {'type': 'progress', 'frac': .2},
        {'type': 'progress', 'frac': .8},
        {'type': 'done', 'result': {'id': 'record'}}
    ]}
    status, headers, body = web('/api/jobs/example/stream', headers={'Last-Event-ID': '1'})
    assert status == 200 and headers['Content-Type'].startswith('text/event-stream')
    assert b'id: 1\n' not in body and b'"frac": 0.2' not in body
    assert b'id: 2\n' in body and b'id: 3\n' in body and b'"type": "done"' in body


def test_non_object_json_returns_error(web):
    assert web('/api/hives', ['not', 'an', 'object'])[0] == 400


def test_farms_group_hives_and_keep_drift_inside_a_farm(web):
    status, _, raw = web('/api/farms', {'name': 'North yard', 'location': 'Talgar'})
    assert status == 200
    north = json.loads(raw)['farm']['id']
    south = json.loads(web('/api/farms', {'name': 'South yard'})[2])['farm']['id']
    a = json.loads(web('/api/hives', {'name': 'A', 'farm_id': north})[2])['hive']
    b = json.loads(web('/api/hives', {'name': 'B', 'farm_id': south})[2])['hive']
    assert a['farm_id'] == north and b['farm_id'] == south
    for hive in (a, b):  # both critical, and at the same yard position in their own farm
        store.save_inspection(hive['id'], {'date': '2026-11-04', 'metrics': {'mites_per_day': 20},
                                           'status': {'overall': 'act'}}, {}, {})
    apiary = json.loads(web('/api/state')[2])['apiary']
    assert {f['name']: f['hive_count'] for f in apiary['farms']} == {'North yard': 1, 'South yard': 1}
    assert apiary['drift_links'] == []


def test_hive_farm_must_exist(web):
    assert web('/api/hives', {'name': 'X', 'farm_id': 'nowhere'})[0] == 400
    hive = store.create_hive('Loose hive')
    assert web('/api/hive_farm', {'hive_id': hive['id'], 'farm_id': 'nowhere'})[0] == 400
    farm = store.create_farm('Home')
    status, _, raw = web('/api/hive_farm', {'hive_id': hive['id'], 'farm_id': farm['id']})
    assert status == 200 and json.loads(raw)['hive']['farm_id'] == farm['id']
    assert web('/api/farms', {'name': ''})[0] == 400


def test_hives_without_a_farm_are_listed_as_unassigned(web):
    store.create_hive('Old hive')
    farms = json.loads(web('/api/state')[2])['apiary']['farms']
    assert farms == [{'id': None, 'name': 'Unassigned', 'location': '', 'hive_count': 1,
                      'counts': {'good': 0, 'watch': 0, 'act': 0, 'unknown': 1}, 'overall': 'unknown'}]
