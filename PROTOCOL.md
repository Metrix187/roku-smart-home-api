# Protocol notes

How the Roku Smart Home bulbs (model RK_BA19C, a rebranded Wyze color A19) are
controlled, worked out by intercepting the iOS app.

## Background

The bulbs are 2.4 GHz Wi-Fi and cloud-only. A port scan finds nothing listening on
them; stock firmware only makes outbound connections, so there's no local control
without reflashing. On the LAN they use Roku's OUI `7C:67:AB`. The Wyze side
identifies each bulb by its MAC with no separators as the `instance_id`.

The app uses two backends. Power can go through either; color, temperature and
brightness go through the Wyze one.

## Power (Roku)

```
POST https://iot-devices.prod.mobile.roku.com/devices/{DEVICE_ID}/command?assert=false
access-token: Bearer <roku oauth token>
content-type: application/json

{"command":"power","parameters":{"power":"on"}}      # or "off"
```

Returns `{"apiVersion":"1","data":{"message":"success"}}`. The app also sends a
set of `x-roku-reserved-*` headers; replaying the captured set and swapping the
body works fine.

## Color / temperature / brightness (Wyze)

```
POST https://api.wyzeiot.com/app/v2/auto/run_action_list
content-type: application/json

{
  "phone_system_type":"1",
  "app_version":"3.6.0.2",
  "app_ver":"com.roku.ios.rokuhome___3.6.0.2",
  "app_name":"com.roku.ios.rokuhome",
  "phone_id":"<per-install uuid>",
  "ts":<epoch ms>,
  "sc":"01dd431d098546f9baf5233724fa2ee2",
  "sv":"1ce7d8d70d91457ebc30376c50fb0810",
  "access_token":"<wyze token>",
  "action_list":[{
    "action_key":"set_mesh_property",
    "instance_id":"<MAC>",
    "provider_key":"RK_BA19C",
    "action_params":{"list":[{"mac":"<MAC>","plist":[{"pid":"P3","pvalue":"1"}]}]}
  }],
  "custom_string":""
}
```

Returns `{"code":"1",...}` on success. `sc` and `sv` are fixed per-endpoint
constants (they differ between endpoints), not per-user secrets.

### Property IDs

| pid    | meaning      | value          | range            |
|--------|--------------|----------------|------------------|
| P3     | power        | `"1"` / `"0"`  | on/off           |
| P1501  | brightness   | `"60"`         | 1–100            |
| P1502  | white temp   | `"4000"`       | ~2700–6500 K     |
| P1507  | RGB color    | `"FF2D00"`     | RRGGBB hex       |

You can set several pids in one `plist`. Power via `P3` works for both on and off,
so everything can run through the single Wyze endpoint keyed by MAC.

## Tokens

If you go all-Wyze, the Wyze `access_token` in the body is the only secret you
need; the Roku Bearer token is only for the Roku power path. Both expire.

Neither is easy to mint off-device. The Roku token comes from
`iot.prod.mobile.roku.com/user/token`, which carries a ~1 KB device-signed
assertion that can't be reproduced off the phone. The app caches its Wyze token
and only refreshes it on real expiry (a cold start just reuses the cached one).
So in practice the tokens are pulled from a capture and refreshed by re-capturing.

## Capturing tokens

1. Run mitmproxy on a machine on the same network:
   `mitmdump --listen-port 8080 -s capture_addon.py`
2. On the phone, set that machine as the Wi-Fi HTTP proxy on port 8080 and trust
   the mitmproxy CA (browse to http://mitm.it).
3. Open the Roku Smart Home app and toggle a bulb so the auth and control calls
   pass through the proxy.
4. Set the phone proxy back to off.

`capture_addon.py` writes each request/response to `capture/roku_api.jsonl`, and
the scripts read the tokens from there.
