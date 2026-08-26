/**
 * telegraf-device-card - Auto-discovering device card using native HA gauge cards.
 *
 * Uses loadCardHelpers to create native hui-gauge-card elements (needle/speedometer style).
 * Only renders gauges for entities that exist and have a valid state.
 *
 * Config:
 *   device: string  - entity prefix, e.g. "tower", "desktop_strix", "framework_13"
 *   title:  string  - display name (optional, defaults to device)
 *   icon:   string  - mdi icon string (optional, defaults to "mdi:server-network")
 */
class TelegrafDeviceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._helpers = null;
    this._cards = [];   // gauge card elements for incremental hass pass-through
    this._built = false;
    this._SUFFIXES = [
      "cpu_usage", "ram_usage", "root_disk_usage",
      "cpu_temperature", "gpu_temperature", "gpu_usage", "gpu_vram_used",
      "battery", "uptime", "docker_containers",
    ];
  }

  static getStubConfig() {
    return { device: "tower", title: "Tower", icon: "mdi:server" };
  }

  setConfig(config) {
    if (!config.device) throw new Error("telegraf-device-card: 'device' is required");
    this._config = config;
    this._built = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!prev || !this._built || this._availabilityChanged(prev, hass)) {
      // Full rebuild when entities appear or disappear
      this._render();
    } else {
      // Incremental: pass updated hass to each gauge card (they handle value re-render)
      for (const card of this._cards) card.hass = hass;
      this._renderStats();
    }
  }

  // -- Entity helpers --------------------------------------------------------

  _pfx(suffix) {
    return `sensor.${this._config.device}_${suffix}`;
  }

  _st(suffix) {
    const s = this._hass?.states[this._pfx(suffix)];
    if (!s || s.state === "unavailable" || s.state === "unknown") return null;
    return s;
  }

  _num(suffix) {
    const s = this._st(suffix);
    if (!s) return null;
    const n = parseFloat(s.state);
    return isNaN(n) ? null : n;
  }

  // Only trigger a full rebuild when an entity goes from available to unavailable or vice versa
  _availabilityChanged(prev, curr) {
    return this._SUFFIXES.some(s => {
      const pid = this._pfx(s);
      const wasOk = prev.states[pid] && prev.states[pid].state !== "unavailable" && prev.states[pid].state !== "unknown";
      const isOk  = curr.states[pid] && curr.states[pid].state !== "unavailable" && curr.states[pid].state !== "unknown";
      return wasOk !== isOk;
    });
  }

  _formatUptime(secs) {
    const d = Math.floor(secs / 86400);
    const h = Math.floor((secs % 86400) / 3600);
    const m = Math.floor((secs % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  // -- Build ----------------------------------------------------------------

  async _render() {
    if (!this._helpers) {
      this._helpers = await window.loadCardHelpers();
    }
    this._built = true;
    this._build();
  }

  _gaugeCard(suffix, name, severity) {
    const card = this._helpers.createCardElement({
      type: "gauge",
      entity: this._pfx(suffix),
      name,
      needle: true,
      min: 0,
      max: 100,
      severity,
    });
    card.hass = this._hass;
    this._cards.push(card);
    return card;
  }

  _build() {
    this._cards = [];
    const { device, title = device, icon = "mdi:server-network" } = this._config;

    const primaryDefs = [
      { suffix: "cpu_usage",       name: "CPU",      severity: { green: 0, yellow: 70, red: 90 } },
      { suffix: "ram_usage",       name: "RAM",      severity: { green: 0, yellow: 75, red: 90 } },
      { suffix: "root_disk_usage", name: "Disk",     severity: { green: 0, yellow: 75, red: 90 } },
    ].filter(d => this._st(d.suffix));

    const secondaryDefs = [
      { suffix: "cpu_temperature", name: "CPU Temp", severity: { green: 0, yellow: 70, red: 85 } },
      { suffix: "gpu_temperature", name: "GPU Temp", severity: { green: 0, yellow: 70, red: 85 } },
      { suffix: "gpu_usage",       name: "GPU %",    severity: { green: 0, yellow: 60, red: 80 } },
      // Battery: inverted - low value is bad
      { suffix: "battery",         name: "Battery",  severity: { red: 0,   yellow: 15, green: 30 } },
    ].filter(d => this._st(d.suffix));

    const uptimeSec = this._num("uptime");
    const docker    = this._num("docker_containers");
    const vramSt    = this._st("gpu_vram_used");
    const hasStats  = uptimeSec !== null || docker !== null || vramSt !== null;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 16px 14px; }
        .header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;
          font-size: 1.05em;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .header ha-icon { --mdc-icon-size: 20px; color: var(--state-icon-color, #44739e); }
        .gauge-row { display: flex; }
        /* Strip card chrome from nested gauge cards so they blend into our ha-card */
        .gauge-cell {
          flex: 1;
          min-width: 0;
          --ha-card-background: transparent;
          --ha-card-box-shadow: none;
          --ha-card-border-radius: 0;
          --ha-card-border-width: 0;
        }
        .divider {
          border: none;
          border-top: 1px solid var(--divider-color, #e0e0e0);
          margin: 4px 0;
        }
        .stats {
          display: flex;
          justify-content: space-around;
          flex-wrap: wrap;
          gap: 4px 12px;
          padding-top: 6px;
        }
        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1px;
          min-width: 56px;
        }
        .stat ha-icon { --mdc-icon-size: 16px; color: var(--state-icon-color, #44739e); }
        .stat-lbl { font-size: 0.7em;  color: var(--secondary-text-color); }
        .stat-val { font-size: 0.88em; font-weight: 500; color: var(--primary-text-color); }
      </style>
      <ha-card>
        <div class="header">
          <ha-icon icon="${icon}"></ha-icon>
          <span>${title}</span>
        </div>
        <div class="gauge-row primary"></div>
        ${secondaryDefs.length > 0 ? '<hr class="divider"><div class="gauge-row secondary"></div>' : ""}
        ${hasStats               ? '<hr class="divider"><div class="stats"></div>'              : ""}
      </ha-card>`;

    const primaryRow = this.shadowRoot.querySelector(".gauge-row.primary");
    for (const def of primaryDefs) {
      const cell = document.createElement("div");
      cell.className = "gauge-cell";
      cell.appendChild(this._gaugeCard(def.suffix, def.name, def.severity));
      primaryRow.appendChild(cell);
    }

    if (secondaryDefs.length > 0) {
      const secondaryRow = this.shadowRoot.querySelector(".gauge-row.secondary");
      for (const def of secondaryDefs) {
        const cell = document.createElement("div");
        cell.className = "gauge-cell";
        cell.appendChild(this._gaugeCard(def.suffix, def.name, def.severity));
        secondaryRow.appendChild(cell);
      }
    }

    if (hasStats) this._renderStats();
  }

  _renderStats() {
    const statsDiv = this.shadowRoot.querySelector(".stats");
    if (!statsDiv) return;

    const uptimeSec = this._num("uptime");
    const docker    = this._num("docker_containers");
    const vramSt    = this._st("gpu_vram_used");

    const stat = (icon, label, value) =>
      `<div class="stat">
        <ha-icon icon="${icon}"></ha-icon>
        <div class="stat-lbl">${label}</div>
        <div class="stat-val">${value}</div>
      </div>`;

    statsDiv.innerHTML = [
      uptimeSec !== null ? stat("mdi:timer-outline", "Uptime",     this._formatUptime(uptimeSec)) : "",
      docker    !== null ? stat("mdi:docker",        "Containers", Math.round(docker))             : "",
      vramSt    !== null ? stat("mdi:memory",        "VRAM",
        `${Math.round(parseFloat(vramSt.state))} ${vramSt.attributes.unit_of_measurement ?? "MiB"}`) : "",
    ].filter(Boolean).join("");
  }

  getCardSize() { return 4; }
}

customElements.define("telegraf-device-card", TelegrafDeviceCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        "telegraf-device-card",
  name:        "Telegraf Device Card",
  description: "Auto-discovers and displays telegraf metrics for a single host using native HA gauges",
});
