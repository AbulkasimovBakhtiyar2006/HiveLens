"""Yard layout, hive colours and the profile photo (no network)."""
import base64
import io
import json

from PIL import Image

from hivelens import store
from tests.test_web import web  # noqa: F401  (shared HTTP fixture)


def _hives(web):
    return {h['id']: h for h in json.loads(web('/api/state')[2])['apiary']['hives']}


def test_saved_positions_drive_drift_links(web):
    farm = store.create_farm('Yard')
    a = store.create_hive('A', farm_id=farm['id'])
    b = store.create_hive('B', farm_id=farm['id'])
    store.save_inspection(a['id'], {'date': '2026-11-04', 'metrics': {'mites_per_day': 20}, 'status': {'overall': 'act'}}, {}, {})
    far = [{'hive_id': a['id'], 'x_m': 0, 'y_m': 0}, {'hive_id': b['id'], 'x_m': 10, 'y_m': 0}]
    assert web('/api/hive_layout', {'farm_id': farm['id'], 'positions': far})[0] == 200
    state = json.loads(web('/api/state')[2])['apiary']
    assert state['drift_links'] == [] and _hives(web)[b['id']]['placed'] is True

    near = [{'hive_id': a['id'], 'x_m': 0, 'y_m': 0}, {'hive_id': b['id'], 'x_m': 2, 'y_m': 1.5}]
    links = json.loads(web('/api/hive_layout', {'farm_id': farm['id'], 'positions': near})[2])['apiary']['drift_links']
    assert [(l['from_id'], l['to_id'], l['distance_m'], l['risk']) for l in links] == [(a['id'], b['id'], 2.5, 'high')]

    assert web('/api/hive_layout', {'farm_id': farm['id'], 'reset': True})[0] == 200
    assert _hives(web)[a['id']]['placed'] is False


def test_layout_rejects_foreign_hives_and_bad_numbers(web):
    farm = store.create_farm('Yard')
    other = store.create_hive('Elsewhere')
    mine = store.create_hive('Mine', farm_id=farm['id'])
    assert web('/api/hive_layout', {'farm_id': farm['id'], 'positions': [{'hive_id': other['id'], 'x_m': 1, 'y_m': 1}]})[0] == 400
    assert web('/api/hive_layout', {'farm_id': farm['id'], 'positions': [{'hive_id': mine['id'], 'x_m': 'far', 'y_m': 1}]})[0] == 400
    assert web('/api/hive_layout', {'farm_id': farm['id'], 'positions': [{'hive_id': mine['id'], 'x_m': 9999, 'y_m': 1}]})[0] == 400


def test_hive_colour(web):
    hive = store.create_hive('Painted')
    assert json.loads(web('/api/hive_style', {'hive_id': hive['id'], 'color': '#6f9fd8'})[2])['hive']['color'] == '#6f9fd8'
    assert _hives(web)[hive['id']]['color'] == '#6f9fd8'
    assert web('/api/hive_style', {'hive_id': hive['id'], 'color': 'blue'})[0] == 400
    assert 'color' not in json.loads(web('/api/hive_style', {'hive_id': hive['id'], 'color': None})[2])['hive']


def test_profile_photo_upload_and_remove(web):
    buf = io.BytesIO()
    Image.new('RGB', (600, 300), (233, 196, 106)).save(buf, 'PNG')
    data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    status, _, raw = web('/api/profile_photo', {'image': data_url})
    assert status == 200 and json.loads(raw)['settings']['profile']['photo_version'] > 0
    status, headers, body = web('/api/profile_photo')
    assert status == 200 and headers['Content-Type'] == 'image/jpeg'
    assert Image.open(io.BytesIO(body)).size == (256, 256)
    # A normal settings save cannot fake or clear the photo version.
    assert json.loads(web('/api/settings', {'profile': {'photo_version': 1}})[2])['settings']['profile']['photo_version'] > 1
    assert web('/api/profile_photo', {'image': 'data:image/png;base64,bm90IGFuIGltYWdl'})[0] == 400
    assert json.loads(web('/api/profile_photo', {'remove': True})[2])['settings']['profile']['photo_version'] == 0
    assert web('/api/profile_photo')[0] == 404
