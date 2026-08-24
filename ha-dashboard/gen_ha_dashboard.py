#!/usr/bin/env python3
"""Generate HA Hardware Status dashboard for Lovelace.
Run on Desktop-STRIX; then deploy:
  scp /tmp/ha_dashboard.json turmacar@${HA_HOST}:/tmp/ && ssh turmacar@${HA_HOST} "sudo cp /tmp/ha_dashboard.json /home/turmacar/HomeAssistant/hass-config/.storage/lovelace.dashboard_raspberrypi"
"""
import json

def gauge(entity, name, yellow=60, red=85, max=100):
    return {"type": "gauge", "entity": entity, "name": name, "min": 0, "max": max,
            "needle": True, "severity": {"green": 0, "yellow": yellow, "red": red}}

def host_section(title, icon, host_id, stats_extras=None, docker=False):
    gauges = {"type": "horizontal-stack", "cards": [
        gauge(f"sensor.{host_id}_cpu_usage",       "CPU",  yellow=70, red=90),
        gauge(f"sensor.{host_id}_ram_usage",        "RAM",  yellow=75, red=90),
        gauge(f"sensor.{host_id}_root_disk_usage",  "Disk", yellow=75, red=90),
    ]}
    stats = [{"entity": f"sensor.{host_id}_uptime", "name": "Uptime", "icon": "mdi:timer-outline"}]
    if docker:
        stats.append({"entity": f"sensor.{host_id}_docker_containers", "name": "Containers", "icon": "mdi:docker"})
    if stats_extras:
        stats.extend(stats_extras)
    return {"type": "grid", "cards": [
        {"type": "markdown", "content": f"## {icon} {title}"},
        gauges,
        {"type": "glance", "show_name": True, "show_icon": True, "show_state": True, "entities": stats},
    ]}

def placeholder_section(title, icon, message):
    return {"type": "grid", "cards": [{"type": "markdown", "content": f"## {icon} {title}\n_{message}_"}]}

dashboard = {
    "views": [{
        "title": "Hardware",
        "path": "hardware",
        "icon": "mdi:server",
        "sections": [
            host_section("Tower (Unraid)", "🗄️", "tower", docker=True),
            host_section("Desktop-STRIX", "🖥️", "desktop_strix", docker=True, stats_extras=[
                {"entity": "sensor.desktop_strix_cpu_temperature", "name": "CPU Temp", "icon": "mdi:thermometer"},
                {"entity": "sensor.desktop_strix_gpu_temperature", "name": "GPU Temp", "icon": "mdi:thermometer"},
                {"entity": "sensor.desktop_strix_gpu_usage",       "name": "GPU %",    "icon": "mdi:expansion-card"},
                {"entity": "sensor.desktop_strix_gpu_vram_used",   "name": "VRAM",     "icon": "mdi:memory"},
            ]),
            host_section("Framework 13", "💻", "framework_13", stats_extras=[
                {"entity": "sensor.framework_13_cpu_temperature", "name": "CPU Temp", "icon": "mdi:thermometer"},
                {"entity": "sensor.framework_13_battery",         "name": "Battery",  "icon": "mdi:battery"},
            ]),
            host_section("HA Pi", "🍓", "ha_pi", stats_extras=[
                {"entity": "sensor.ha_pi_cpu_temperature", "name": "CPU Temp", "icon": "mdi:thermometer"},
            ]),
            host_section("Pi-hole", "🛡️", "pihole", stats_extras=[
                {"entity": "sensor.pihole_cpu_temperature", "name": "CPU Temp", "icon": "mdi:thermometer"},
            ]),
        ],
        "badges": [],
        "header": {"layout": "responsive", "badges_position": "bottom", "badges_wrap": "wrap"}
    }]
}

wrapper = {"version": 1, "minor_version": 1, "key": "lovelace.dashboard_raspberrypi",
           "data": {"config": dashboard}}
print(json.dumps(wrapper, indent=2))
