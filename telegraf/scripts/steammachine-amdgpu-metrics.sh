#!/bin/bash
# Dumps amdgpu's own sysfs readings as-is (native field names/units - no
# renaming or unit conversion here, that's telegraf_bridge's
# parse_amdgpu_sysfs() job) for inputs.exec + data_format=json in
# steammachine.conf. hwmon index for "amdgpu" is looked up by name since
# hwmonN numbering can shift across reboots/kernel versions.
set -euo pipefail

HWMON_DIR=$(dirname "$(grep -l '^amdgpu$' /sys/class/hwmon/hwmon*/name | head -1)")

printf '{"index":"0","gpu_busy_percent":%s,"mem_info_vram_used":%s,"temp1_input":%s}\n' \
  "$(cat /sys/class/drm/card0/device/gpu_busy_percent)" \
  "$(cat /sys/class/drm/card0/device/mem_info_vram_used)" \
  "$(cat "$HWMON_DIR/temp1_input")"

