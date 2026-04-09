import urllib.request, urllib.parse, urllib.error, ssl, json

url = "https://api.scryfall.com/cards/named?exact=Counterspell"
print("URL:", url)
print("Python SSL default context:", ssl.create_default_context().check_hostname)

# Test 1: exact same call as the build script
print("\n--- Test 1: with User-Agent header ---")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "PauperArtistLookup/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
        print("OK —", data.get("name"), "/", data.get("set_name"))
except Exception as e:
    print("FAIL:", type(e).__name__, e)

# Test 2: no headers at all
print("\n--- Test 2: no headers ---")
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
        print("OK —", data.get("name"), "/", data.get("set_name"))
except Exception as e:
    print("FAIL:", type(e).__name__, e)

# Test 3: using requests library if available
print("\n--- Test 3: requests library ---")
try:
    import requests
    r = requests.get(url, timeout=10)
    print("Status:", r.status_code)
    print("OK —", r.json().get("name"))
except ImportError:
    print("requests not installed — skipping")
except Exception as e:
    print("FAIL:", type(e).__name__, e)

# Test 4: print full error body if 400
print("\n--- Test 4: raw error body ---")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "PauperArtistLookup/1.0"})
    urllib.request.urlopen(req, timeout=10)
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print("Body:", e.read().decode("utf-8", errors="replace"))
except Exception as e:
    print("FAIL:", type(e).__name__, e)