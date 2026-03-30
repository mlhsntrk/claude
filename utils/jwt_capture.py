"""
Extract JWT bearer token from the browser's localStorage or cookies
after a successful VFS Global login.
"""
import json
import logging
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

# Common localStorage key names used by VFS Global's Angular app
_LOCAL_STORAGE_KEYS = [
    "access_token",
    "authToken",
    "token",
    "jwt",
    "id_token",
    "vfs_token",
    "userToken",
]

# Cookie name fragments that likely contain JWT values
_COOKIE_NAME_FRAGMENTS = ["token", "jwt", "auth", "bearer"]


def extract_jwt(driver: WebDriver) -> Optional[str]:
    """
    Try localStorage then cookies to find a JWT token.
    Returns the raw token string or None.
    """
    # 1. Try localStorage
    try:
        raw = driver.execute_script("return JSON.stringify(window.localStorage);")
        if raw:
            data: dict = json.loads(raw)
            for key in _LOCAL_STORAGE_KEYS:
                if key in data and data[key]:
                    value = data[key]
                    logging.info(f"JWT found in localStorage['{key}'] (first 40 chars): {value[:40]}…")
                    return value
            # If none of the known keys matched, log available keys for debugging
            logging.debug(f"localStorage keys present: {list(data.keys())}")
    except Exception as exc:
        logging.warning(f"Could not read localStorage: {exc}")

    # 2. Fallback: cookies
    try:
        for cookie in driver.get_cookies():
            name = cookie.get("name", "").lower()
            if any(frag in name for frag in _COOKIE_NAME_FRAGMENTS):
                value = cookie.get("value", "")
                if value:
                    logging.info(f"JWT found in cookie '{cookie['name']}' (first 40 chars): {value[:40]}…")
                    return value
    except Exception as exc:
        logging.warning(f"Could not read cookies: {exc}")

    logging.warning("JWT token not found in localStorage or cookies.")
    return None
