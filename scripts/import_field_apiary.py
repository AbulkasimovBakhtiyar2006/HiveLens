"""Import a real study apiary, without synthetic inspections or model calls.

python scripts/import_field_apiary.py --workspace production --site 5
Safe to repeat: matches published study IDs and preserves existing photo inspections.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hivelens.field_data import import_apiary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', choices=['demo', 'production'], required=True)
    parser.add_argument('--site', default='5', help='MUST-B site ID; 5 = Serra da Lousa, Portugal')
    args = parser.parse_args()
    print(json.dumps(import_apiary(args.site, args.workspace), ensure_ascii=False, indent=2))
