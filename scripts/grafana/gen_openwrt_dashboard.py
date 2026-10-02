#!/usr/bin/env python3
"""Generate the OpenWRT router dashboard (network-focused, separate from the main system dashboard).

This dashboard is created via the Grafana HTTP API (not the resource-table hack used for
the main dashboard) since it's a brand-new dashboard - the API handles UID/versioning safely.

Deploy (never store the admin password in a script or file - enter it interactively):
    python3 scripts/grafana/gen_openwrt_dashboard.py > /tmp/openwrt_dashboard_payload.json
    read -s -p "Grafana admin password: " GRAFANA_PW && echo
    curl -s -u "admin:$GRAFANA_PW" -X POST http://<tower-ip>:13000/api/dashboards/db \\
      -H "Content-Type: application/json" --data @/tmp/openwrt_dashboard_payload.json
    unset GRAFANA_PW

Re-running this script and re-POSTing updates the same dashboard in place (pinned by UID
below with "overwrite": true), it will not create a duplicate.
"""
import json

DS = {"type": "influxdb", "uid": "aezhfouuz162ob"}
HOST = "openwrt"
DASHBOARD_UID = "a7w6s4"


def stat(title, query, unit, x, y, w=4, h=4, thresholds=None, decimals=None):
    fc = {"mappings": [], "unit": unit,
          "thresholds": thresholds or {"mode": "absolute", "steps": [{"color": "green", "value": 0}]}}
    if decimals is not None:
        fc["decimals"] = decimals
    return {
        "datasource": DS,
        "fieldConfig": {"defaults": fc, "overrides": []},
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {
            "colorMode": "value", "graphMode": "none", "justifyMode": "auto",
            "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto", "wideLayout": True,
        },
        "targets": [{
            "datasource": DS, "dsType": "influxdb", "rawQuery": True,
            "query": query, "refId": "A", "resultFormat": "time_series",
        }],
        "title": title, "type": "stat",
    }


def timeseries(title, targets, unit, x, y, w=12, h=7, negative_in=False):
    panel_targets = []
    for i, (alias, query) in enumerate(targets):
        panel_targets.append({
            "datasource": DS, "dsType": "influxdb", "rawQuery": True,
            "query": query, "refId": chr(65 + i), "resultFormat": "time_series",
        })
    overrides = []
    if negative_in:
        overrides.append({"matcher": {"id": "byRegexp", "options": "/ in$/"},
                           "properties": [{"id": "custom.transform", "value": "negative-Y"}]})
    return {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": 10, "gradientMode": "none",
                    "lineInterpolation": "linear", "lineWidth": 1, "pointSize": 5,
                    "showPoints": "never", "spanNulls": True,
                    "stacking": {"group": "A", "mode": "none"},
                },
                "mappings": [], "unit": unit,
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": 0}]},
            },
            "overrides": overrides,
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "interval": "$inter",
        "options": {
            "legend": {"calcs": ["mean", "lastNotNull", "max"], "displayMode": "table", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "none"},
        },
        "targets": panel_targets,
        "title": title, "type": "timeseries",
    }


def row(title, y):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": [], "title": title, "type": "row"}


panels = []
panels.append(row("Router Overview", 0))
panels.append(stat("CPU Usage",
    f'SELECT last("usage_idle") * -1 + 100 FROM "cpu" WHERE host = \'{HOST}\' AND "cpu" = \'cpu-total\' AND $timeFilter',
    "percent", 0, 1,
    thresholds={"mode": "absolute", "steps": [{"color": "rgba(50, 172, 45, 0.97)", "value": 0}, {"color": "rgba(237, 129, 40, 0.89)", "value": 70}, {"color": "rgba(245, 54, 54, 0.9)", "value": 90}]}))
panels.append(stat("RAM Usage",
    f'SELECT last("used_percent") FROM "mem" WHERE host = \'{HOST}\' AND $timeFilter',
    "percent", 4, 1,
    thresholds={"mode": "absolute", "steps": [{"color": "rgba(50, 172, 45, 0.97)", "value": 0}, {"color": "rgba(237, 129, 40, 0.89)", "value": 75}, {"color": "rgba(245, 54, 54, 0.9)", "value": 90}]}))
panels.append(stat("Disk Usage (overlay)",
    f'SELECT last("used_percent") FROM "disk" WHERE host = \'{HOST}\' AND path = \'/overlay\' AND $timeFilter',
    "percent", 8, 1,
    thresholds={"mode": "absolute", "steps": [{"color": "rgba(50, 172, 45, 0.97)", "value": 0}, {"color": "rgba(237, 129, 40, 0.89)", "value": 75}, {"color": "rgba(245, 54, 54, 0.9)", "value": 90}]}))
panels.append(stat("Uptime",
    f'SELECT last("uptime") FROM "system" WHERE host = \'{HOST}\' AND $timeFilter',
    "s", 12, 1, w=4))
panels.append(stat("Avg DNS Latency",
    f'SELECT mean("query_time_ms") FROM "dns_query" WHERE host = \'{HOST}\' AND $timeFilter',
    "ms", 16, 1, w=4, decimals=1))

panels.append(row("WAN Throughput", 5))
panels.append(timeseries("WAN Throughput", [
    ("Download", f'SELECT non_negative_derivative(mean("bytes_recv"),1s)*8 AS "Download" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
    ("Upload",   f'SELECT non_negative_derivative(mean("bytes_sent"),1s)*8 AS "Upload" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
], "bps", 0, 6)
)
panels.append(timeseries("WAN Packets/sec", [
    ("Received", f'SELECT non_negative_derivative(mean("packets_recv"),1s) AS "Received" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
    ("Sent",     f'SELECT non_negative_derivative(mean("packets_sent"),1s) AS "Sent" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
], "short", 12, 6)
)
panels.append(timeseries("WAN Errors && Drops", [
    ("err_in",  f'SELECT non_negative_derivative(mean("err_in"),1s) AS "Errors in" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
    ("err_out", f'SELECT non_negative_derivative(mean("err_out"),1s) AS "Errors out" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
    ("drop_in", f'SELECT non_negative_derivative(mean("drop_in"),1s) AS "Drops in" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
    ("drop_out",f'SELECT non_negative_derivative(mean("drop_out"),1s) AS "Drops out" FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter GROUP BY time($__interval) fill(none)'),
], "short", 0, 13)
)


def wan_usage_stat(title, time_from, x, bucket="5m"):
    """WAN bytes over a calendar-aligned window from eth0's cumulative counters."""
    def query(field, name):
        return (f'SELECT sum("d") AS "{name}" FROM (SELECT non_negative_difference(last("{field}")) AS "d" '
                f'FROM "net" WHERE host = \'{HOST}\' AND interface = \'eth0\' AND $timeFilter '
                f'GROUP BY time({bucket}) fill(none))')
    panel = stat(title, query("bytes_recv", "Download"), "decbytes", x, 13, w=4, h=7, decimals=2)
    panel["targets"].append({**panel["targets"][0], "refId": "B", "query": query("bytes_sent", "Upload")})
    panel["timeFrom"] = time_from
    panel["options"]["orientation"] = "auto"
    return panel


panels.append(wan_usage_stat("WAN Usage - This Week", "now/w", 12))
panels.append(wan_usage_stat("WAN Usage - This Month", "now/M", 16))
# Lifetime = all retained net data for the router (predates HA's lifetime sensors).
wan_lifetime = wan_usage_stat("WAN Usage - Lifetime", "20y", 20, bucket="1h")
wan_lifetime["hideTimeOverride"] = True
panels.append(wan_lifetime)

panels.append(row("DNS", 20))
panels.append(timeseries("DNS Query Latency by Resolver", [
    ("dns", f'SELECT mean("query_time_ms") FROM "dns_query" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval), "server" fill(null)'),
], "ms", 0, 21, w=24)
)

panels.append(row("Connections", 28))
panels.append(timeseries("TCP Connection States", [
    ("established", f'SELECT mean("tcp_established") AS "Established" FROM "netstat" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval) fill(null)'),
    ("time_wait",   f'SELECT mean("tcp_time_wait") AS "Time Wait" FROM "netstat" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval) fill(null)'),
    ("listen",      f'SELECT mean("tcp_listen") AS "Listen" FROM "netstat" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval) fill(null)'),
    ("close_wait",  f'SELECT mean("tcp_close_wait") AS "Close Wait" FROM "netstat" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval) fill(null)'),
], "short", 0, 29)
)
panels.append(timeseries("UDP Sockets", [
    ("udp", f'SELECT mean("udp_socket") AS "UDP Sockets" FROM "netstat" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval) fill(null)'),
], "short", 12, 29)
)

def client_usage_table(title, time_from, x, y, w=8, h=11, bucket="5m"):
    """Per-client bytes over a calendar-aligned window. lan_client counters are cumulative
    per nlbwmon period, so diff per (mac, hostname) before summing per hostname."""
    def query(field, name):
        return (f'SELECT sum("d") AS "{name}" FROM (SELECT non_negative_difference(last("{field}")) AS "d" '
                f'FROM "lan_client" WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time({bucket}), "mac", "hostname" fill(none)) '
                f'GROUP BY "hostname"')
    return {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {"unit": "decbytes", "custom": {"cellOptions": {"type": "gauge", "mode": "basic"}}},
            "overrides": [{"matcher": {"id": "byName", "options": "Device"},
                           "properties": [{"id": "custom.cellOptions", "value": {"type": "auto"}}]}],
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "timeFrom": time_from,
        "options": {"showHeader": True, "cellHeight": "sm"},
        "targets": [
            {"datasource": DS, "dsType": "influxdb", "rawQuery": True, "query": query("rx_bytes", "Download"),
             "refId": "A", "resultFormat": "table"},
            {"datasource": DS, "dsType": "influxdb", "rawQuery": True, "query": query("tx_bytes", "Upload"),
             "refId": "B", "resultFormat": "table"},
        ],
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "calculateField", "options": {"mode": "reduceRow", "reduce": {"reducer": "sum"}, "alias": "Total"}},
            {"id": "organize", "options": {"excludeByName": {"Time": True}, "renameByName": {"hostname": "Device"}}},
            {"id": "sortBy", "options": {"sort": [{"field": "Total", "desc": True}]}},
        ],
        "title": title, "type": "table",
    }


def client_rate_query(field):
    return (f'SELECT sum("r") FROM (SELECT non_negative_derivative(last("{field}"),1s)*8 AS "r" FROM "lan_client" '
            f'WHERE host = \'{HOST}\' AND $timeFilter GROUP BY time($__interval), "mac", "hostname" fill(none)) '
            f'GROUP BY time($__interval), "hostname" fill(none)')


# Per-client traffic from nlbwmon (telegraf/scripts/openwrt-nlbw-clients.sh); Influx only, not HA.
panels.append(row("Clients", 36))
panels.append(client_usage_table("Clients - This Week", "now/w", 0, 37))
panels.append(client_usage_table("Clients - This Month", "now/M", 8, 37))
# "Lifetime" = everything since lan_client collection began (2026-10-02), bounded by bucket retention.
lifetime = client_usage_table("Clients - Lifetime", "20y", 16, 37, bucket="1h")
lifetime["hideTimeOverride"] = True
panels.append(lifetime)
for i, (title, field) in enumerate((("Client Download Rate", "rx_bytes"), ("Client Upload Rate", "tx_bytes"))):
    panel = timeseries(title, [("rate", client_rate_query(field))], "bps", 12 * i, 48)
    panel["targets"][0]["alias"] = "$tag_hostname"
    panel["interval"] = "1m"
    panels.append(panel)

dashboard = {
    "uid": DASHBOARD_UID,
    "title": "OpenWRT: Router",
    "tags": ["telegraf", "network", "openwrt"],
    "timezone": "",
    "schemaVersion": 42,
    "refresh": "1m",
    "time": {"from": "now-3h", "to": "now"},
    "templating": {"list": [{
        "name": "inter", "type": "interval", "query": "10s,30s,1m,5m,10m",
        "current": {"text": "30s", "value": "30s"}, "options": [],
    }]},
    "panels": panels,
}

print(json.dumps({"dashboard": dashboard, "folderUid": "", "overwrite": True}, indent=2))
