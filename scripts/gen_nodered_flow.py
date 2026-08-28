#!/usr/bin/env python3
"""Generate Node-RED flow JSON for telegraf → HA MQTT Discovery bridge.
Run on Desktop-STRIX; scp /tmp/flows.json turmacar@${HA_HOST}:/home/turmacar/HomeAssistant/nodered/flows.json
then ssh turmacar@${HA_HOST} "docker restart nodered"
"""
import json

TAB    = "tab_sys_metrics"
BROKER = "broker_mosquitto"
INJECT = "inject_startup"
FN_DISC  = "fn_discovery"
MQTT_IN  = "mqtt_in_systems"
FN_XFORM = "fn_transform"
DEBUG    = "debug_raw"
MQTT_OUT = "mqtt_out_ha"

DISCOVERY_FUNC = r"""
// Publish HA MQTT Discovery configs on startup and every hour.
// Edit hosts array to add/remove monitored machines.

const baseSensors = [
    { metric: 'cpu_usage',       label: 'CPU Usage',         icon: 'mdi:cpu-64-bit',     unit: '%',  device_class: null,          state_class: 'measurement' },
    { metric: 'ram_usage',       label: 'RAM Usage',         icon: 'mdi:memory',          unit: '%',  device_class: null,          state_class: 'measurement' },
    { metric: 'disk_root_usage', label: 'Root Disk Usage',   icon: 'mdi:harddisk',        unit: '%',  device_class: null,          state_class: 'measurement' },
    { metric: 'uptime',          label: 'Uptime',            icon: 'mdi:timer-outline',   unit: 's',  device_class: 'duration',    state_class: 'total_increasing' },
];

const extraSensors = {
    docker_running: { metric: 'docker_running',  label: 'Docker Containers', icon: 'mdi:docker',          unit: null,  device_class: null,          state_class: 'measurement' },
    gpu_temp:       { metric: 'gpu_temp',        label: 'GPU Temperature',   icon: 'mdi:thermometer',     unit: '°C',  device_class: 'temperature', state_class: 'measurement' },
    gpu_usage:      { metric: 'gpu_usage',       label: 'GPU Usage',         icon: 'mdi:expansion-card',  unit: '%',   device_class: null,          state_class: 'measurement' },
    gpu_vram_used:  { metric: 'gpu_vram_used',   label: 'GPU VRAM Used',     icon: 'mdi:expansion-card',  unit: 'MiB', device_class: null,          state_class: 'measurement' },
    gpu_name:       { metric: 'gpu_name',        label: 'GPU Model',         icon: 'mdi:expansion-card',  unit: null,  device_class: null,          state_class: null },
    cpu_temp:       { metric: 'cpu_temp',        label: 'CPU Temperature',   icon: 'mdi:thermometer',     unit: '°C',  device_class: 'temperature', state_class: 'measurement' },
    battery:        { metric: 'battery',         label: 'Battery',           icon: 'mdi:battery',         unit: '%',   device_class: 'battery',     state_class: 'measurement' },
    wan_rx_mbps:    { metric: 'wan_rx_mbps',     label: 'WAN Download',      icon: 'mdi:download-network', unit: 'Mbit/s', device_class: 'data_rate', state_class: 'measurement' },
    wan_tx_mbps:    { metric: 'wan_tx_mbps',     label: 'WAN Upload',        icon: 'mdi:upload-network',  unit: 'Mbit/s', device_class: 'data_rate', state_class: 'measurement' },
    dns_latency:    { metric: 'dns_latency',     label: 'DNS Latency',       icon: 'mdi:dns',             unit: 'ms',  device_class: 'duration',    state_class: 'measurement' },
};

// Hosts with more than one GPU get indexed sensors (gpu0_temp, gpu1_temp, ...)
// instead of the single flat gpu_temp/gpu_usage/gpu_vram_used set.
const gpuSensors = (i) => ([
    { metric: `gpu${i}_temp`,      label: `GPU ${i} Temperature`, icon: 'mdi:thermometer',    unit: '°C',  device_class: 'temperature', state_class: 'measurement' },
    { metric: `gpu${i}_usage`,     label: `GPU ${i} Usage`,       icon: 'mdi:expansion-card', unit: '%',   device_class: null,          state_class: 'measurement' },
    { metric: `gpu${i}_vram_used`, label: `GPU ${i} VRAM Used`,   icon: 'mdi:expansion-card', unit: 'MiB', device_class: null,          state_class: 'measurement' },
    { metric: `gpu${i}_name`,      label: `GPU ${i} Model`,       icon: 'mdi:expansion-card', unit: null,  device_class: null,          state_class: null },
]);

const hosts = [
    { name: 'Tower',         id: 'tower',         manufacturer: 'Unraid',    model: 'Server',  extras: ['docker_running','cpu_temp'], gpus: 2 },
    { name: 'Desktop-STRIX', id: 'desktop_strix', manufacturer: 'Kubuntu',   model: 'Desktop', extras: ['gpu_temp','gpu_usage','gpu_vram_used','gpu_name','cpu_temp'] },
    { name: 'Framework_13',  id: 'framework_13',  manufacturer: 'Framework', model: 'Laptop',  extras: ['cpu_temp','battery'] },
    { name: 'ha-pi',         id: 'ha_pi',         manufacturer: 'Raspberry', model: 'Pi',      extras: ['cpu_temp'] },
    { name: 'pihole',        id: 'pihole',        manufacturer: 'Raspberry', model: 'Pi',      extras: ['cpu_temp'] },
    { name: 'openwrt',       id: 'openwrt',       manufacturer: 'OpenWRT',   model: 'Router',  extras: ['wan_rx_mbps','wan_tx_mbps','dns_latency'] },
];

for (const host of hosts) {
    const sensors = [...baseSensors, ...(host.extras || []).map(k => extraSensors[k]).filter(Boolean)];
    if (host.gpus) {
        for (let i = 0; i < host.gpus; i++) sensors.push(...gpuSensors(i));
    }
    const device  = { identifiers: [`telegraf_${host.id}`], name: host.name, manufacturer: host.manufacturer, model: host.model };
    for (const s of sensors) {
        const uid = `${host.id}_${s.metric}`;
        const cfg = { name: s.label, unique_id: uid, object_id: uid, state_topic: `homeassistant/sensor/${uid}/state`, icon: s.icon, device };
        if (s.unit)         cfg.unit_of_measurement = s.unit;
        if (s.device_class) cfg.device_class = s.device_class;
        if (s.state_class)  cfg.state_class  = s.state_class;
        node.send({ topic: `homeassistant/sensor/${uid}/config`, payload: JSON.stringify(cfg), retain: true, qos: 1 });
    }
}
return null;
"""

TRANSFORM_FUNC = r"""
// Transform telegraf MQTT messages into HA state updates.
// telegraf data_format = "json" sends: {fields:{...}, tags:{...}, name:"...", timestamp:...}
// Topic: systems/{Hostname}/{measurement}

// Hosts with more than one GPU publish indexed metrics (gpu0_temp, gpu1_temp, ...)
// instead of the flat gpu_temp/gpu_usage/gpu_vram_used used by single-GPU hosts.
const MULTI_GPU_HOSTS = { tower: true };

const parts = msg.topic.split('/');
if (parts.length < 3) return null;

const hostname    = parts[1];
const measurement = parts[2];
const host_id     = hostname.toLowerCase().replace(/[-\s]/g, '_');

let data;
try { data = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload; }
catch(e) { return null; }

const items = Array.isArray(data) ? data : [data];

// OpenWRT's dns_query publishes one item per upstream resolver; average per batch
// telegraf's dns_query field is query_time_ms (already milliseconds), not response_time
if (measurement === 'dns_query' && host_id === 'openwrt') {
    const times = items.map(i => (i.fields || i).query_time_ms).filter(v => v != null);
    if (times.length > 0) {
        const avgMs = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
        node.send({ topic: `homeassistant/sensor/openwrt_dns_latency/state`, payload: String(avgMs), retain: false, qos: 0 });
    }
    return null;
}

for (const item of items) {
    const fields = item.fields || item;
    const tags   = item.tags   || {};

    // Guard: only publish when the specific field is present in this message
    const pub = (metric, value) => {
        if (value === undefined || value === null) return;
        node.send({ topic: `homeassistant/sensor/${host_id}_${metric}/state`, payload: String(value), retain: false, qos: 0 });
    };

    if (measurement === 'cpu') {
        if (tags.cpu !== 'cpu-total') continue;
        pub('cpu_usage', parseFloat((100 - (fields.usage_idle || 0)).toFixed(1)));
    }
    else if (measurement === 'mem') {
        pub('ram_usage', parseFloat((fields.used_percent || 0).toFixed(1)));
    }
    else if (measurement === 'disk') {
        if (tags.path !== '/') continue;
        pub('disk_root_usage', parseFloat((fields.used_percent || 0).toFixed(1)));
    }
    else if (measurement === 'system') {
        // system sends separate MQTT messages for load vs uptime; guard prevents publishing 0
        if (fields.uptime !== undefined) pub('uptime', Math.floor(fields.uptime));
    }
    else if (measurement === 'docker') {
        if (fields.n_containers_running !== undefined) pub('docker_running', fields.n_containers_running);
    }
    else if (measurement === 'nvidia_smi') {
        // Multi-GPU hosts get one set of entities per GPU index; single-GPU hosts
        // keep the original flat naming so existing entities aren't orphaned.
        const prefix = MULTI_GPU_HOSTS[host_id] ? `gpu${tags.index}_` : 'gpu_';
        if (fields.temperature_gpu != null) pub(`${prefix}temp`,      parseFloat(fields.temperature_gpu.toFixed(1)));
        if (fields.utilization_gpu != null) pub(`${prefix}usage`,     parseFloat(fields.utilization_gpu.toFixed(1)));
        if (fields.memory_used     != null) pub(`${prefix}vram_used`, Math.round(fields.memory_used));
        if (tags.name) pub(`${prefix}name`, tags.name.replace(/^NVIDIA\s+/i, ''));
    }
    else if (measurement === 'sensors') {
        // tags.feature is lowercase in line protocol: tctl (AMD), package_id_0 (Intel)
        const feature = (tags.feature || '').toLowerCase();
        const chip    = (tags.chip    || '').toLowerCase();
        const isCpuTemp = feature === 'tctl' || feature.startsWith('package') ||
                          (chip.includes('coretemp') && feature.startsWith('physical'));
        if (isCpuTemp && fields.temp_input != null) pub('cpu_temp', parseFloat(fields.temp_input.toFixed(1)));
    }
    else if (measurement === 'temp') {
        // Raspberry Pi thermal via [[inputs.temp]] — thermal_zone0; Tower's k10temp Tctl
        const tag_sensor = (tags.sensor || '').toLowerCase();
        if ((tag_sensor === '' || tag_sensor.includes('thermal_zone0') || tag_sensor.includes('cpu') || tag_sensor.includes('tctl')) && fields.temp != null) {
            pub('cpu_temp', parseFloat(fields.temp.toFixed(1)));
        }
    }
    else if (measurement === 'battery' || (measurement === 'file' && tags.name_override === 'battery')) {
        // Battery from [[inputs.file]] with name_override = "battery"
        const val = fields.value !== undefined ? fields.value : fields[Object.keys(fields)[0]];
        if (val !== undefined) pub('battery', Math.round(val));
    }
    else if (measurement === 'net' && host_id === 'openwrt') {
        // WAN interface only; rate computed from cumulative byte counters between messages
        if (tags.interface !== 'eth0') continue;
        const now  = Date.now();
        const prev = context.get('net_openwrt');
        context.set('net_openwrt', { t: now, rx: fields.bytes_recv, tx: fields.bytes_sent });
        if (prev && fields.bytes_recv != null && fields.bytes_sent != null) {
            const dt = (now - prev.t) / 1000;
            if (dt > 0) {
                const rxMbps = (fields.bytes_recv - prev.rx) * 8 / 1e6 / dt;
                const txMbps = (fields.bytes_sent - prev.tx) * 8 / 1e6 / dt;
                if (rxMbps >= 0) pub('wan_rx_mbps', parseFloat(rxMbps.toFixed(2)));
                if (txMbps >= 0) pub('wan_tx_mbps', parseFloat(txMbps.toFixed(2)));
            }
        }
    }
}
return null;
"""

flow = [
    {"id": TAB, "type": "tab", "label": "System Metrics → HA",
     "info": "telegraf MQTT → HA MQTT Discovery. Edit hosts[] in fn_discovery to add machines."},

    # NOTE: no "credentials" key here on purpose. Node-RED stores mqtt-broker
    # credentials separately from flows.json; set user/password once via the
    # editor UI. A full deploy that includes credentials={"password": ""}
    # OVERWRITES the live stored password and breaks the broker connection
    # (this caused a real outage - see PROJECT_CONTEXT.local.md).
    {"id": BROKER, "type": "mqtt-broker", "name": "Mosquitto (HA Pi)",
     "broker": "mosquitto", "port": "1883", "clientid": "nodered-ha-bridge",
     "usetls": False, "keepalive": "60", "cleansession": True},

    {"id": INJECT, "type": "inject", "z": TAB,
     "name": "Startup: publish Discovery", "repeat": "3600",
     "once": True, "onceDelay": 5,
     "topic": "", "payload": "", "payloadType": "str",
     "wires": [[FN_DISC]]},

    {"id": FN_DISC, "type": "function", "z": TAB,
     "name": "Publish HA Discovery Configs", "func": DISCOVERY_FUNC,
     "outputs": 1, "noerr": 0, "wires": [[MQTT_OUT]]},

    {"id": MQTT_IN, "type": "mqtt in", "z": TAB,
     "name": "Telegraf (systems/#)", "topic": "systems/#",
     "qos": "0", "datatype": "auto", "broker": BROKER,
     "wires": [[FN_XFORM, DEBUG]]},

    {"id": FN_XFORM, "type": "function", "z": TAB,
     "name": "Extract & Route Metrics", "func": TRANSFORM_FUNC,
     "outputs": 1, "noerr": 0, "wires": [[MQTT_OUT]]},

    {"id": DEBUG, "type": "debug", "z": TAB,
     "name": "Raw MQTT (disable when done)", "active": False,
     "tosidebar": True, "console": False, "tostatus": False,
     "complete": "true", "targetType": "full", "wires": []},

    {"id": MQTT_OUT, "type": "mqtt out", "z": TAB,
     "name": "→ HA MQTT Discovery", "topic": "", "qos": "1", "retain": "",
     "broker": BROKER, "wires": []},
]

print(json.dumps(flow, indent=2))
