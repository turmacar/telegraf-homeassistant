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

def device_card(title, icon, device):
    return {"type": "custom:telegraf-device-card", "device": device,
            "title": title, "icon": icon}

dashboard = {
    "views": [{
        "title": "Hardware",
        "path": "hardware",
        "icon": "mdi:server",
        "sections": [
            device_card("Tower (Unraid)", "mdi:server",         "tower"),
            device_card("Desktop-STRIX",  "mdi:desktop-tower",  "desktop_strix"),
            device_card("Framework 13",   "mdi:laptop",         "framework_13"),
            device_card("HA Pi",          "mdi:raspberry-pi",   "ha_pi"),
            device_card("Pi-hole",        "mdi:shield-check",   "pihole"),
            device_card("Router",         "mdi:router-network", "openwrt"),
        ],
        "badges": [],
        "header": {"layout": "responsive", "badges_position": "bottom", "badges_wrap": "wrap"}
    }]
}

wrapper = {"version": 1, "minor_version": 1, "key": "lovelace.dashboard_raspberrypi",
           "data": {"config": dashboard}}
print(json.dumps(wrapper, indent=2))
