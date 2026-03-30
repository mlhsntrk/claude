"""
VFS Global Visa Appointment Checker — Entry Point

Usage:
    python main.py           # Loop every 15 minutes indefinitely
    python main.py --once    # Single run, then exit
    python main.py --results # Print latest DB results and exit

The script checks all configured country portals sequentially,
records SUCCESS/FAILED/ERROR results in vfs.db, and prints a summary.
"""
import argparse
import logging
import sys
import time

from config import TARGET_COUNTRIES, REPEAT_INTERVAL_MINUTES
from db import init_db, get_all_results
from utils.browser import create_driver
from checker import check_country
from notifier import print_results, build_notification_message


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("vfs_checker.log", encoding="utf-8"),
        ],
    )


def run_once() -> list[dict]:
    """Run one full check cycle across all countries. Returns list of result dicts."""
    driver = create_driver()
    results: list[dict] = []
    try:
        for country in TARGET_COUNTRIES:
            logging.info(f"{'─' * 50}")
            logging.info(f"Checking: {country['name']} ({country['code'].upper()})")
            result = check_country(driver, country)
            results.append(result)
            time.sleep(2)  # Brief pause between countries
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return results


def show_stored_results() -> None:
    """Print the last 50 results from the database."""
    rows = get_all_results(limit=50)
    if not rows:
        print("No results in database yet.")
        return
    print(f"\n{'─' * 72}")
    print(f"  Last {len(rows)} results from vfs.db:")
    print(f"{'─' * 72}")
    for r in rows:
        icon = "✅" if r["status"] == "SUCCESS" else "❌" if r["status"] == "FAILED" else "⚠️"
        print(f"  {icon}  {r['checked_at'][:19]}  {r['country_name']:<30} {r['status']}")
    print(f"{'─' * 72}\n")


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(description="VFS Global appointment checker")
    parser.add_argument("--once",    action="store_true", help="Run once and exit")
    parser.add_argument("--results", action="store_true", help="Show stored results and exit")
    args = parser.parse_args()

    # Ensure DB tables exist
    init_db()

    if args.results:
        show_stored_results()
        sys.exit(0)

    cycle = 0
    while True:
        cycle += 1
        logging.info(f"{'═' * 50}")
        logging.info(f"Starting check cycle #{cycle}")
        logging.info(f"{'═' * 50}")

        results = run_once()
        print_results(results)

        # Also log the compact notification message
        logging.info("\n" + build_notification_message(results))

        if args.once:
            logging.info("--once flag set. Exiting after single cycle.")
            break

        logging.info(
            f"Next check in {REPEAT_INTERVAL_MINUTES} minute(s). "
            f"Press Ctrl+C to stop."
        )
        try:
            time.sleep(REPEAT_INTERVAL_MINUTES * 60)
        except KeyboardInterrupt:
            logging.info("Interrupted by user. Exiting.")
            break


if __name__ == "__main__":
    main()
