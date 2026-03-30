"""
Selenium explicit-wait helpers and dropdown selectors.
Supports both native <select> elements and Angular Material mat-select.
"""
import time
import logging
from typing import Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

DEFAULT_TIMEOUT = 20


def wait_for_element(driver: WebDriver, locator: Tuple, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(locator)
    )


def wait_clickable(driver: WebDriver, locator: Tuple, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)
    )


def wait_visible(driver: WebDriver, locator: Tuple, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator)
    )


def select_dropdown_by_text(
    driver: WebDriver,
    locator: Tuple,
    target_text: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """
    Select a dropdown option whose visible text contains target_text
    (case-insensitive).  Handles:
      - Native HTML <select>
      - Angular Material <mat-select> / <mat-option>
    """
    element = wait_clickable(driver, locator, timeout)
    tag = element.tag_name.lower()

    if tag == "select":
        sel = Select(element)
        for option in sel.options:
            if target_text.lower() in option.text.lower():
                sel.select_by_visible_text(option.text)
                logging.debug(f"Selected native option: '{option.text}'")
                return
        raise ValueError(f"No <option> matching '{target_text}' found in <select>")

    # Angular Material mat-select: click to open the panel, then pick option
    element.click()
    time.sleep(0.6)  # allow overlay panel to render

    options = driver.find_elements(By.CSS_SELECTOR, "mat-option .mat-option-text, mat-option span.mdc-list-item__primary-text")
    for opt in options:
        if target_text.lower() in opt.text.lower():
            opt.click()
            logging.debug(f"Selected mat-option: '{opt.text}'")
            return

    # Fallback: any visible element inside an open overlay
    options = driver.find_elements(By.CSS_SELECTOR, ".cdk-overlay-container mat-option")
    for opt in options:
        if target_text.lower() in opt.text.lower():
            opt.click()
            logging.debug(f"Selected overlay mat-option: '{opt.text}'")
            return

    raise ValueError(f"No mat-option matching '{target_text}' found in open dropdown panel")


def is_text_present(driver: WebDriver, text: str) -> bool:
    """True if the given text appears anywhere in the current page source."""
    return text in driver.page_source
