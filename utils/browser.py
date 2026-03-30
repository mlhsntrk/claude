"""
Selenium WebDriver factory using undetected-chromedriver.
Bypasses Cloudflare bot detection used on VFS Global portals.
"""
import logging
import undetected_chromedriver as uc

from config import HEADLESS

# ChromeDriver binary confirmed at version 145 on this system
CHROMEDRIVER_PATH = "/opt/node22/bin/chromedriver"
CHROME_VERSION = 145


def create_driver() -> uc.Chrome:
    """Return a configured undetected Chrome WebDriver instance."""
    options = uc.ChromeOptions()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7")
    options.add_argument("--window-size=1920,1080")
    # Persistent profile retains cookies/session between reruns
    options.add_argument("--user-data-dir=/tmp/vfs_chrome_profile")

    driver = uc.Chrome(
        driver_executable_path=CHROMEDRIVER_PATH,
        options=options,
        version_main=CHROME_VERSION,
    )
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(0)  # Always use explicit waits

    logging.info("Chrome WebDriver created (undetected-chromedriver).")
    return driver
