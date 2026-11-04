"""Download pinned CC BY 4.0 field data; build a provenance-preserving reference archive.

Run: python scripts/import_mustb.py. No model calls and no operational hive writes.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RECORD = '5148318'
SOURCE = f'https://zenodo.org/records/{RECORD}'
FILES = ('01_Sites_coord.csv', 'Table_III_Hives.csv', 'Table_V_Colony_inspection.zip', 'Table_VI_SSD2.csv')


def build(raw: Path) -> dict:
    metadata = json.loads((raw / 'metadata.json').read_text())
    if str(metadata['id']) != RECORD or metadata['metadata']['license']['id'] != 'cc-by-4.0':
        raise ValueError('Unexpected dataset version or license.')
    manifest = []
    for name in FILES:
        expected = next(f for f in metadata['files'] if f['key'] == name)
        content = (raw / name).read_bytes()
        if 'md5:' + hashlib.md5(content).hexdigest() != expected['checksum']:
            raise ValueError(f'Checksum mismatch: {name}')
        manifest.append({'file': name, 'source_url': expected['links']['self'], 'checksum': expected['checksum'], 'sha256': hashlib.sha256(content).hexdigest()})
    def rows(name):
        return list(csv.DictReader((raw / name).open(encoding='utf-8-sig', newline='')))
    sites = {r['siteNo']: r for r in rows('01_Sites_coord.csv')}
    hives = {}
    for r in rows('Table_III_Hives.csv'):
        if r['siteNo'] not in sites:
            continue
        site = sites[r['siteNo']]
        hives[(r['siteNo'], r['hiveNo'])] = {
            'id': r['hiveId'], 'hive_no': r['hiveNo'], 'site_id': r['siteNo'],
            'site': site['siteName'], 'country': r['sampCountry'], 'subspecies': r['subSpecies'],
            'weight': [], 'varroa': [],
        }
    totals = defaultdict(lambda: [0.0, 0])
    skipped_weight = 0
    excluded_dates = []
    with zipfile.ZipFile(raw / 'Table_V_Colony_inspection.zip') as z:
        with z.open('Table_V_Colony_inspection.csv') as fh:
            for r in csv.DictReader(io.TextIOWrapper(fh, encoding='utf-8-sig')):
                if r['paramText'] != 'Colony weight' or r['resUnit_desc'] != 'Kilogram' or not r['resVal']:
                    continue
                pair = (r['siteNo'], r['hiveNo'])
                if pair not in hives:
                    skipped_weight += 1
                    continue
                when = date(int(r['sampY']), int(r['sampM']), int(r['sampD'])).isoformat()
                if r['sampY'] not in ('2019', '2020'):
                    excluded_dates.append({'source_id': r['resId'], 'date': when, 'reason': 'Outside the 2019–2020 field campaign; retained in raw source, not plotted.'})
                    continue
                v = float(r['resVal'])
                total = totals[(*pair, when)]
                total[0] += v
                total[1] += 1
    for (site, hive, when), (total, n) in sorted(totals.items()):
        hives[(site, hive)]['weight'].append({'date': when, 'value': round(total / n, 3), 'n': n})
    site_names = {s['siteName']: key for key, s in sites.items()}
    omitted_methods = defaultdict(int)
    for r in rows('Table_VI_SSD2.csv'):
        if r['paramCode_desc'].lower() != 'varroa':
            continue
        # Mite-fall rows have a conflicting per-100-bees unit in the source.
        # Keep the unambiguous wash protocol only; never convert to mites/day.
        if r['anMethText'] != 'Soapy water method' or r['resUnit_desc'] != 'number per 100 adult bees':
            omitted_methods[r['anMethText']] += 1
            continue
        ids = dict(x.split('=', 1) for x in r['sampUnitIds'].split('$') if '=' in x)
        pair = (site_names.get(ids.get('sampHoldingId')), ids.get('herdId'))
        if pair not in hives:
            omitted_methods['unmatched hive'] += 1
            continue
        when = date(int(r['sampY']), int(r['sampM']), int(r['sampD'])).isoformat()
        hives[pair]['varroa'].append({
            'date': when, 'value': float(r['resVal']) if r['resType'] == 'VAL' and r['resVal'] else None,
            'result_type': r['resType'], 'result_description': r['resType_desc'],
            'source_id': r['resId'], 'method': r['anMethText'], 'unit': r['resUnit_desc'],
            'raw_value': r['resVal'], 'lod': r['resLOD'] or None,
        })
    result = []
    for h in hives.values():
        h['varroa'].sort(key=lambda r: (r['date'], r['source_id']))
        h['weight'].sort(key=lambda r: r['date'])
        if h['weight'] or h['varroa']:
            result.append(h)
    result.sort(key=lambda h: (-len(h['varroa']), -len(h['weight']), h['id']))
    dates = [r['date'] for h in result for key in ('weight', 'varroa') for r in h[key]]
    return {
        'id': 'mustb', 'title': 'EFSA MUST-B field observations', 'version': 'v2',
        'source_url': SOURCE, 'doi': f'10.5281/zenodo.{RECORD}',
        'paper_url': 'https://doi.org/10.2903/sp.efsa.2021.EN-6695',
        'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'Dupont, Yoko L. et al. (2021). Research project on field data collection for honey bee colony model evaluation — datasets. Zenodo, v2.',
        'transformations': [
            'Original study hive IDs, site IDs and sampling dates retained. No dates shifted.',
            'Colony weight is the daily arithmetic mean of available scale readings in kilograms; n records the sample count. It is not honey weight.',
            'Varroa values use only the soapy water protocol, in mites per 100 adult bees. Not converted to natural mite fall per day.',
            'Below-detection-limit records are null with result_type LOD, never zero. Missing days are not interpolated.',
            'Dates outside the documented 2019–2020 campaign are excluded and logged, never silently corrected.',
            'Mite-downfall records excluded because their source unit conflicts with their method. Other unmatched hive/site rows excluded.',
            'This is a historical third-party archive, not a HiveLens deployment or an evaluation of its photo detector.',
        ],
        'excluded_dates': excluded_dates, 'manifest': manifest, 'omitted_varroa': dict(omitted_methods), 'unmatched_weight_rows': skipped_weight,
        'date_range': [min(dates), max(dates)], 'hives': result,
        'summary': {'hives': len(result), 'sites': len({h['site_id'] for h in result}), 'daily_weights': sum(len(h['weight']) for h in result), 'varroa_samples': sum(len(h['varroa']) for h in result)},
    }


def main():
    raw = ROOT / 'data' / 'research' / 'mustb'
    raw.mkdir(parents=True, exist_ok=True)
    if not (raw / 'metadata.json').exists():
        r = requests.get(f'https://zenodo.org/api/records/{RECORD}', timeout=45); r.raise_for_status()
        (raw / 'metadata.json').write_text(json.dumps(r.json(), indent=2))
    meta = json.loads((raw / 'metadata.json').read_text())
    for name in FILES:
        if not (raw / name).exists():
            item = next(f for f in meta['files'] if f['key'] == name)
            r = requests.get(item['links']['self'], timeout=90); r.raise_for_status()
            (raw / name).write_bytes(r.content)
    data = build(raw)
    target = ROOT / 'hivelens' / 'datasets' / 'mustb.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'file': str(target), 'date_range': data['date_range'], **data['summary'], 'omissions': data['omitted_varroa'], 'unmatched_weight_rows': data['unmatched_weight_rows']}, indent=2))


if __name__ == '__main__':
    main()
