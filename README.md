# telegraf-homeassistant

Monitoring stack for home network: Telegraf -> InfluxDB/MQTT -> Grafana + Home Assistant.

## Architecture

```
[Each machine]
  telegraf ──► InfluxDB (Tower:8086)     ◄── Grafana (Tower:13000)
           ──► Mosquitto (ha-pi:1883)
                    │
         telegraf_bridge (HA custom integration,
         sibling repo telegraf-homeassistant-bridge)
                    │
            Home Assistant entities
```

Node-RED previously sat here (MQTT->HA Discovery transform); retired
2026-08-28 and its `nodered/` flow removed from this repo, replaced by the
`telegraf_bridge` custom integration.

## Monitored Hosts

| Hostname | IP | OS | Config |
|----------|----|----|--------|
| Tower | ${INFLUXDB_HOST} | Unraid | `telegraf/tower.conf` |
| Desktop-STRIX | ${DESKTOP_IP} | Kubuntu | `telegraf/desktop-strix.conf` |
| Framework_13 | ${LAPTOP_IP} | Garuda (Arch) | `telegraf/framework13.conf` |
| ha-pi | ${MQTT_HOST} | Debian 12 | `telegraf/ha-pi.conf` |
| pihole | ${PIHOLE_IP} | Debian 12 | `telegraf/pihole.conf` |
| openwrt | ${ROUTER_IP} | OpenWRT 25.x | `telegraf/openwrt.conf` |
| SteamMachine | ${STEAMMACHINE_IP} | SteamOS (Steam Machine 2026) | `telegraf/steammachine.conf` |

## Credentials

Configs use environment variable placeholders. Set these before deploying:

```bash
export INFLUXDB_TOKEN="..."        # HomeLab org admin token
export TELEGRAF_MQTT_PASSWORD="..."  # telegraf user in Mosquitto pwfile
```

Or substitute directly in the config files (do not commit real credentials).

## Infrastructure Notes

### InfluxDB (Tower)
- v2.x, org: `HomeLab`, bucket: `telegraf`
- InfluxQL v1 compatibility enabled (Grafana uses InfluxQL)

### MQTT (HA Pi)
- Mosquitto at `${MQTT_HOST}:1883`, `allow_anonymous false`
- Add telegraf user: `docker exec mosquitto mosquitto_passwd /mosquitto/config/pwfile telegraf`

### Node-RED (HA Pi) - decommissioned 2026-08-28
- Previously ran at `http://${MQTT_HOST}:1880`, doing the MQTT->HA Discovery
  transform. Replaced by the `telegraf_bridge` custom integration (sibling
  repo `telegraf-homeassistant-bridge`). `nodered/flows.json` removed from
  this repo; see `archive/TODO_ha-integration.local.md` for migration history.

### Grafana (Tower)
- v13.x at `http://${INFLUXDB_HOST}:13000`
- **Unified storage**: dashboard JSON lives in `resource` table, NOT `dashboard` table
- To update `$server` variable regex: `python3 scripts/grafana/fix_resource_table.py`

## Adding a New Host

1. Copy an existing `telegraf/*.conf`, change `hostname` and inputs for the device type
2. Deploy the config to the new host: `cat telegraf/newhostname.conf | ssh user@host "cat > /etc/telegraf/telegraf.conf"`
3. Add the host to the HA-side `telegraf_bridge` integration (auto-discovers `systems/#` topics, no per-host list to maintain)
4. Add a `device_card()` entry to `ha-dashboard/gen_ha_dashboard.py` and redeploy dashboard
   - No per-host entity list needed - `telegraf-device-card` auto-discovers which entities exist
5. Update Grafana $server regex: `python3 scripts/grafana/fix_resource_table.py --hosts "Tower,...,newhostname"`

## Lovelace Card: telegraf-device-card

A custom card that auto-discovers which entities a device provides and only renders those panels.
No docker gauge for machines without docker; no GPU row for machines without an NVIDIA card; etc.

### Install

#### HACS (recommended)

1. HACS -> top-right menu -> **Custom repositories**
2. Repository: `https://github.com/turmacar/telegraf-homeassistant`, Type: **Dashboard**
3. Download "Telegraf Device Card", then reload the browser when prompted

HACS registers the Lovelace resource and versions its URL on every update, so
no manual cache busting is needed. The card itself lives in `dist/`.

#### Manual

```bash
# Copy the card to HA's www directory (served at /local/)
scp dist/telegraf-device-card.js ${HA_USER}@${HA_HOST}:<ha_config>/www/

# Then in HA: Settings -> Dashboards -> three-dot menu -> Resources -> Add resource
#   URL: /local/telegraf-device-card.js   Type: JavaScript module
# After redeploying the card, bump a ?v=N query on that resource URL (e.g. ?v=7);
# the frontend caches /local/ resources by URL, so a restart alone won't pick it up.
```

Don't keep both installs: remove the manual `/local/` resource and `www/` file
before switching to HACS (the card can only be registered once).

### Usage

```yaml
type: custom:telegraf-device-card
device: tower          # entity prefix: sensor.tower_*
title: "Tower (Unraid)"
icon: mdi:server
```

### Entities auto-detected

| Suffix | Panel | Notes |
|--------|-------|-------|
| `cpu_usage` | Gauge (primary) | Always shown if present |
| `ram_usage` | Gauge (primary) | Always shown if present |
| `root_disk_usage` | Gauge (primary) | Always shown if present |
| `cpu_temperature` | Gauge (secondary row) | Only if entity exists |
| `gpu_temperature` | Gauge (secondary row) | Only if entity exists |
| `gpu_usage` | Gauge (secondary row) | Only if entity exists |
| `battery` | Gauge (secondary row, inverted) | Only if entity exists |
| `uptime` | Stat | Only if entity exists |
| `docker_containers` | Stat | Only if entity exists |
| `gpu_vram_used` | Stat | Only if entity exists |
| `wan_download` / `wan_upload` | Download / Upload sections ("Now") | Router WAN rate |
| `dns_latency` | Stat | Router DNS latency |
| `wan_{download,upload}_{this_week,this_month,lifetime}` | Download / Upload sections (Week / Month / Lifetime) | Router WAN usage totals |

## Router: WAN Usage & Per-Client Traffic

- **WAN usage** (week / month / lifetime): tracked by `telegraf_bridge` for net
  metrics tagged `role = "wan"` (see `telegraf/openwrt.conf`), and shown in
  Grafana's "OpenWRT: Router" dashboard.
- **Per-client usage** (Grafana only, not sent to Home Assistant): `nlbwmon` on
  the router (`apk add nlbwmon`) plus `telegraf/scripts/openwrt-nlbw-clients.sh`
  (deploy to `/etc/telegraf/nlbw-clients.sh`) emits a `lan_client` measurement
  tagged by hostname (static DHCP name, lease hostname, IP, then MAC).
  `namedrop = ["lan_client"]` on the MQTT output keeps it out of HA.
- Regenerate/deploy the dashboard: `python3 scripts/grafana/gen_openwrt_dashboard.py`
  (see its docstring for the API POST).

## Per-OS telegraf Install

| OS | Command |
|----|---------|
| Ubuntu/Debian | `curl -s https://repos.influxdata.com/influxdata-archive.key \| sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/influxdata-archive.gpg && echo 'deb [...] https://repos.influxdata.com/debian stable main' \| sudo tee /etc/apt/sources.list.d/influxdata.list && sudo apt install telegraf` |
| Arch/Garuda | `paru -S telegraf-bin` (use `paru`, not `yay`) |
| OpenWRT 25.x | `apk add telegraf-full` (full package - base lacks mqtt output; uses `apk` not `opkg`) |

### OpenWRT gotchas
- No sftp-server: `cat file | ssh root@${ROUTER_IP} "cat > /etc/telegraf/telegraf.conf"`
- No nano: use `vi`
- Init script shebang may be missing: check `/etc/init.d/telegraf` starts with `#!/bin/sh /etc/rc.common`
- Enable: `/etc/init.d/telegraf enable && /etc/init.d/telegraf start`
- telegraf 1.39 `[[inputs.exec]]` takes argv arrays: `commands = [["/path/to/script"]]`.
  `command = [...]` fails to parse; dry-run with `telegraf --config ... --test` before restarting.
- Add `/etc/telegraf/` to `/etc/sysupgrade.conf` so scripts and the env file survive upgrades.

### Desktop (Ubuntu 25.04)
- InfluxData repo doesn't have Ubuntu 25.04 - use jammy: `sudo sed -i 's/noble/jammy/' /etc/apt/sources.list.d/influxdata.list`
- Service unit not in PATH after install: `sudo cp /usr/lib/telegraf/scripts/telegraf.service /etc/systemd/system/`

## telegraf MQTT Output Notes (1.39)
- Use `topic` (Go template), NOT `topic_prefix` - `topic_prefix` was removed
- LWT (`will_*`) fields are NOT supported in the mqtt output in 1.39
- `data_format = "json"` sends structured JSON with `fields`, `tags`, `name`, `timestamp` keys
- Topic format: `systems/{Hostname}/{measurement}` e.g. `systems/Tower/cpu`

## Node-RED Transform Function Notes (historical - Node-RED decommissioned)
- `system` measurement sends **multiple** MQTT messages (separate for load1/load5 vs uptime vs uptime_format)
- Always guard with `!== undefined` before publishing to avoid overwriting correct values with 0
- `[[inputs.sensors]]` tag values are **lowercase** in line protocol: `feature=tctl` not `Tctl`
- `[[inputs.battery]]` does not exist in telegraf 1.39 - use `[[inputs.file]]` with `name_override = "battery"`
