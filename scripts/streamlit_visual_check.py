#!/usr/bin/env python3
"""Quick visual check of the public Streamlit app.

The script opens every sidebar page, saves screenshots and fails if Streamlit
shows a visible error.

Run:  ./.venv/bin/python scripts/streamlit_visual_check.py
"""
from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

URL = "https://moex-futures-eda.streamlit.app/"
PAGES = [
    "Abstract", "Dataset Description", "Data Cleaning", "Descriptive Statistics",
    "Basic Plots", "Detailed Overview", "Hypothesis Testing",
    "Discussion / Conclusion",
]
OUT = pathlib.Path("reports/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
ERROR_MARKERS = ("traceback (most recent call last)", "error running app",
                 "oh no.", "this app has encountered an error")


def wake_if_sleeping(page):
    txt = page.inner_text("body").lower()
    if "get this app back up" in txt or "is sleeping" in txt:
        print("  app was sleeping -> clicking wake button ...")
        for sel in ('button:has-text("get this app back up")',
                    'text=Yes, get this app back up!'):
            try:
                page.click(sel, timeout=8000)
                break
            except Exception:
                continue
        page.wait_for_timeout(50000)


def select_page(page, name):
    sidebar = page.locator('[data-testid="stSidebar"]')
    # Try the regular radio control first.
    try:
        page.get_by_role("radio", name=name).click(timeout=8000)
        return True
    except Exception:
        pass
    # If Streamlit markup changes, the visible label is a useful fallback.
    try:
        sidebar.get_by_text(name, exact=True).first.click(timeout=8000)
        return True
    except Exception as e:
        print(f"    nav fallback failed for {name!r}: {e}")
        return False


def main():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(60000)
        print(f"opening {URL}")
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        wake_if_sleeping(page)
        # Streamlit Cloud puts the app in an iframe; opening the inner route gives
        # full-page screenshots instead of only the iframe viewport.
        page.goto(URL.rstrip("/") + "/~/+/", wait_until="domcontentloaded")
        page.wait_for_timeout(10000)
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=120000)
        page.wait_for_timeout(5000)

        for i, name in enumerate(PAGES, start=1):
            ok_nav = select_page(page, name)
            page.wait_for_timeout(9000 if name in
                                  ("Basic Plots", "Detailed Overview",
                                   "Hypothesis Testing") else 6000)
            body = page.inner_text("body").lower()
            has_err = any(m in body for m in ERROR_MARKERS)
            fn = f"{i:02d}_{name.replace(' / ', '_').replace(' ', '_')}.png"
            page.screenshot(path=str(OUT / fn), full_page=True)
            status = "OK" if (ok_nav and not has_err) else (
                "ERROR-ON-PAGE" if has_err else "NAV-ISSUE")
            results[name] = f"{status}  ({fn})"
            print(f"  [{i}/8] {name:26} -> {results[name]}")
        browser.close()

    print("\n=== SUMMARY ===")
    bad = 0
    for k, v in results.items():
        print(f"{k:26}: {v}")
        if not v.startswith("OK"):
            bad += 1
    print(f"\n{8 - bad}/8 pages OK")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
