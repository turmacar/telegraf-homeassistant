# telegraf-homeassistant

Monitoring stack for home network: Telegraf → InfluxDB/MQTT → Grafana + Home Assistant.

## Architecture

```
[Each machine]
  telegraf ──► InfluxDB (Tower:8086)     ◄── Grafana (Tower:13000)
           ──► Mosquitto (ha-pi:1883)
                    │
               Node-RED (ha-pi:1880)
                    │
               HA MQTT Discovery
                    │
            Home Assistant entities
```

## Monitored Hosts

| Hostname | IP | OS | Config |
|----------|----|----|--------|
| Tower | ${INFLUXDB_HOST} | Unraid | `telegraf/tower.conf` |
| Desktop-STRIX | ${DESKTOP_IP} | Kubuntu | `telegraf/desktop-strix.conf` |
| Framework_13 | ${LAPTOP_IP} | Garuda (Arch) | `telegraf/framework13.conf` |
| ha-pi | ${MQTT_HOST} | Debian 12 | `telegraf/ha-pi.conf` |
| pihole | ${PIHOLE_IP} | Debian 12 | `telegraf/pihole.conf` |
| openwrt | ${ROUTER_IP} | OpenWRT 25.x | `telegraf/openwrt.conf` |

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

### Node-RED (HA Pi)
- Running at `http://${MQTT_HOST}:1880` in Docker, `ha_net` network
- Data: `/home/turmacar/HomeAssistant/nodered/`
- Deploy: `scp nodered/flows.json turmacar@${HA_HOST}:/home/turmacar/HomeAssistant/nodered/flows.json && ssh turmacar@${HA_HOST} "docker restart nodered"`
- After deploy, open Node-RED UI and set MQTT broker password (stored separately in Node-RED credentials)

### Grafana (Tower)
- v13.x at `http://${INFLUXDB_HOST}:13000`
- **Unified storage**: dashboard JSON lives in `resource` table, NOT `dashboard` table
- To update `$server` variable regex: `python3 scripts/grafana/fix_resource_table.py`

## Adding a New Host

1. Copy an existing `telegraf/*.conf`, change `hostname` and inputs for the device type
2. Deploy the config to the new host: `cat telegraf/newhostname.conf | ssh user@host "cat > /etc/telegraf/telegraf.conf"`
3. Add the hostname to `hosts[]` in `scripts/gen_nodered_flow.py` and redeploy Node-RED flow
4. Add a section to `ha-dashboard/gen_ha_dashboard.py` and redeploy dashboard
5. Update Grafana $server regex: `python3 scripts/grafana/fix_resource_table.py --hosts "Tower,...,newhostname"`

## Per-OS telegraf Install

| OS | Command |
|----|---------|
| Ubuntu/Debian | `curl -s https://repos.influxdata.com/influxdata-archive.key \| sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/influxdata-archive.gpg && echo 'deb [...] https://repos.influxdata.com/debian stable main' \| sudo tee /etc/apt/sources.list.d/influxdata.list && sudo apt install telegraf` |
| Arch/Garuda | `paru -S telegraf-bin` (use `paru`, not `yay`) |
| OpenWRT 25.x | `apk add telegraf-full` (full package — base lacks mqtt output; uses `apk` not `opkg`) |

### OpenWRT gotchas
- No sftp-server: `cat file | ssh root@${ROUTER_IP} "cat > /etc/telegraf/telegraf.conf"`
- No nano: use `vi`
- Init script shebang may be missing: check `/etc/init.d/telegraf` starts with `#!/bin/sh /etc/rc.common`
- Enable: `/etc/init.d/telegraf enable && /etc/init.d/telegraf start`

### Desktop (Ubuntu 25.04)
- InfluxData repo doesn't have Ubuntu 25.04 — use jammy: `sudo sed -i 's/noble/jammy/' /etc/apt/sources.list.d/influxdata.list`
- Service unit not in PATH after install: `sudo cp /usr/lib/telegraf/scripts/telegraf.service /etc/systemd/system/`

## telegraf MQTT Output Notes (1.39)
- Use `topic` (Go template), NOT `topic_prefix` — `topic_prefix` was removed
- LWT (`will_*`) fields are NOT supported in the mqtt output in 1.39
- `data_format = "json"` sends structured JSON with `fields`, `tags`, `name`, `timestamp` keys
- Topic format: `systems/{Hostname}/{measurement}` e.g. `systems/Tower/cpu`

## Node-RED Transform Function Notes
- `system` measurement sends **multiple** MQTT messages (separate for load1/load5 vs uptime vs uptime_format)
- Always guard with `!== undefined` before publishing to avoid overwriting correct values with 0
- `[[inputs.sensors]]` tag values are **lowercase** in line protocol: `feature=tctl` not `Tctl`
- `[[inputs.battery]]` does not exist in telegraf 1.39 — use `[[inputs.file]]` with `name_override = "battery"`
