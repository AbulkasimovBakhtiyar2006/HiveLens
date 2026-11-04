"""Usage metering, cost maths and settings (no network, no API key needed)."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from hivelens import config, meta_client, settings, usage
from tests.test_web import web  # noqa: F401  (shared HTTP fixture)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(config, 'CACHE_DIR', tmp_path / 'cache')
    usage.clear_context()
    return tmp_path


PRICES = settings.DEFAULTS['prices']


def test_cost_per_call():
    muse = {'kind': 'reasoning', 'input_tokens': 1_000_000, 'cached_tokens': 400_000, 'output_tokens': 200_000}
    # 600k fresh × 1.25 + 400k cached × 0.15 + 200k × 4.25, per million
    assert usage.call_cost(muse, PRICES) == pytest.approx(0.75 + 0.06 + 0.85)
    assert usage.call_cost({'kind': 'segmentation'}, PRICES) == pytest.approx(0.005)
    assert usage.call_cost({**muse, 'ok': False}, PRICES) == 0


def test_metered_client_records_chat_and_streamed_sam(data_dir):
    chat_usage = SimpleNamespace(prompt_tokens=1200, completion_tokens=300,
                                 prompt_tokens_details=SimpleNamespace(cached_tokens=200),
                                 completion_tokens_details=SimpleNamespace(reasoning_tokens=120))
    events = [SimpleNamespace(type='response.output_text.delta', delta='mask'),
              SimpleNamespace(type='response.completed', response=SimpleNamespace(usage={'input_tokens': 900, 'output_tokens': 50}))]
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(usage=chat_usage))),
        responses=SimpleNamespace(create=lambda **kw: iter(events)),
    )
    meta_client._meter(fake)
    usage.set_context(job_id='job1', job_kind='inspection', hive_id='h1', label='Hive 1')
    fake.chat.completions.create(model=config.REASONING_MODEL, messages=[])
    assert [e.type for e in fake.responses.create(model=config.SEGMENT_MODEL, stream=True)] == \
        ['response.output_text.delta', 'response.completed']
    usage.clear_context()

    rows = usage.read_all()
    assert [(r['kind'], r['input_tokens'], r['output_tokens'], r['job_id']) for r in rows] == [
        ('reasoning', 1200, 300, 'job1'), ('segmentation', 900, 50, 'job1')]
    assert rows[0]['cached_tokens'] == 200 and rows[0]['reasoning_tokens'] == 120


def test_summary_projects_monthly_cost(data_dir):
    usage.set_context(job_id='a', job_kind='inspection', label='Hive 1')
    for _ in range(10):
        usage.record('sam-3.1', 'segmentation')          # 10 × $0.005
    usage.record('muse-spark-1.3', 'reasoning', {'prompt_tokens': 100_000, 'completion_tokens': 10_000})
    usage.clear_context()
    s = usage.summary(PRICES, hive_count=5, inspections_per_month=4, today=date.today())
    per = 10 * 0.005 + 0.1 * 1.25 + 0.01 * 4.25
    assert s['per_inspection'] == pytest.approx(per)
    assert s['projection']['monthly_cost'] == pytest.approx(per * 5 * 4)
    assert s['totals']['today']['calls'] == 11 and s['jobs'][0]['segmentation'] == 10


def test_settings_validation(data_dir):
    saved = settings.save({'profile': {'name': ' Bakhtiyar ', 'role': 'owner'}, 'prices': {'sam': {'per_request': '0.01'}}})
    assert saved['profile']['name'] == 'Bakhtiyar' and saved['prices']['sam']['per_request'] == 0.01
    assert settings.load()['prices']['muse']['output_per_m'] == 4.25   # untouched defaults stay
    for bad in ({'profile': {'email': 'not-an-email'}}, {'profile': {'role': 'queen'}},
                {'prices': {'muse': {'input_per_m': -1}}}, {'planning': {'monthly_budget': 'lots'}}):
        with pytest.raises(ValueError):
            settings.save(bad)


def test_usage_and_settings_endpoints(web):
    status, _, raw = web('/api/settings', {'profile': {'name': 'Ada'}, 'planning': {'inspections_per_hive_month': 2}})
    assert status == 200 and json.loads(raw)['settings']['profile']['name'] == 'Ada'
    assert 'api_key' not in raw.decode().lower().replace('has_api_key', '')
    assert web('/api/settings', {'prices': {'sam': {'per_request': 'x'}}})[0] == 400
    data = json.loads(web('/api/usage')[2])
    assert data['totals']['all']['calls'] == 0 and data['per_inspection'] is None
    assert json.loads(web('/api/state')[2])['profile']['name'] == 'Ada'
