#!/usr/bin/env python3
"""Generate HA Hardware Status dashboard for Lovelace.

Requires telegraf-device-card installed as a Lovelace resource:
  cp lovelace-cards/telegraf-device-card.js <ha_config>/www/
  # Add /local/telegraf-device-card.js as a resource in Lovelace settings

Run and deploy:
  python3 ha-dashboard/gen_ha_dashboard.py > /tmp/ha_dashboard.json
  scp /tmp/ha_dashboard.json turmacar@homeassistant.lan:/tmp/
  ssh turmacar@homeassistant.lan "sudo cp /tmp/ha_dashboard.json \
    /home/turmacar/HomeAssistant/hass-config/.storage/lovelace.dashboard_raspberrypi"
"""
import json

def device_card(title, icon, device, **options):
    return {"type": "custom:telegraf-device-card", "device": device,
            "title": title, "icon": icon, **options}

dashboard = {
    "views": [{
        "title": "Hardware",
        "path": "hardware",
        "icon": "mdi:server",
        "sections": [
            # gpu_throttle_c order matches gpus:2 index order in gen_nodered_flow.py (gpu0=1050 Ti, gpu1=1070)
            device_card("Tower (Unraid)", "mdi:server",         "tower",         cpu_throttle_c=95, gpu_throttle_c=[97, 94]),
            device_card("Desktop-STRIX",  "mdi:desktop-tower",  "desktop_strix", vram_max=8192, cpu_throttle_c=95, gpu_throttle_c=93),
            device_card("Framework 13",   "mdi:laptop",         "framework_13",  cpu_throttle_c=100),
            device_card("HA Pi",          "mdi:raspberry-pi",   "ha_pi",         cpu_throttle_c=80),
            device_card("Pi-hole",        "mdi:shield-check",   "pihole",        cpu_throttle_c=80),
            device_card("Router",         "mdi:router-network", "openwrt",       cpu_throttle_c=105),
        ],
        "badges": [],
        "header": {"layout": "responsive", "badges_position": "bottom", "badges_wrap": "wrap"}
    }]
}

wrapper = {"version": 1, "minor_version": 1, "key": "lovelace.dashboard_raspberrypi",
           "data": {"config": dashboard}}
print(json.dumps(wrapper, indent=2))
