# telegraf-homeassistant

Monitoring stack for home network: Telegraf → InfluxDB/MQTT → Grafana + Home Assistant.

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

Node-RED previously sat here (MQTT→HA Discovery transform); retired
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
- Previously ran at `http://${MQTT_HOST}:1880`, doing the MQTT→HA Discovery
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

```bash
# Copy the card to HA's www directory (served at /local/)
scp lovelace-cards/telegraf-device-card.js turmacar@homeassistant.lan:/home/turmacar/HomeAssistant/hass-config/www/

# Then in HA: Settings → Dashboards → ⋮ → Resources → Add resource
#   URL: /local/telegraf-device-card.js   Type: JavaScript module
```

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
