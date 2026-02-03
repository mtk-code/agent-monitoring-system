import json
import time
import socket
from pathlib import Path

import requests
import psutil

AGENT_VERSION = "0.2.0"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError("config.json not found. Copy config.example.json to config.json")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_metrics():
    return {
        "hostname": socket.gethostname(),
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "uptime_sec": int(time.time() - psutil.boot_time()),
    }


def main():
    cfg = load_config()
    interval = int(cfg.get("interval_sec", 10))
    headers = {"X-Auth-Token": cfg.get("auth_token", "")}

    print(
        f"[agent] starting device_id={cfg.get('device_id')} "
        f"interval={interval}s server={cfg.get('server_url')} version={AGENT_VERSION}"
    )

    last_error = ""

    while True:
        payload = collect_metrics()
        payload["device_id"] = cfg["device_id"]

        # extra fields for monitoring
        payload["agent_version"] = AGENT_VERSION
        payload["status"] = "ok" if last_error == "" else "error"
        payload["last_error"] = last_error

        try:
            r = requests.post(cfg["server_url"], json=payload, headers=headers, timeout=5)
            print("[agent] sent", r.status_code)
            if r.status_code == 200:
                last_error = ""
            else:
                last_error = f"HTTP {r.status_code}: {r.text}"
        except Exception as e:
            last_error = repr(e)
            print("[agent] ERROR sending payload:", last_error)

        time.sleep(interval)


if __name__ == "__main__":
    main()
