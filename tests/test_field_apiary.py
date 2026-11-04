import io
import json
import zipfile

from hivelens import store, workspace
from hivelens.field_data import import_apiary
from tests.test_web import web  # noqa: F401


def test_real_apiary_import_is_scoped_idempotent_and_not_an_inspection(web):
    first = import_apiary('5', 'production')
    assert first['farm'] == 'Serra da Lousa'
    assert len(first['hive_ids']) == 7
    assert first['daily_weights'] == 2969 and first['varroa_samples'] == 31
    assert store.list_hives() == [] and store.list_farms() == []
    with workspace.scope('production'):
        hid = first['hive_ids'][0]
        original = store.field_history(hid)
        assert original['hive']['id'] == 'PT_5_2'
        assert original['hive']['varroa'][1]['date'] == '2019-08-30'
        assert original['license'] == 'CC BY 4.0'
        assert store.inspections(hid) == [] and store.metrics_rows(hid) == []
        assert len(store.list_farms()) == 1
        store.save_inspection(hid, {'id': 'own-photo', 'date': '2026-11-05', 'metrics': {'mites_per_day': 2}}, {}, {})
    second = import_apiary('5', 'production')
    assert first == second
    with workspace.scope('production'):
        assert len(store.list_hives()) == 7 and len(store.list_farms()) == 1
        assert store.field_history(hid) == original
        assert store.inspections(hid)[0]['id'] == 'own-photo'
    state = json.loads(web('/api/workspaces/production/state')[2])
    assert len(state['apiary']['hives']) == 7
    assert state['apiary']['drift_links'] == []
    assert state['apiary']['summary']['act'] == 0
    row = next(h for h in state['apiary']['hives'] if h['id'] == hid)
    assert row['field_archive']['study_hive_id'] == 'PT_5_2'
    assert row['mites_per_day'] == 2  # Own photo, never substituted from the archived wash values.
    other = next(h for h in state['apiary']['hives'] if h['id'] != hid)
    assert other['mites_per_day'] is None and other['latest_date'] is None
    history = json.loads(web(f'/api/workspaces/production/hive/{hid}')[2])
    assert history['field_history'] == original and len(history['inspections']) == 1
    assert json.loads(web(f'/api/workspaces/demo/hive/{hid}')[2])['field_history'] is None
    z = zipfile.ZipFile(io.BytesIO(web(f'/api/workspaces/production/export/{hid}.zip')[2]))
    assert json.loads(z.read(f'{hid}/field_history.json')) == original
    assert json.loads(z.read(f'{hid}/field_history.json'))['manifest']
