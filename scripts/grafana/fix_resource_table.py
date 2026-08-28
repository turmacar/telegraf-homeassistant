#!/usr/bin/env python3
"""
Patch Grafana's unified storage (resource table) to update the $server variable regex.
Run from Desktop-STRIX - requires SSH access to Tower.

Usage:
    python3 fix_resource_table.py
    python3 fix_resource_table.py --hosts "Tower,Desktop-STRIX,ha-pi,pihole"

Grafana 11+ stores dashboards in the `resource` table (Kubernetes-style JSON),
not the legacy `dashboard` table. All programmatic edits must target resource.value.
"""
import json, subprocess, sys, argparse, os

DB = '/mnt/user/appdata/grafana/grafana.db'
DASHBOARD_NAME = '000000127'
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')


def load_env_var(name):
    """Read a var from the real environment, falling back to the repo's gitignored .env."""
    if name in os.environ:
        return os.environ[name]
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH):
            line = line.strip()
            if line.startswith(f'{name}='):
                return line.split('=', 1)[1].split('#')[0].strip()
    return None


parser = argparse.ArgumentParser()
parser.add_argument('--hosts', default='Tower,Desktop-STRIX,Framework_13,ha-pi,pihole,openwrt',
                    help='Pipe-separated list of hostnames for $server regex')
parser.add_argument('--tower', default=None,
                    help='root@<ip> for Tower; defaults to INFLUXDB_HOST from env/.env')
args = parser.parse_args()

tower_host = args.tower or load_env_var('INFLUXDB_HOST')
if not tower_host:
    sys.exit('Set INFLUXDB_HOST in .env, export it, or pass --tower root@<ip>')
TOWER = tower_host if '@' in tower_host else f'root@{tower_host}'

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
