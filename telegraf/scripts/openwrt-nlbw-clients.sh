#!/bin/sh
# Per-client traffic from nlbwmon as influx line protocol. Counters are cumulative
# per nlbwmon accounting period (resets monthly), so query with non_negative_difference.
# hostname tag = static DHCP name > DHCP lease hostname > IP (lease, then ARP) > MAC.
{
  uci -q show dhcp | sed 's/^/U /'
  sed 's/^/L /' /tmp/dhcp.leases
  ip -4 neigh show | sed 's/^/N /'
  nlbw -c csv -g mac -s, -q | sed 's/^/C /'
} | awk '
  $1 == "U" && $2 ~ /^dhcp\.@host\[[0-9]+\]\.(name|mac)=/ {
    idx = $2; sub(/\]\..*/, "", idx); sub(/.*\[/, "", idx)
    val = substr($0, index($0, "=") + 1); gsub(/\047/, "", val)
    if ($2 ~ /\.name=/) sname[idx] = val; else smacs[idx] = val
    next
  }
  $1 == "L" { m = tolower($3); ip[m] = $4; if ($5 != "*") host[m] = $5; next }
  $1 == "N" && $5 == "lladdr" { m = tolower($6); if (!(m in ip)) ip[m] = $2; next }
  $1 == "C" {
    if (!built) {
      for (i in smacs) if (i in sname) { n = split(smacs[i], ms, " "); for (j = 1; j <= n; j++) static[tolower(ms[j])] = sname[i] }
      built = 1
    }
    split(substr($0, 3), f, ",")
    if (f[1] == "mac") next
    mac = tolower(f[1])
    name = (mac in static) ? static[mac] : (mac in host) ? host[mac] : (mac in ip) ? ip[mac] : mac
    printf "lan_client,mac=%s,hostname=%s%s conns=%.0fi,rx_bytes=%.0fi,rx_pkts=%.0fi,tx_bytes=%.0fi,tx_pkts=%.0fi\n", \
      mac, name, ((mac in ip) ? ",ip=" ip[mac] : ""), f[2], f[3], f[4], f[5], f[6]
  }
'
