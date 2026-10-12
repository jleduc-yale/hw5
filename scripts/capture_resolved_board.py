"""Screenshot each ticket on the running dashboard (http://localhost:5173) into output/screenshots/.

Run with the backend (port 8000) and dashboard (npm run dev) both up:
    .venv/bin/python scripts/capture_resolved_board.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "output" / "screenshots"
BASE = "http://localhost:5173"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        for ticket_id in (101, 102, 103):
            page.goto(f"{BASE}/?ticket={ticket_id}")
            page.wait_for_selector(".detail-title h1")
            page.wait_for_selector(".outcome", timeout=15000)  # summary tab rendered = run events loaded
            page.wait_for_timeout(1200)  # let the balance count-up and fade-ins settle
            page.screenshot(path=OUT / f"ticket_{ticket_id}.png", full_page=True)
            print("saved", f"ticket_{ticket_id}.png")
        page.goto(f"{BASE}/?ticket=101")
        page.wait_for_selector(".outcome", timeout=15000)
        page.wait_for_timeout(1200)
        page.screenshot(path=OUT / "board_overview.png")
        print("saved board_overview.png")
        browser.close()


if __name__ == "__main__":
    main()
