import os, requests
print("T18_FORCE_IPV4:", os.environ.get("T18_FORCE_IPV4"))
try:
    r = requests.get("https://api.notion.com/v1/", timeout=15)
    print("Status:", r.status_code)
    print("OK: HTTPS is reachable from python.")
except Exception as e:
    print("ERROR:", repr(e))
