#!/usr/bin/env python3
"""
MTGGoldfish Pauper Metagame Scraper
-------------------------------------
Scrapes top Pauper decklists, adds new cards to allcards.txt, updates data.json.

First-time setup:
    pip install playwright
    playwright install chromium

Usage:
    python scrape_mtggoldfish.py             # scrape + update everything
    python scrape_mtggoldfish.py --dry-run   # preview only, no files modified
"""

import asyncio, json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

METAGAME_URL = "https://www.mtggoldfish.com/metagame/pauper/full"
CARDS_FILE   = Path("allcards.txt")
LOG_FILE     = Path("scrape_log.json")


async def scrape(dry_run=False):
    from playwright.async_api import async_playwright

    # Load existing cards
    existing = set()
    if CARDS_FILE.exists():
        existing = {l.strip() for l in CARDS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}
    print(f"Loaded {len(existing)} existing cards from allcards.txt")

    all_scraped = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ))
        page = await ctx.new_page()

        print(f"\nLoading {METAGAME_URL} ...")
        await page.goto(METAGAME_URL, wait_until="networkidle", timeout=60000)

        # Collect unique archetype hrefs
        raw = await page.eval_on_selector_all(
            "a[href*='/archetype/']",
            "els => [...new Set(els.map(e => e.href))]"
        )
        hrefs = list(dict.fromkeys(
            h.split("?")[0].split("#")[0]
            for h in raw if "/archetype/" in h
        ))
        print(f"Found {len(hrefs)} archetypes\n")

        for i, href in enumerate(hrefs):
            slug = href.rstrip("/").split("/")[-1]
            print(f"  [{i+1:>2}/{len(hrefs)}] {slug}", end=" ... ", flush=True)
            try:
                await page.goto(href, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(0.5)

                dl_el = await page.query_selector("a[href*='/deck/download/']")
                if not dl_el:
                    print("no download link, skipping")
                    continue

                dl_href = await dl_el.get_attribute("href")
                if not dl_href.startswith("http"):
                    dl_href = "https://www.mtggoldfish.com" + dl_href

                resp  = await page.request.get(dl_href)
                text  = await resp.text()
                cards = parse_decklist(text)
                all_scraped |= cards
                print(f"{len(cards)} cards")

            except Exception as e:
                print(f"ERROR — {e}")

            await asyncio.sleep(1.2)

        await browser.close()

    new_cards = sorted(all_scraped - existing)

    print(f"\n{'─'*50}")
    print(f"Total unique cards found      : {len(all_scraped)}")
    print(f"Already in allcards.txt       : {len(all_scraped & existing)}")
    print(f"New cards to add              : {len(new_cards)}")
    if new_cards:
        print("\nNew cards:")
        for c in new_cards:
            print(f"  + {c}")

    log = {
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "total_scraped": len(all_scraped),
        "already_known": len(all_scraped & existing),
        "new_cards":     new_cards,
        "total_after":   len(existing) + len(new_cards),
        "dry_run":       dry_run,
    }

    if not dry_run:
        if new_cards:
            with open(CARDS_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(new_cards) + "\n")
            print(f"\n✓ {len(new_cards)} card(s) appended to {CARDS_FILE}")
            print("Fetching new cards from Scryfall ...")
            subprocess.run(
                [sys.executable, "build_data.py", "--force"] + new_cards,
                check=True
            )
        else:
            print("\n✓ allcards.txt is already up to date")
    else:
        print("\n[DRY RUN] No files were modified.")

    LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ Log written to {LOG_FILE}")


def parse_decklist(text):
    """Parse MTGGoldfish plaintext export: '4 Lightning Bolt' or '4 Lightning Bolt (SLD) 123'"""
    cards = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower() == "sideboard" or line.startswith("//"):
            continue
        m = re.match(r'^\d+\s+(.+?)(?:\s+\([A-Z0-9]{2,5}\))?(?:\s+\d+)?$', line)
        if m:
            cards.add(m.group(1).strip())
    return cards


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN — no files will be modified ===\n")
    asyncio.run(scrape(dry_run))
