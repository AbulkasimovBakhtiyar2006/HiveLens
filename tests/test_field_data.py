"""The bundled archive must preserve real chronology, protocols and provenance."""
import json
from pathlib import Path
from collections import Counter


def test_field_archive_integrity():
    d = json.loads((Path(__file__).resolve().parents[1] / 'hivelens/datasets/mustb.json').read_text())
    assert d['license'] == 'CC BY 4.0'
    assert d['doi'] == '10.5281/zenodo.5148318'
    assert len(d['hives']) == len({h['id'] for h in d['hives']}) == 57
    assert {h['country'] for h in d['hives']} == {'DK', 'PT'}
    assert sum(len(h['weight']) for h in d['hives']) == 13245
    assert sum(len(h['varroa']) for h in d['hives']) == 143
    assert len(d['manifest']) == 4
    assert all(len(f['sha256']) == 64 and f['checksum'].startswith('md5:') for f in d['manifest'])
    for h in d['hives']:
        for key in ['weight', 'varroa']:
            dates = [r['date'] for r in h[key]]
            assert dates == sorted(dates)
            assert all('2019-01-01' <= date <= '2020-12-31' for date in dates)
        assert all(w['n'] >= 1 and w['value'] > 0 for w in h['weight'])
        for r in h['varroa']:
            assert r['source_id'] and r['method'] == 'Soapy water method'
            assert r['unit'] == 'number per 100 adult bees'
            if r['result_type'] == 'LOD':
                assert r['value'] is None and r['raw_value'] == ''
            else:
                assert r['result_type'] == 'VAL' and r['value'] == float(r['raw_value'])
    assert d['omitted_varroa'] == {'Mite down-fall in 24h': 33}
    assert len(d['excluded_dates']) == 4
    assert d['unmatched_weight_rows'] == 1658
    example = next(h for h in d['hives'] if h['id'] == 'PT_5_2')
    assert len(example['weight']) > 500 and len(example['varroa']) == 6
    assert example['varroa'][1]['source_id'] == 'Var139'
    assert example['varroa'][1]['date'] == '2019-08-30'
    assert example['varroa'][1]['value'] == 2.5
