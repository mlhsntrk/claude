"""
Selenium WebDriver factory with Cloudflare bypass.
Uses undetected-chromedriver with patch_driver=False for macOS compatibility.
"""
import logging
import undetected_chromedriver as uc

from config import HEADLESS

CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
CHROME_VERSION = 146


def create_driver() -> uc.Chrome:
    """Return a configured undetected Chrome WebDriver instance."""
    options = uc.ChromeOptions()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-data-dir=/tmp/vfs_chrome_profile")

    driver = uc.Chrome(
        driver_executable_path=CHROMEDRIVER_PATH,
        options=options,
        version_main=CHROME_VERSION,
        use_subprocess=True,   # macOS ile uyumlu subprocess modu
        patch_driver=False,    # patch adımını atla — macOS'ta kill -9 sebebi buydu
    )

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(0)

    logging.info("Chrome WebDriver created (undetected-chromedriver, patch_driver=False).")
    return driver
