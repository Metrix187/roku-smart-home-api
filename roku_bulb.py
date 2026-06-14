#!/usr/bin/env python3
"""
roku_bulb.py - control Roku BC1000X (Wyze-made) smart bulbs with no app.

Protocol reverse-engineered from the Roku Smart Home iOS app via mitmproxy.
Two cloud backends are used by the app; we use both:

  * Power      -> Roku:  POST iot-devices.prod.mobile.roku.com/devices/{id}/command
                         body {"command":"power","parameters":{"power":"on|off"}}
                         auth: header  access-token: Bearer <roku-oauth-token>

  * Color/temp/brightness -> Wyze: POST api.wyzeiot.com/app/v2/auto/run_action_list
                         action_key "set_mesh_property" on the bulb's MAC
                         pids: P3=power(1/0)  P1501=brightness(1-100)
                               P1502=color temp(K)  P1507=RGB hex
                         auth: access_token inside the JSON body

Secrets are NOT hard-coded. They're read live from the mitmproxy capture
(capture/roku_api.jsonl), so re-running a capture refreshes the tokens.
"""
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "capture", "roku_api.jsonl")

ROKU_CMD_HOST = "iot-devices.prod.mobile.roku.com"
WYZE_HOST = "api.wyzeiot.com"


# --------------------------------------------------------------------------- #
# Capture parsing
# --------------------------------------------------------------------------- #
def load_records(path=CAP):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return recs


def _roku_template(recs):
    """A captured Roku /command request to copy headers (incl. bearer) from."""
    for r in recs:
        if r.get("host") == ROKU_CMD_HOST and "/command" in r.get("path", ""):
            return r
    return None


def _wyze_template(recs):
    """A captured Wyze run_action_list request + its parsed body."""
    for r in recs:
        if r.get("host") == WYZE_HOST and r.get("path", "").startswith(
            "/app/v2/auto/run_action_list"
        ):
            try:
                return r, json.loads(r["req_body"])
            except Exception:
                pass
    return None, None


def roku_device_ids(recs):
    ids = []
    for r in recs:
        if r.get("host") == ROKU_CMD_HOST:
            parts = r.get("path", "").split("/")
            if len(parts) >= 3 and parts[1] == "devices" and parts[2] not in ids:
                ids.append(parts[2])
    return ids


def wyze_macs(recs):
    macs = []
    for r in recs:
        if r.get("host") == WYZE_HOST and "run_action_list" in r.get("path", ""):
            try:
                for a in json.loads(r["req_body"]).get("action_list", []):
                    iid = a.get("instance_id")
                    if iid and iid not in macs:
                        macs.append(iid)
            except Exception:
                pass
    return macs


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _clean_headers(h):
    out = {}
    for k, v in h.items():
        if k.lower() in ("content-length", "accept-encoding"):
            continue
        out[k] = v
    out["accept-encoding"] = "identity"  # avoid gzip/br so we can read plain JSON
    return out


def _post(url, headers, body_bytes):
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# Roku power path
# --------------------------------------------------------------------------- #
def roku_command(recs, device_id, command, parameters):
    tpl = _roku_template(recs)
    if not tpl:
        raise SystemExit("No Roku /command template in capture - re-run a capture.")
    headers = _clean_headers(tpl["req_headers"])
    headers["x-roku-reserved-request-id"] = str(uuid.uuid4()).upper()
    body = json.dumps({"command": command, "parameters": parameters}).encode()
    url = f"https://{ROKU_CMD_HOST}/devices/{device_id}/command?assert=false"
    return _post(url, headers, body)


def power(recs, device_id, on):
    return roku_command(recs, device_id, "power", {"power": "on" if on else "off"})


# --------------------------------------------------------------------------- #
# Wyze mesh-property path (color / temp / brightness)
# --------------------------------------------------------------------------- #
def wyze_set(recs, mac, plist):
    tpl, body = _wyze_template(recs)
    if not tpl:
        raise SystemExit("No Wyze run_action_list template in capture.")
    new = dict(body)
    new["ts"] = int(time.time() * 1000)
    new["action_list"] = [
        {
            "action_key": "set_mesh_property",
            "instance_id": mac,
            "provider_key": "RK_BA19C",
            "action_params": {"list": [{"mac": mac, "plist": plist}]},
        }
    ]
    headers = _clean_headers(tpl["req_headers"])
    url = f"https://{WYZE_HOST}/app/v2/auto/run_action_list"
    return _post(url, headers, json.dumps(new).encode())


def set_color(recs, mac, hex_rgb):
    hex_rgb = hex_rgb.lstrip("#").upper()
    return wyze_set(recs, mac, [{"pid": "P3", "pvalue": "1"},
                                {"pid": "P1507", "pvalue": hex_rgb}])


def set_temp(recs, mac, kelvin):
    return wyze_set(recs, mac, [{"pid": "P3", "pvalue": "1"},
                                {"pid": "P1502", "pvalue": str(kelvin)}])


def set_brightness(recs, mac, pct):
    return wyze_set(recs, mac, [{"pid": "P3", "pvalue": "1"},
                                {"pid": "P1501", "pvalue": str(pct)}])


def set_power(recs, mac, on):
    """Power via the Wyze mesh path (P3) - lets every control use one token + MAC."""
    return wyze_set(recs, mac, [{"pid": "P3", "pvalue": "1" if on else "0"}])


def wyze_devices(recs):
    """Parse the latest captured get_object_list response into bulb dicts:
    [{mac, nickname, ip, model, on}]. Falls back to empty if not captured."""
    by_mac = {}
    for r in recs:
        if r.get("host") == WYZE_HOST and "get_object_list" in r.get("path", ""):
            try:
                dl = json.loads(r["resp_body"]).get("data", {}).get("device_list", [])
            except Exception:
                continue
            for d in dl:
                mac = d.get("mac")
                if not mac:
                    continue
                p = d.get("device_params", {})
                by_mac[mac] = {
                    "mac": mac,
                    "nickname": d.get("nickname") or mac,
                    "ip": p.get("ip", ""),
                    "model": d.get("product_model", ""),
                    "on": bool(p.get("switch_state", 0)),
                }
    return list(by_mac.values())


def wyze_get_object_list(recs):
    """Live-call get_object_list -> (status, body). Doubles as a token-validity
    check (body contains code "1" when the token is good) and a live state read."""
    for r in recs:
        if r.get("host") == WYZE_HOST and "get_object_list" in r.get("path", ""):
            try:
                body = json.loads(r["req_body"])
            except Exception:
                continue
            body["ts"] = int(time.time() * 1000)
            headers = _clean_headers(r["req_headers"])
            url = "https://%s/app/v2/home_page/get_object_list" % WYZE_HOST
            return _post(url, headers, json.dumps(body).encode())
    return None, None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
USAGE = """\
usage:
  python roku_bulb.py                       list discovered bulbs (ids + macs)
  python roku_bulb.py power on|off [id]     turn bulb on/off (Roku id)
  python roku_bulb.py blink [id]            off ~1.5s then on (visual test)
  python roku_bulb.py color RRGGBB [mac]    set RGB color   (Wyze mac)
  python roku_bulb.py temp  2700-6500 [mac] set white temp  (Wyze mac)
  python roku_bulb.py bright 1-100 [mac]    set brightness  (Wyze mac)
"""


def main():
    recs = load_records()
    ids = roku_device_ids(recs)
    macs = wyze_macs(recs)
    args = sys.argv[1:]
    if not args:
        print("Roku device IDs :", ids or "(none found)")
        print("Wyze bulb MACs  :", macs or "(none found)")
        print()
        print(USAGE)
        return

    cmd = args[0].lower()
    if cmd == "power":
        dev = args[2] if len(args) > 2 else ids[0]
        print(power(recs, dev, args[1].lower() in ("on", "1", "true")))
    elif cmd == "blink":
        dev = args[1] if len(args) > 1 else ids[0]
        print("off ->", power(recs, dev, False))
        time.sleep(1.5)
        print("on  ->", power(recs, dev, True))
    elif cmd == "color":
        mac = args[2] if len(args) > 2 else macs[0]
        print(set_color(recs, mac, args[1]))
    elif cmd == "temp":
        mac = args[2] if len(args) > 2 else macs[0]
        print(set_temp(recs, mac, int(args[1])))
    elif cmd == "bright":
        mac = args[2] if len(args) > 2 else macs[0]
        print(set_brightness(recs, mac, int(args[1])))
    else:
        print(USAGE)


if __name__ == "__main__":
    main()
