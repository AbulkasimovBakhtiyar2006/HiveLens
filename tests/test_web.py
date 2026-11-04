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
                               ('/static/app.js', 'text/javascript'), ('/static/mark.svg', 'image/svg+xml'),
                               ('/designs', 'text/html'), ('/designs/', 'text/html'),
                               ('/static/layouts.css', 'text/css'), ('/static/layouts.js', 'text/javascript'),
                               ('/static/layouts-next.css', 'text/css'), ('/static/layouts-next.js', 'text/javascript')]:
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


def test_demo_video_supports_browser_seeking(web):
    status, headers, body = web('/static/comb-demo.mp4', headers={'Range': 'bytes=0-31'})
    assert status == 206 and len(body) == 32
    assert headers['Content-Type'] == 'video/mp4'
    assert headers['Content-Range'].startswith('bytes 0-31/')
    assert b'ftyp' in body
    assert web('/static/comb-demo.mp4', headers={'Range': 'bytes=999999999-'} )[0] == 416
    assert web('/static/camera.js')[0] == 200


def test_capture_sources_validated_before_starting_job(web):
    hive = store.create_hive('Camera hive')
    payload = {'hive_id': hive['id'], 'date': '2026-11-04', 'frames_b64': ['image']}
    source = {'source': 'camera', 'name': 'Back camera', 'captured_at': '2026-11-04T16:00:00Z',
              'width': 1920, 'height': 1080, 'video_seconds': None}
    payload['capture_sources'] = {'frame_1': source}
    server._validate_inspection_payload(payload)
    for bad in [None, {'board': source}, {'frame_1': {**source, 'width': 0}},
                {'frame_1': {**source, 'source': 'live-youtube'}},
                {'frame_1': {**source, 'video_seconds': float('nan')}}]:
        payload['capture_sources'] = bad
        assert web('/api/inspect', payload)[0] == 400
    assert not server._JOBS


def test_demo_video_analysis_does_not_change_colony_status_or_trends(web):
    hive = store.create_hive('Real colony')
    store.save_inspection(hive['id'], {'id': 'real', 'date': '2026-11-03',
        'metrics': {'mites_per_day': 1}, 'status': {'overall': 'good'}}, {}, {})
    store.save_inspection(hive['id'], {'id': 'demo', 'date': '2026-11-04', 'demo_capture': True,
        'metrics': {'mites_per_day': 90}, 'status': {'overall': 'act'}}, {}, {})
    overview = json.loads(web('/api/state')[2])['apiary']['hives'][0]
    assert overview['overall'] == 'good' and overview['mites_per_day'] == 1
    history = json.loads(web(f'/api/hive/{hive["id"]}')[2])
    assert len(history['inspections']) == 2
    assert len(history['metrics_rows']) == 1
    assert len(store.history_before(hive['id'], '2026-11-05')) == 1


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


# ── Farm location and weather (network calls are faked) ────────────────
from hivelens import place  # noqa: E402


@pytest.mark.parametrize('text, expected', [
    ('https://www.google.com/maps/place/Talgar/@43.30,77.23,13z/data=!3m1!4b1!3d43.30235!4d77.23811', (43.30235, 77.23811)),
    ('https://www.google.com/maps/@43.25,76.95,15z', (43.25, 76.95)),
    ('https://maps.google.com/?q=43.1,77.5', (43.1, 77.5)),
    ('43.30, 77.24', (43.30, 77.24)),
    ('Talgar, Kazakhstan', None),
    ('95, 200', None),
])
def test_parse_coordinates(text, expected):
    assert place.parse_coordinates(text) == expected


@pytest.mark.parametrize('temp, wind, rain, code, day, level', [
    (20, 2, 0, 0, True, 'good'),
    (11, 2, 0, 0, True, 'limited'),
    (20, 7, 0, 1, True, 'limited'),
    (20, 12, 0, 1, True, 'none'),
    (8, 1, 0, 0, True, 'none'),
    (20, 1, 1.5, 61, True, 'none'),
    (20, 1, 0, 0, False, 'none'),
])
def test_bee_flight(temp, wind, rain, code, day, level):
    assert place.bee_flight(temp, wind, rain, code, day)['level'] == level


def test_farm_location_breed_and_weather(web, monkeypatch):
    calls = []

    def fake_get_json(url, timeout=8.0):
        calls.append(url)
        if 'geocoding' in url:
            return {'results': [{'name': 'Talghar', 'admin1': 'Almaty Region', 'country': 'Kazakhstan',
                                 'country_code': 'KZ', 'latitude': 43.3, 'longitude': 77.24, 'elevation': 980}]}
        hours = [f'2026-11-04T{h:02d}:00' for h in range(24)]
        return {'timezone': 'Asia/Almaty', 'elevation': 980,
                'current': {'time': '2026-11-04T12:00', 'temperature_2m': 18, 'wind_speed_10m': 3, 'precipitation': 0,
                            'weather_code': 2, 'is_day': 1, 'wind_gusts_10m': 5, 'wind_direction_10m': 90},
                'hourly': {'time': hours, 'temperature_2m': [18] * 24, 'precipitation_probability': [10] * 24,
                           'precipitation': [0] * 24, 'weather_code': [2] * 24, 'wind_speed_10m': [3] * 24,
                           'wind_direction_10m': [90] * 24, 'wind_gusts_10m': [5] * 24, 'is_day': [1] * 24},
                'daily': {'time': ['2026-11-04'], 'weather_code': [61], 'temperature_2m_max': [19], 'temperature_2m_min': [6],
                          'precipitation_sum': [2.5], 'precipitation_probability_max': [70], 'wind_speed_10m_max': [6],
                          'wind_gusts_10m_max': [11]}}

    monkeypatch.setattr(place, '_get_json', fake_get_json)
    monkeypatch.setattr(place, '_cache', {})
    status, _, raw = web('/api/farms', {'name': 'Talgar', 'location': 'Talgar, Kazakhstan', 'breed': 'carpatica'})
    farm = json.loads(raw)['farm']
    assert status == 200 and farm['lat'] == 43.3 and farm['breed'] == 'carpatica' and farm['country_code'] == 'KZ'

    weather = json.loads(web(f"/api/weather/{farm['id']}")[2])
    assert weather['current']['scene'] == 'partly' and weather['current']['flight']['level'] == 'good'
    assert len(weather['hourly']) == 12 and weather['daily'][0]['scene'] == 'rain'

    # A map link wins over the place name and needs no geocoder call.
    calls.clear()
    status, _, raw = web('/api/farm_update', {'farm_id': farm['id'], 'name': 'Talgar', 'location': 'Talgar',
                                              'maps_url': 'https://www.google.com/maps/@43.1,77.5,14z'})
    farm = json.loads(raw)['farm']
    assert status == 200 and (farm['lat'], farm['lon']) == (43.1, 77.5) and 'breed' not in farm
    assert not any('geocoding' in u for u in calls)


def test_farm_without_location_has_no_weather(web):
    farm = json.loads(web('/api/farms', {'name': 'Home'})[2])['farm']
    status, _, raw = web(f"/api/weather/{farm['id']}")
    assert status == 409 and 'location' in json.loads(raw)['error']
    assert web('/api/farms', {'name': 'X', 'breed': 'unicorn'})[0] == 400
    assert web('/api/farm_update', {'farm_id': 'nowhere', 'name': 'X'})[0] == 404
