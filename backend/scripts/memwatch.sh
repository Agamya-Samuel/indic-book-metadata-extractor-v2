#!/usr/bin/env bash
# Memory-pressure watcher for the config-matrix run (4 vCPU / 15.62 GiB, no swap).
# Full 5 s series goes to /tmp/mem.log; stdout (-> /tmp/pressure.log) only on pressure.
THRESH_MIB=1500
while true; do
  avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  rss=$(ps -o rss= -C llama-server | awk '{s+=$1} END{print int(s/1024)}')
  ts=$(date +%H:%M:%S)
  echo "$ts avail=${avail}MiB llama_rss=${rss}MiB" >> /tmp/mem.log
  if [ "${avail:-9999}" -lt "$THRESH_MIB" ]; then
    echo "MEMPRESSURE $ts avail=${avail}MiB llama_rss=${rss}MiB"
  fi
  sleep 5
done
