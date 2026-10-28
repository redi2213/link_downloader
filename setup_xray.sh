#!/usr/bin/env bash
# setup_xray.sh — start local SOCKS from V2Ray/Xray JSON (or leave unused)
set -euo pipefail

CFG_RAW="${V2RAY_CONFIG:-}"
if [ -z "$CFG_RAW" ]; then
  echo "No V2RAY_CONFIG — skip xray"
  exit 0
fi

echo "Installing Xray..."
VER=$(curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
URL="https://github.com/XTLS/Xray-core/releases/download/${VER}/Xray-linux-64.zip"
curl -sL "$URL" -o /tmp/xray.zip
unzip -o /tmp/xray.zip -d /tmp/xray
sudo mv /tmp/xray/xray /usr/local/bin/xray
sudo chmod +x /usr/local/bin/xray
xray version || true

python3 <<'PY'
import json, os, re, sys

raw = os.environ.get("V2RAY_CONFIG", "").strip()
if not raw:
    sys.exit(0)

# strip markdown fences if user pasted them
raw = re.sub(r"^```(?:json)?\s*", "", raw)
raw = re.sub(r"\s*```$", "", raw)

try:
    cfg = json.loads(raw)
except json.JSONDecodeError as e:
    print("ERROR: V2RAY_CONFIG is not valid JSON:", e)
    print("Paste full Xray/V2Ray JSON config (not only a vmess:// link).")
    sys.exit(1)

# Ensure a local SOCKS inbound on 10808 for our scripts
inbounds = cfg.get("inbounds") or []
has_socks = False
for ib in inbounds:
    if ib.get("protocol") in ("socks", "mixed") and int(ib.get("port") or 0) == 10808:
        has_socks = True
        break

if not has_socks:
    inbounds.insert(0, {
        "tag": "socks-in",
        "port": 10808,
        "listen": "127.0.0.1",
        "protocol": "socks",
        "settings": {"udp": True, "auth": "noauth"},
        "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
    })
    cfg["inbounds"] = inbounds
    print("Added local SOCKS inbound 127.0.0.1:10808")

# Prefer routing all traffic out via first outbound if routing missing
if "outbounds" not in cfg or not cfg["outbounds"]:
    print("ERROR: config has no outbounds")
    sys.exit(1)

path = "/tmp/xray-config.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
print("Wrote", path)
PY

echo "Starting Xray on socks 127.0.0.1:10808 ..."
nohup xray run -c /tmp/xray-config.json > /tmp/xray.log 2>&1 &
echo $! > /tmp/xray.pid
sleep 2
if ! kill -0 "$(cat /tmp/xray.pid)" 2>/dev/null; then
  echo "Xray failed to start. Log:"
  cat /tmp/xray.log || true
  exit 1
fi
echo "Xray PID $(cat /tmp/xray.pid)"
# quick check
curl -sS --max-time 15 -x socks5h://127.0.0.1:10808 https://httpbin.org/ip || echo "warn: proxy self-test failed (may still work for some sites)"
