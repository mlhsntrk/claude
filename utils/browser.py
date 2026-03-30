"""
Selenium WebDriver factory with anti-bot detection options.
Uses standard selenium with stealth flags compatible with macOS.
"""
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from config import HEADLESS

CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"


def create_driver() -> webdriver.Chrome:
    """Return a configured Chrome WebDriver instance."""
    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-data-dir=/tmp/vfs_chrome_profile")

    # Hide automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-extensions")

    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    # Mask navigator.webdriver via CDP
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(0)

    logging.info("Chrome WebDriver created.")
    return driver
