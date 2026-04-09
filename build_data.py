#!/usr/bin/env python3
"""
Pauper Artist Index Builder
----------------------------
Place this file in the same folder as allcards.txt, then run:
    python build_data.py

It will create data.json, which the HTML app reads.
Re-run any time you update allcards.txt.
"""

import json, time, sys, argparse
import urllib.parse
import requests

DELAY = 0.12  # 8 req/s — safely under Scryfall's 10/s limit
HEADERS = {
    "User-Agent": "PauperArtistLookup/1.0; personal project",
    "Accept": "application/json",
}

def scryfall_get(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_printings(card_name):
    # Step 1: resolve the card to get its prints_search_uri
    params = urllib.parse.urlencode({"exact": card_name})
    named_url = f"https://api.scryfall.com/cards/named?{params}"
    print(f"\n    >> {named_url}", end=" ", flush=True)
    try:
        named = scryfall_get(named_url)
    except requests.HTTPError as e:
        print(f"\n    !! HTTP {e.response.status_code} → {named_url}")
        print(f"    !! Body: {e.response.text}")
        if e.response.status_code == 404:
            return []
        raise
    time.sleep(DELAY)

    # Step 2: paginate through unique artworks (unique=art deduplicates reprints with same art)
    base = named.get("prints_search_uri", "")
    url = base + ("&" if "?" in base else "?") + "unique=art&include_extras=false"
    results = []
    while url:
        data = scryfall_get(url)
        seen_illustrations = set()
        for c in data.get("data", []):
            illus_id = c.get("illustration_id") or c.get("id")
            if illus_id in seen_illustrations:
                continue
            if "paper" not in c.get("games", []):
                continue
            seen_illustrations.add(illus_id)
            image = (
                c.get("image_uris", {}).get("normal")
                or (c.get("card_faces") or [{}])[0].get("image_uris", {}).get("normal", "")
            )
            results.append({
                "artist":   c.get("artist", "Unknown"),
                "set_name": c.get("set_name", ""),
                "set_code": c.get("set", ""),
                "cn":       c.get("collector_number", ""),
                "image":    image,
                "uri":      c.get("scryfall_uri", ""),
            })
        url = data.get("next_page")
        time.sleep(DELAY)
    return results


def main():
    parser = argparse.ArgumentParser(description="Build Pauper artist index from Scryfall.")
    parser.add_argument("--force", nargs="*", metavar="CARD",
        help="Re-fetch all cards (no args) or specific cards: --force 'Lightning Bolt' 'Counterspell'")
    args = parser.parse_args()

    try:
        with open("allcards.txt", encoding="utf-8") as f:
            cards = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        sys.exit("Error: allcards.txt not found.")

    # Load existing data so we can skip already-fetched cards
    try:
        with open("data.json", encoding="utf-8") as f:
            existing = json.load(f)
        by_artist = existing.get("by_artist", {})
        by_card   = existing.get("by_card", {})
        print(f"Loaded existing data.json ({len(by_card)} cards already cached)")
    except FileNotFoundError:
        by_artist, by_card = {}, {}
        print("No existing data.json found, fetching everything from scratch")

    # Determine which cards to (re-)fetch
    if args.force is None:
        # Normal mode: skip already cached
        force_set = set()
    elif len(args.force) == 0:
        # --force with no args: redo everything
        force_set = set(cards)
        print("--force: re-fetching all cards")
    else:
        # --force Card1 Card2 ...: redo specific cards
        force_set = set(args.force)
        unknown = force_set - set(cards)
        if unknown:
            print(f"⚠  These cards are not in allcards.txt and will be skipped: {', '.join(unknown)}")
        force_set -= unknown
        print(f"--force: re-fetching {len(force_set)} specific card(s): {', '.join(force_set)}")

    # Remove forced cards from existing data before re-fetching
    for name in force_set:
        if name in by_card:
            # Remove their old artist entries too
            for p in by_card[name]:
                artist = p["artist"]
                if artist in by_artist:
                    by_artist[artist] = [x for x in by_artist[artist] if x["card_name"] != name]
                    if not by_artist[artist]:
                        del by_artist[artist]
            del by_card[name]

    new_cards = [c for c in cards if c not in by_card]
    skipped   = len(cards) - len(new_cards)
    print(f"Fetching {len(new_cards)} card(s) from Scryfall (skipping {skipped} already cached)...\n")
    errors = []
    cards = new_cards

    for i, name in enumerate(cards):
        print(f"  [{i+1:>3}/{len(cards)}] {name}", end=" ... ", flush=True)
        try:
            printings = fetch_printings(name)
            by_card[name] = []
            for p in printings:
                artist = p["artist"]
                by_artist.setdefault(artist, []).append({
                    "card_name": name, "set_name": p["set_name"],
                    "set_code": p["set_code"], "cn": p["cn"],
                    "image": p["image"], "uri": p["uri"],
                })
                by_card[name].append({
                    "artist": artist, "set_name": p["set_name"],
                    "set_code": p["set_code"], "cn": p["cn"],
                    "image": p["image"], "uri": p["uri"],
                })
            print(f"{len(printings)} printings")
        except Exception as e:
            print(f"ERROR — {e}")
            errors.append((name, str(e)))
        time.sleep(DELAY)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"by_artist": by_artist, "by_card": by_card}, f, ensure_ascii=False)

    print(f"\n✓  data.json written — {len(by_artist)} artists · {len(by_card)} cards")
    if errors:
        print(f"\n⚠  {len(errors)} cards not fetched:")
        for n, e in errors:
            print(f"     {n}: {e}")

if __name__ == "__main__":
    main()