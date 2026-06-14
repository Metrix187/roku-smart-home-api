#!/usr/bin/env python3
"""
Local LAN web dashboard for the Roku BC1000X bulbs. No external dependencies.

    py dashboard.py
    -> open http://<this-pc-LAN-ip>:8765 from any device on your Wi-Fi
       (this PC is 10.0.0.188, so: http://10.0.0.188:8765)

Everything routes through the Wyze mesh endpoint (single token), keyed by MAC,
so power + color + temp + brightness all work for each physical bulb. Tokens are
reloaded from capture/roku_api.jsonl on every action, so re-capturing refreshes
them without restarting the server.

Note: uses port 8765 (not 8080) so the dashboard can run alongside a token
re-capture, which needs mitmproxy on 8080.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import roku_bulb as rb

HOST = "0.0.0.0"
PORT = 8765


def get_bulbs():
    recs = rb.load_records()
    devs = rb.wyze_devices(recs)
    if not devs:  # fallback if get_object_list wasn't captured
        devs = [{"mac": m, "nickname": m, "ip": "", "model": "", "on": True}
                for m in rb.wyze_macs(recs)]
    return devs


def _ok(status, body):
    return status == 200 and ('"code":"1"' in body or '"message":"success"' in body)


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Bulbs</title>
<style>
  :root { --bg:#0e1014; --card:#191d26; --card2:#222732; --txt:#e8ebf0; --mut:#8b93a3;
          --accent:#ffb000; --on:#34c759; --off:#3a4150; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  header { padding:20px 18px 8px; display:flex; align-items:center; justify-content:space-between; }
  h1 { font-size:20px; margin:0; letter-spacing:.3px; }
  .allbtns button { margin-left:8px; }
  .wrap { padding:10px 14px 40px; display:grid; gap:16px;
          grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); max-width:900px; margin:0 auto; }
  .card { background:var(--card); border-radius:18px; padding:18px; box-shadow:0 6px 20px #0006; }
  .card.off { opacity:.62; }
  .top { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
  .name { font-size:18px; font-weight:600; text-transform:capitalize; }
  .ip { font-size:12px; color:var(--mut); font-weight:400; }
  .pill { font-size:12px; padding:4px 10px; border-radius:999px; background:var(--off); color:#cfd5e1; }
  .card.on .pill { background:var(--on); color:#04210f; }
  .row { display:flex; gap:10px; margin:12px 0; }
  button { cursor:pointer; border:0; border-radius:12px; padding:11px 14px; font-size:15px;
           font-weight:600; background:var(--card2); color:var(--txt); flex:1; transition:transform .05s; }
  button:active { transform:scale(.96); }
  button.on { background:var(--on); color:#04210f; }
  button.off { background:#c8453a; color:#fff; }
  label { display:block; font-size:12px; color:var(--mut); margin:14px 0 6px; }
  input[type=range] { width:100%; accent-color:var(--accent); height:26px; }
  .swatches { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }
  .sw { width:30px; height:30px; border-radius:50%; border:2px solid #ffffff22; cursor:pointer; }
  .colorpick { display:flex; align-items:center; gap:10px; margin-top:6px; }
  input[type=color] { width:46px; height:34px; border:0; background:none; border-radius:8px; }
  #toast { position:fixed; left:50%; bottom:22px; transform:translateX(-50%);
           background:#000a; padding:10px 16px; border-radius:12px; font-size:14px; opacity:0;
           transition:opacity .2s; pointer-events:none; }
  #toast.show { opacity:1; }
  footer { text-align:center; color:var(--mut); font-size:12px; padding:0 0 30px; }
</style>
</head>
<body>
<header>
  <h1>💡 Bulbs</h1>
  <div class="allbtns">
    <button onclick="allPower(true)" style="background:var(--on);color:#04210f">All On</button>
    <button onclick="allPower(false)" style="background:#c8453a;color:#fff">All Off</button>
  </div>
</header>
<div class="wrap" id="wrap"></div>
<footer>app-free control · reverse-engineered Roku/Wyze cloud</footer>
<div id="toast"></div>

<script>
const BULBS = __BULBS__;
const PRESETS = ["FF3B30","FF9500","FFCC00","34C759","00C7BE","0A84FF","5E5CE6","BF5AF2","FF2D55","FFFFFF"];

function toast(msg, ok=true){
  const t=document.getElementById('toast'); t.textContent=(ok?'✓ ':'✕ ')+msg;
  t.style.background = ok ? '#0a3' : '#a22'; t.classList.add('show');
  clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove('show'),1400);
}
async function api(path, body){
  try {
    const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j = await r.json();
    if(!j.ok) toast(j.error||'failed', false);
    return j;
  } catch(e){ toast('network error', false); return {ok:false}; }
}
function setOn(mac, on){
  const c=document.querySelector('.card[data-mac="'+mac+'"]'); if(!c)return;
  c.classList.toggle('on', on); c.classList.toggle('off', !on);
  c.querySelector('.pill').textContent = on?'on':'off';
}
async function power(mac,on){ setOn(mac,on); const j=await api('/api/power',{mac,on}); if(j.ok) toast(on?'on':'off'); }
async function bright(mac,pct){ setOn(mac,true); const j=await api('/api/bright',{mac,pct:+pct}); if(j.ok) toast('brightness '+pct+'%'); }
async function color(mac,hex){ hex=hex.replace('#',''); setOn(mac,true); const j=await api('/api/color',{mac,hex}); if(j.ok) toast('color #'+hex); }
async function temp(mac,k){ setOn(mac,true); const j=await api('/api/temp',{mac,k:+k}); if(j.ok) toast(k+'K white'); }
async function allPower(on){ for(const b of BULBS) setOn(b.mac,on); const j=await api('/api/all',{on}); if(j.ok) toast(on?'all on':'all off'); }

function card(b){
  const sw = PRESETS.map(h=>`<div class="sw" style="background:#${h}" onclick="color('${b.mac}','${h}')"></div>`).join('');
  return `
  <div class="card ${b.on?'on':'off'}" data-mac="${b.mac}">
    <div class="top">
      <div><div class="name">${b.nickname}</div><div class="ip">${b.ip||b.mac}</div></div>
      <div class="pill">${b.on?'on':'off'}</div>
    </div>
    <div class="row">
      <button class="on"  onclick="power('${b.mac}',true)">On</button>
      <button class="off" onclick="power('${b.mac}',false)">Off</button>
    </div>
    <label>Brightness</label>
    <input type="range" min="1" max="100" value="80" onchange="bright('${b.mac}',this.value)">
    <label>White warmth (2700–6500K)</label>
    <input type="range" min="2700" max="6500" step="100" value="4000" onchange="temp('${b.mac}',this.value)">
    <label>Color</label>
    <div class="colorpick">
      <input type="color" value="#ffb000" onchange="color('${b.mac}',this.value)">
      <span style="color:var(--mut);font-size:13px">pick or tap a preset →</span>
    </div>
    <div class="swatches">${sw}</div>
  </div>`;
}
document.getElementById('wrap').innerHTML = BULBS.map(card).join('');
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html") or self.path.startswith("/?"):
            html = PAGE.replace("__BULBS__", json.dumps(get_bulbs()))
            self._send(200, html, "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._send(200, json.dumps(get_bulbs()))
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", "0") or 0)
        try:
            data = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            data = {}
        recs = rb.load_records()
        try:
            if self.path == "/api/power":
                status, body = rb.set_power(recs, data["mac"], bool(data["on"]))
            elif self.path == "/api/bright":
                status, body = rb.set_brightness(recs, data["mac"], int(data["pct"]))
            elif self.path == "/api/color":
                status, body = rb.set_color(recs, data["mac"], str(data["hex"]))
            elif self.path == "/api/temp":
                status, body = rb.set_temp(recs, data["mac"], int(data["k"]))
            elif self.path == "/api/all":
                on = bool(data["on"])
                results = [rb.set_power(recs, d["mac"], on) for d in get_bulbs()]
                status = 200 if all(s == 200 for s, _ in results) else 502
                body = json.dumps([b for _, b in results])
            else:
                return self._send(404, '{"error":"unknown endpoint"}')
            self._send(200, json.dumps({"ok": _ok(status, body), "status": status, "resp": body}))
        except KeyError as e:
            self._send(400, json.dumps({"ok": False, "error": "missing field %s" % e}))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}))

    def log_message(self, *args):
        pass  # keep the console quiet


def main():
    bulbs = get_bulbs()
    print("Bulb dashboard -> http://%s:%d" % (HOST, PORT))
    print("From your phone/laptop on the same Wi-Fi: http://10.0.0.188:%d" % PORT)
    print("Bulbs:", ", ".join("%s (%s)" % (b["nickname"], b["mac"]) for b in bulbs) or "none")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
