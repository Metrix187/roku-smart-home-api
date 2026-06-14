# roku-smart-home-api

Control Roku Smart Home (BC1000X) bulbs without the app.

These bulbs are rebranded Wyze color A19s. They're cloud-only: no local API, and
they can't be added to the Wyze app, so tools like ha-wyzeapi don't see them. I
intercepted the Roku Smart Home iOS app's cloud calls with mitmproxy and replay
them from a small Python script.

Reverse-engineered by sky.

## What it does

Power, RGB color, white color temperature and brightness, verified on real bulbs.
No app and no firmware flashing.

```
python roku_bulb.py                 # list bulbs
python roku_bulb.py power on
python roku_bulb.py color FF2D00
python roku_bulb.py temp 4000
python roku_bulb.py bright 60
```

There's also a small stdlib web dashboard (`dashboard.py`) you can run on your LAN
and open from a phone: on/off, sliders and a color picker per bulb.

## How it works

The app talks to two clouds. Power goes to Roku
(`iot-devices.prod.mobile.roku.com/devices/{id}/command`). Color, brightness and
temperature go to Wyze (`api.wyzeiot.com/app/v2/auto/run_action_list`), setting
mesh properties P3/P1501/P1502/P1507 on the bulb's MAC. Endpoints, payloads and
property IDs are in [PROTOCOL.md](PROTOCOL.md).

## Setup

The scripts read auth tokens from a mitmproxy capture of the app, so nothing is
hard-coded. Capture a session (see [PROTOCOL.md](PROTOCOL.md)) and run
`python roku_bulb.py`. No third-party packages.

## Limitations

- Cloud, not local: needs internet and the vendor backend being up.
- Tokens expire and there's no auto-refresh yet, so you re-capture now and then.
- Unofficial API, so it can break whenever Roku or Wyze change their backend.

## License

MIT, see [LICENSE](LICENSE). Personal/research use, not affiliated with Roku or
Wyze. Use on hardware you own.
