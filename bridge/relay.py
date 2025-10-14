# relay.py (mirror of VPS /opt/t18-relay/relay.py)
# Source of truth: C:\T18\bridge\relay.py
# Deployed to VPS via SCP/SSH (see ops notes)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, signal, sys, time, urllib.request, urllib.error

BIND_HOST   = os.getenv("BIND_HOST", "127.0.0.1")
BIND_PORT   = int(os.getenv("BIND_PORT", "51839"))
DH_BASE_URL = os.getenv("DH_BASE_URL", "https://api.dhan.co")
CLIENT_ID   = os.getenv("CLIENT_ID", "")
SECRET_URL  = os.getenv("SECRET_URL", "http://127.0.0.1:51840/secret/read")
DEBUG       = os.getenv("DEBUG", "1") == "1"

def _read_json(h):
    try:
        length = int(h.headers.get('Content-Length', '0'))
        raw = h.rfile.read(length) if length > 0 else b""
        return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        return None

def _json(h, code, obj):
    try:
        body = json.dumps(obj).encode("utf-8")
    except Exception:
        body = b'{"ok": false, "error": "serialization error"}'
        code = 500
    h.send_response(code); h.send_header("Content-Type","application/json")
    h.send_header("Content-Length", str(len(body))); h.end_headers(); h.wfile.write(body)

def _get_bearer_token():
    r = urllib.request.Request(SECRET_URL, method="GET")
    with urllib.request.urlopen(r, timeout=3) as resp:
        tok = resp.read().decode("utf-8").strip()
        if tok.startswith('"') and tok.endswith('"'): tok = tok[1:-1]
        return tok

class RelayHandler(BaseHTTPRequestHandler):
    server_version = "T18Relay/1.0"
    def log_message(self, fmt, *args):
        if DEBUG: super().log_message(fmt, *args)

    def do_GET(self):
        if self.path == "/health":
            return _json(self, 200, {
                "ok": True, "service": "t18-relay", "time": int(time.time()),
                "dh_base_url": DH_BASE_URL, "client_id_set": bool(CLIENT_ID),
            })
        return _json(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        if self.path != "/relay": return _json(self, 404, {"ok": False, "error": "Not found"})
        data = _read_json(self)
        if data is None: return _json(self, 400, {"ok": False, "error": "Invalid JSON body"})

        if "dhBody" in data:  # FAST-PATH live pass-through
            dh = data.get("dhBody")
            if not isinstance(dh, dict):
                return _json(self, 422, {"ok": False, "error": "`dhBody` must be a JSON object"})
            required = ["securityId","exchangeSegment","transactionType","quantity","productType","orderType","validity"]
            miss = [k for k in required if k not in dh]
            if miss: return _json(self, 422, {"ok": False, "error": f"`dhBody` missing: {', '.join(miss)}"})
            try:
                token = _get_bearer_token()
            except Exception as e:
                return _json(self, 502, {"ok": False, "error": f"Token service error: {e}"})

            url = f"{DH_BASE_URL}/v2/orders"
            payload = json.dumps(dh).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type","application/json")
            req.add_header("Authorization", f"Bearer {token}")
            if CLIENT_ID: req.add_header("Client-Id", CLIENT_ID)
            try:
                with urllib.request.urlopen(req, timeout=7) as resp:
                    out = resp.read().decode("utf-8")
                    try: out_json = json.loads(out)
                    except Exception: out_json = {"raw": out}
                    return _json(self, 200, {"ok": True, "mode": "live-pass", "upstream": out_json})
            except urllib.error.HTTPError as he:
                body = he.read().decode("utf-8")
                try: err_json = json.loads(body)
                except Exception: err_json = {"raw": body}
                return _json(self, he.code, {"ok": False, "mode": "live-pass", "upstream": err_json})
            except Exception as e:
                return _json(self, 504, {"ok": False, "error": f"Upstream relay error: {e}"})

        # Legacy paper/backtest path
        req_keys = ["symbol","segment","instrument","side","qty"]
        miss = [k for k in req_keys if k not in data]
        if miss: return _json(self, 422, {"ok": False, "error": f"Missing fields: {', '.join(miss)}"})
        return _json(self, 200, {"ok": True, "mode": "legacy-paper", "echo": {k: data.get(k) for k in req_keys}})

def run():
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), RelayHandler)
    def _stop(signum, frame):
        try: server.shutdown()
        except Exception: pass
        finally: sys.exit(0)
    signal.signal(signal.SIGINT, _stop); signal.signal(signal.SIGTERM, _stop)
    if DEBUG: print(f"[t18-relay] starting on {BIND_HOST}:{BIND_PORT} (DH_BASE_URL={DH_BASE_URL})", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        if DEBUG: print("[t18-relay] stopped", flush=True)

if __name__ == "__main__": run()
