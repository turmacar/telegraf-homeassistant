#!/usr/bin/env python3
"""
Patch Grafana's unified storage (resource table) to update the $server variable regex.
Run from Desktop-STRIX — requires SSH access to Tower.

Usage:
    python3 fix_resource_table.py
    python3 fix_resource_table.py --hosts "Tower,Desktop-STRIX,ha-pi,pihole"

Grafana 11+ stores dashboards in the `resource` table (Kubernetes-style JSON),
not the legacy `dashboard` table. All programmatic edits must target resource.value.
"""
import json, subprocess, sys, argparse

DB = '/mnt/user/appdata/grafana/grafana.db'
DASHBOARD_NAME = '000000127'
TOWER = 'root@${INFLUXDB_HOST}'

parser = argparse.ArgumentParser()
parser.add_argument('--hosts', default='Tower,Desktop-STRIX,Framework_13,ha-pi,pihole,openwrt',
                    help='Pipe-separated list of hostnames for $server regex')
args = parser.parse_args()

hosts = '|'.join(args.hosts.split(','))
new_regex = f'/^({hosts})$/'

script = f'''
import json, subprocess
DB = '{DB}'
result = subprocess.run(['sqlite3', DB, "SELECT value FROM resource WHERE name='{DASHBOARD_NAME}';"],
                        capture_output=True, text=True)
outer = json.loads(result.stdout.strip())
for v in outer['spec']['templating']['list']:
    if v['name'] == 'server':
        v['regex'] = {repr(new_regex)}
        v['options'] = []
        print('Updated $server regex:', v['regex'])
outer['metadata']['generation'] += 1
new_json = json.dumps(outer, separators=(',', ':'))
escaped = new_json.replace("'", "''")
subprocess.run(['sqlite3', DB,
    f"UPDATE resource SET value='{{escaped}}', resource_version=resource_version+1 WHERE name='{DASHBOARD_NAME}';"],
    check=True)
subprocess.run(['docker', 'restart', 'Grafana'], capture_output=True)
print('Done. Hard-refresh Grafana in browser.')
'''

result = subprocess.run(['ssh', TOWER, f'python3 - << \'EOF\'\n{script}\nEOF'],
                        capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr[:200])
