"""Explicitly import a published study apiary into a workspace, preserving provenance."""
from __future__ import annotations

import json
from pathlib import Path
from . import store, workspace

ARCHIVE = Path(__file__).parent / 'datasets' / 'mustb.json'


def import_apiary(site_id: str = '5', mode: str = 'production') -> dict:
    data = json.loads(ARCHIVE.read_text())
    selected = [h for h in data['hives'] if h['site_id'] == str(site_id)]
    if not selected:
        raise ValueError('No study hives for this site.')
    provenance = {k: data[k] for k in ('id', 'version', 'source_url', 'doi', 'paper_url', 'license', 'license_url', 'attribution', 'transformations', 'manifest')}
    dates = sorted(r['date'] for h in selected for key in ('weight', 'varroa') for r in h[key])
    source = {**provenance, 'site_id': str(site_id), 'site': selected[0]['site'],
              'kind': 'published_field_study', 'date_range': [dates[0], dates[-1]],
              'hives': len(selected), 'daily_weights': sum(len(h['weight']) for h in selected),
              'varroa_samples': sum(len(h['varroa']) for h in selected)}
    with workspace.scope(mode):
        farm = next((f for f in store.list_farms() if
                     f.get('field_archive', {}).get('doi') == data['doi'] and
                     f['field_archive'].get('site_id') == str(site_id)), None)
        if farm is None:
            country = {'PT': 'Portugal', 'DK': 'Denmark'}[selected[0]['country']]
            farm = store.create_farm(selected[0]['site'], f'{selected[0]["site"]}, {country}')
        farm = store.update_farm(farm['id'], field_archive=source)
        imported = []
        for study_hive in selected:
            existing = next((h for h in store.list_hives() if
                             h.get('field_archive', {}).get('doi') == data['doi'] and
                             h['field_archive'].get('study_hive_id') == study_hive['id']), None)
            hive = existing or store.create_hive(study_hive['id'], farm['location'], farm['id'])
            hd = sorted(r['date'] for key in ('weight', 'varroa') for r in study_hive[key])
            summary = {'kind': 'published_field_study', 'doi': data['doi'], 'study_hive_id': study_hive['id'],
                       'site_id': str(site_id), 'date_range': [hd[0], hd[-1]],
                       'daily_weights': len(study_hive['weight']), 'varroa_samples': len(study_hive['varroa']),
                       'latest_weight': study_hive['weight'][-1] if study_hive['weight'] else None,
                       'latest_varroa': study_hive['varroa'][-1] if study_hive['varroa'] else None}
            store.save_field_history(hive['id'], {**provenance, 'hive': study_hive}, summary)
            imported.append(hive['id'])
        return {'workspace': mode, 'farm': farm['name'], 'farm_id': farm['id'], 'hive_ids': imported,
                'date_range': source['date_range'], 'daily_weights': source['daily_weights'],
                'varroa_samples': source['varroa_samples'], 'source_url': data['source_url']}
