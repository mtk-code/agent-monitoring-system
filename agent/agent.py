import json
import time
import socket
from pathlib import Path

import requests
import psutil

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
        "uptime_sec": int(time.time()),
    }


def main():
    cfg = load_config()
    interval = int(cfg.get("interval_sec", 10))

    print(f"[agent] starting device_id={cfg.get('device_id')} interval={interval}s server={cfg.get('server_url')}")

    while True:
        payload = collect_metrics()
        payload["device_id"] = cfg["device_id"]

        try:
            headers = {"X-Auth-Token": cfg.get("auth_token", "")}
            r = requests.post(cfg["server_url"], json=payload, headers=headers, timeout=5)
            print("[agent] sent", r.status_code)

        except Exception as e:
            print("[agent] ERROR sending payload:", repr(e))

        time.sleep(interval)


if __name__ == "__main__":
    main()
