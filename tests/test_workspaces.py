"""Workspaces are separate data stores, not an authentication boundary."""
import io
import json
import threading
import zipfile
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

import server
from hivelens import settings, store, usage, workspace
from tests.test_web import web  # noqa: F401


def test_workspace_api_keeps_same_named_hives_and_files_separate(web):
    for mode, location in [('demo', 'Sandbox'), ('production', 'Real yard')]:
        status, _, raw = web(f'/api/workspaces/{mode}/hives', {'name': 'Hive one', 'location': location})
        assert status == 200
        assert json.loads(raw)['hive']['id'] == 'hive-one'
        with workspace.scope(mode):
            store.save_inspection('hive-one', {'id': mode, 'date': '2026-11-05', 'metrics': {}},
                                  {'board': Image.new('RGB', (4, 4), 'white')}, {})
    for mode, location, other in [('demo', 'Sandbox', 'production'), ('production', 'Real yard', 'demo')]:
        prefix = f'/api/workspaces/{mode}'
        state = json.loads(web(prefix + '/state')[2])
        assert state['workspace'] == mode and state['hives'][0]['location'] == location
        assert len(state['hives']) == 1
        assert web(f'{prefix}/file/hive-one/{mode}/board.jpg')[0] == 200
        assert web(f'{prefix}/file/hive-one/{other}/board.jpg')[0] == 404
        history = json.loads(web(prefix + '/hive/hive-one')[2])
        assert [r['id'] for r in history['inspections']] == [mode]
        z = zipfile.ZipFile(io.BytesIO(web(prefix + '/export/hive-one.zip')[2]))
        assert any('/' + mode + '/' in n for n in z.namelist())
        assert not any('/' + other + '/' in n for n in z.namelist())
    assert json.loads(web('/api/state')[2])['workspace'] == 'demo'
    assert web('/api/workspaces/invalid/state')[0] == 400


def test_production_starts_empty_and_cannot_seed_samples(web):
    store.create_hive('Demo only')
    state = json.loads(web('/api/workspaces/production/state')[2])
    assert state['hives'] == [] and state['apiary']['farms'] == []
    assert state['samples'] == {'boards': [], 'frames': []}
    assert web('/api/workspaces/production/seed_apiary', {})[0] == 403
    assert web('/api/workspaces/production/commons', {})[0] == 403
    web('/api/workspaces/production/hives', {'name': 'Own hive'})
    base = {'hive_id': 'own-hive', 'date': '2026-11-05'}
    for payload in [dict(base, board_sample='sample.jpg'), dict(base, frame_samples=['sample.jpg']),
                    dict(base, frames_b64=['image'], capture_sources={'frame_1': {'source': 'demo'}})]:
        status, _, raw = web('/api/workspaces/production/inspect', payload)
        assert status == 400 and 'demo workspace' in json.loads(raw)['error']
    assert not server._JOBS


def test_settings_profile_usage_and_worker_context_are_isolated(web):
    for mode in workspace.MODES:
        prefix = f'/api/workspaces/{mode}'
        assert web(prefix + '/settings', {'profile': {'name': mode}})[0] == 200
        with workspace.scope(mode):
            settings.set_photo(Image.new('RGB', (20, 20), 'red' if mode == 'demo' else 'blue'))
            usage.set_context(job_id=mode)
            with ThreadPoolExecutor(max_workers=2) as pool:
                entries = [pool.submit(copy_context().run, usage.record, 'sam', 'segmentation') for _ in range(2)]
                assert all(f.result()['workspace'] == mode for f in entries)
            assert [r['job_id'] for r in usage.read_all()] == [mode, mode]
            usage.clear_context()
    for mode in workspace.MODES:
        raw = web(f'/api/workspaces/{mode}/settings')[2]
        assert json.loads(raw)['settings']['profile']['name'] == mode
    assert web('/api/workspaces/demo/profile_photo')[2] != web('/api/workspaces/production/profile_photo')[2]
    assert workspace.current() == 'demo'


def test_background_job_preserves_production_context_and_stream_scope(web, monkeypatch):
    done = threading.Event()
    result = []
    def run(job_id, body):
        result.append(workspace.current())
        store.create_hive('Created by worker')
        with server._JOBS_LOCK:
            server._JOBS[job_id]['status'] = 'done'
        done.set()
    monkeypatch.setattr(server, '_run_inspection_job', run)
    monkeypatch.setattr(server.config, 'has_api_key', lambda: True)
    web('/api/workspaces/production/hives', {'name': 'Input hive'})
    status, _, raw = web('/api/workspaces/production/inspect', {
        'hive_id': 'input-hive', 'date': '2026-11-05', 'frames_b64': ['stubbed in test']})
    assert status == 200 and done.wait(3)
    assert result == ['production']
    job_id = json.loads(raw)['job_id']
    assert web(f'/api/workspaces/demo/jobs/{job_id}/stream')[0] == 404
    assert web(f'/api/workspaces/production/jobs/{job_id}/stream')[0] == 200
    assert store.list_hives() == []
    assert len(json.loads(web('/api/workspaces/production/state')[2])['hives']) == 2


def test_empty_production_profile_removal_and_public_archive(web):
    assert web('/api/workspaces/production/profile_photo', {'remove': True})[0] == 200
    for mode in workspace.MODES:
        status, _, raw = web(f'/api/workspaces/{mode}/research/mustb')
        assert status == 200
        data = json.loads(raw)
        assert data['summary']['hives'] == 57
        assert data['source_url'] == 'https://zenodo.org/records/5148318'
    assert web('/static/reference.js')[0] == 200
    assert web('/static/reference.css')[0] == 200
