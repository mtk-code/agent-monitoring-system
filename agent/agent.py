import json
import time
import socket
from pathlib import Path
import threading

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

    # compute server base (strip last path segment e.g. /ingest)
    server_url = cfg.get("server_url", "")
    if "/" in server_url:
        server_base = server_url.rsplit("/", 1)[0]
    else:
        server_base = server_url

    cmd_poll_interval = int(cfg.get("cmd_poll_interval_sec", 10))

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

        # start command polling thread once
        if not any(t.name == "cmd-poller" for t in threading.enumerate()):
            def poll_loop():
                while True:
                    try:
                        try:
                            resp = requests.get(
                                f"{server_base}/devices/{cfg['device_id']}/commands/next",
                                headers=headers,
                                timeout=5,
                            )
                        except Exception as e:
                            print("[agent] command poll error:", repr(e))
                            time.sleep(cmd_poll_interval)
                            continue

                        if resp.status_code == 401:
                            print("[agent] command poll unauthorized (bad token)")
                        elif resp.status_code != 200:
                            print("[agent] command poll unexpected status:", resp.status_code)
                        else:
                            try:
                                cmd = resp.json()
                            except Exception:
                                cmd = None

                            if cmd:
                                print("[agent] received command:", cmd)
                                # immediately ack (mock execution)
                                try:
                                    ack_body = {"success": True, "message": "executed (mock)"}
                                    ack_url = f"{server_base}/devices/{cfg['device_id']}/commands/{cmd.get('id')}/ack"
                                    aresp = requests.post(ack_url, json=ack_body, headers=headers, timeout=5)
                                    print("[agent] acked command", cmd.get('id'), "status", aresp.status_code)
                                except Exception as e:
                                    print("[agent] ERROR acking command:", repr(e))

                        time.sleep(cmd_poll_interval)
                    except Exception as e:
                        print("[agent] poll loop exception:", repr(e))
                        time.sleep(cmd_poll_interval)

            t = threading.Thread(target=poll_loop, name="cmd-poller", daemon=True)
            t.start()

        time.sleep(interval)


if __name__ == "__main__":
    main()
