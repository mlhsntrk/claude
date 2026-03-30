"""
Core appointment checker.

check_country(driver, country) performs the full workflow for one country:
  - Reuse stored JWT if still valid (skip login)
  - Otherwise: Selenium login + OTP + JWT capture
  - Fill the reservation form
  - Detect success / no-appointment message
  - Persist the result to the database
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import (
    MASTER_KEY,
    VFS_EMAIL,
    FORM_APPLICATION_CENTER,
    FORM_CATEGORY,
    FORM_SUB_CATEGORY,
    NO_APPOINTMENT_TEXT,
    CONTINUE_BUTTON_TEXT,
)
from db import get_encrypted_password, decrypt_password, get_valid_jwt, save_jwt, save_result
from gmail_otp import fetch_latest_otp
from utils.waits import (
    wait_clickable, wait_visible, wait_for_element,
    select_dropdown_by_text, is_text_present,
)
from utils.jwt_capture import extract_jwt

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED  = "FAILED"
STATUS_ERROR   = "ERROR"

# ------------------------------------------------------------------
# Selectors — VFS Global Angular SPA (tr locale)
# These may need updating if VFS changes their markup.
# ------------------------------------------------------------------

# Login page
SEL_EMAIL    = (By.CSS_SELECTOR, "input[type='email'], input[formcontrolname='username']")
SEL_PASSWORD = (By.CSS_SELECTOR, "input[type='password'], input[formcontrolname='password']")
SEL_SUBMIT   = (By.CSS_SELECTOR, "button[type='submit']")

# OTP page
SEL_OTP_FIELD = (By.CSS_SELECTOR, "input[formcontrolname='otp'], input[name='otp'], input[placeholder*='OTP'], input[placeholder*='Kod'], input[maxlength='6']")

# Post-login dashboard
SEL_DASHBOARD = (By.CSS_SELECTOR, "app-home, .home-container, app-dashboard, [class*='dashboard']")

# New appointment button (text-based XPath)
XPATH_NEW_APPT = (By.XPATH, "//*[contains(text(),'Yeni Randevu') or contains(text(),'New Appointment') or contains(text(),'Randevu Al') or contains(text(),'Book Appointment')]")

# Form dropdowns — formcontrolname values observed on VFS TR Angular app
SEL_CENTER      = (By.CSS_SELECTOR, "mat-select[formcontrolname='centre'], mat-select[formcontrolname='center'], select[name*='centre'], select[name*='center']")
SEL_CATEGORY    = (By.CSS_SELECTOR, "mat-select[formcontrolname='visaCategory'], mat-select[formcontrolname='category'], select[name*='category']")
SEL_SUBCATEGORY = (By.CSS_SELECTOR, "mat-select[formcontrolname='visaSubCategory'], mat-select[formcontrolname='subCategory'], select[name*='sub']")

# Search / check button
XPATH_SEARCH_BTN = (By.XPATH, "//*[contains(text(),'Randevu Ara') or contains(text(),'Search') or contains(text(),'Ara') or @type='submit'][@class[contains(.,'search')] or @id[contains(.,'search')] or contains(text(),'Ara')]")

# "Devam Et" continue button
XPATH_DEVAM = (By.XPATH, f"//button[contains(text(),'{CONTINUE_BUTTON_TEXT}')]")


def check_country(driver: WebDriver, country: dict) -> dict:
    """
    Run the full appointment check for one country.

    Returns:
        dict with keys: country, code, status, detail
    """
    name = country["name"]
    code = country["code"]
    url  = country["url"]
    result = {"country": name, "code": code, "status": STATUS_ERROR, "detail": ""}

    try:
        # ----------------------------------------------------------------
        # Step 1: Attempt to reuse a stored JWT (skip full login)
        # ----------------------------------------------------------------
        existing_jwt = get_valid_jwt(code)
        if existing_jwt:
            logging.info(f"[{name}] Reusing stored JWT — navigating directly to dashboard.")
            # Navigate to the base app URL (strip /login suffix)
            base_url = url.replace("/login", "")
            driver.get(base_url)
            # Inject JWT into localStorage so the Angular app picks it up
            _inject_jwt(driver, existing_jwt)
            driver.refresh()
            try:
                wait_for_element(driver, SEL_DASHBOARD, timeout=10)
                logging.info(f"[{name}] Dashboard loaded with existing JWT.")
            except TimeoutException:
                logging.info(f"[{name}] JWT reuse failed — falling back to full login.")
                existing_jwt = None  # Force full login below

        # ----------------------------------------------------------------
        # Step 2: Full Selenium login (if no valid JWT)
        # ----------------------------------------------------------------
        if not existing_jwt:
            _full_login(driver, name, code, url)

        # ----------------------------------------------------------------
        # Step 3: Start new reservation
        # ----------------------------------------------------------------
        _start_new_reservation(driver, name)

        # ----------------------------------------------------------------
        # Step 4: Fill the form
        # ----------------------------------------------------------------
        _fill_reservation_form(driver, name)

        # ----------------------------------------------------------------
        # Step 5: Check availability result
        # ----------------------------------------------------------------
        result = _check_availability(driver, name, code, result)

    except TimeoutException as exc:
        result["detail"] = f"Timeout: {exc}"
        logging.error(f"[{name}] Timeout: {exc}")
    except Exception as exc:
        result["detail"] = f"{type(exc).__name__}: {exc}"
        logging.error(f"[{name}] Unexpected error: {exc}", exc_info=True)

    # Persist result to DB
    save_result(code, name, result["status"], result["detail"])
    return result


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _full_login(driver: WebDriver, name: str, code: str, url: str) -> None:
    """Navigate to login URL, enter credentials, handle OTP, capture JWT."""
    if not VFS_EMAIL:
        raise RuntimeError("VFS_EMAIL is not set in .env")
    encrypted_pw = get_encrypted_password()
    if not encrypted_pw:
        raise RuntimeError("No password found in DB. Run setup_credentials.py first.")
    email = VFS_EMAIL
    password = decrypt_password(encrypted_pw, MASTER_KEY)

    logging.info(f"[{name}] Navigating to: {url}")
    driver.get(url)

    # Enter email
    email_field = wait_clickable(driver, SEL_EMAIL)
    email_field.clear()
    email_field.send_keys(email)

    # Enter password
    pw_field = wait_clickable(driver, SEL_PASSWORD)
    pw_field.clear()
    pw_field.send_keys(password)

    # Capture timestamp just before submitting (for OTP email filtering)
    otp_trigger_time = datetime.now(timezone.utc)

    submit_btn = wait_clickable(driver, SEL_SUBMIT)
    submit_btn.click()
    logging.info(f"[{name}] Login form submitted.")

    # Wait for OTP field to appear
    try:
        otp_field = wait_visible(driver, SEL_OTP_FIELD, timeout=20)
    except TimeoutException:
        # Some country portals skip OTP if the session is still warm
        logging.info(f"[{name}] OTP field not found — assuming direct login succeeded.")
        wait_for_element(driver, SEL_DASHBOARD, timeout=15)
        _save_new_jwt(driver, name, code)
        return

    logging.info(f"[{name}] OTP field detected. Fetching OTP from Gmail…")
    otp = fetch_latest_otp(triggered_at=otp_trigger_time)
    if not otp:
        raise RuntimeError(f"[{name}] OTP not received within timeout.")

    otp_field.clear()
    otp_field.send_keys(otp)

    # Submit OTP form
    otp_submit = wait_clickable(driver, SEL_SUBMIT)
    otp_submit.click()
    logging.info(f"[{name}] OTP submitted.")

    # Wait for dashboard
    wait_for_element(driver, SEL_DASHBOARD, timeout=20)
    logging.info(f"[{name}] Login successful.")

    _save_new_jwt(driver, name, code)


def _save_new_jwt(driver: WebDriver, name: str, code: str) -> None:
    """Extract JWT from browser and persist to DB."""
    token = extract_jwt(driver)
    if token:
        save_jwt(code, token)
        logging.info(f"[{name}] JWT captured and saved to DB.")
    else:
        logging.warning(f"[{name}] Could not capture JWT — session reuse disabled for this run.")


def _inject_jwt(driver: WebDriver, token: str) -> None:
    """Inject a JWT into common localStorage keys so the Angular app accepts it."""
    for key in ("access_token", "authToken", "token"):
        driver.execute_script(f"window.localStorage.setItem('{key}', arguments[0]);", token)


def _start_new_reservation(driver: WebDriver, name: str) -> None:
    """Click the 'New Appointment' button on the dashboard."""
    try:
        btn = wait_clickable(driver, XPATH_NEW_APPT, timeout=15)
        btn.click()
        logging.info(f"[{name}] Clicked 'New Appointment' button.")
        time.sleep(1.5)
    except TimeoutException:
        # Some portals land directly on the appointment form
        logging.info(f"[{name}] 'New Appointment' button not found — may already be on form.")


def _fill_reservation_form(driver: WebDriver, name: str) -> None:
    """Fill the three cascading dropdowns on the reservation form."""
    logging.info(f"[{name}] Filling reservation form…")

    # Application Center
    try:
        select_dropdown_by_text(driver, SEL_CENTER, FORM_APPLICATION_CENTER)
        logging.info(f"[{name}] Application Center set to '{FORM_APPLICATION_CENTER}'.")
        time.sleep(1.2)  # Allow dependent dropdown to reload
    except (TimeoutException, ValueError) as exc:
        logging.warning(f"[{name}] Could not set Application Center: {exc}")

    # Application Category
    try:
        select_dropdown_by_text(driver, SEL_CATEGORY, FORM_CATEGORY)
        logging.info(f"[{name}] Category set to '{FORM_CATEGORY}'.")
        time.sleep(1.2)
    except (TimeoutException, ValueError) as exc:
        logging.warning(f"[{name}] Could not set Category: {exc}")

    # Sub-category
    try:
        select_dropdown_by_text(driver, SEL_SUBCATEGORY, FORM_SUB_CATEGORY)
        logging.info(f"[{name}] Sub-category set to '{FORM_SUB_CATEGORY}'.")
        time.sleep(1.0)
    except (TimeoutException, ValueError) as exc:
        logging.warning(f"[{name}] Could not set Sub-category: {exc}")

    # Click search / check availability
    try:
        search_btn = wait_clickable(driver, XPATH_SEARCH_BTN, timeout=10)
        search_btn.click()
        logging.info(f"[{name}] Search button clicked.")
    except TimeoutException:
        # Fallback: submit the form via Enter key or first available submit button
        logging.info(f"[{name}] Search button not found via XPATH — trying generic submit.")
        try:
            generic_submit = wait_clickable(driver, SEL_SUBMIT, timeout=5)
            generic_submit.click()
        except TimeoutException:
            logging.warning(f"[{name}] No submit button found. Result detection may fail.")

    time.sleep(3)  # Allow SPA to render availability response


def _check_availability(
    driver: WebDriver, name: str, code: str, result: dict
) -> dict:
    """Detect success or no-appointment message and update result dict."""
    if is_text_present(driver, NO_APPOINTMENT_TEXT):
        result["status"] = STATUS_FAILED
        result["detail"] = "Randevu bulunamadı: 'Üzgünüz, şu an için uygun randevu bulunamamaktadır.'"
        logging.info(f"[{name}] FAILED — no appointments available.")
    else:
        # Look for 'Devam Et' button (appointment slot found)
        try:
            devam_btn = wait_clickable(driver, XPATH_DEVAM, timeout=6)
            if devam_btn.is_enabled():
                result["status"] = STATUS_SUCCESS
                result["detail"] = "Randevu mevcut! 'Devam Et' butonu aktif."
                logging.info(f"[{name}] SUCCESS — appointment available!")
            else:
                result["detail"] = "'Devam Et' butonu bulundu fakat devre dışı."
                logging.warning(f"[{name}] 'Devam Et' found but disabled.")
        except TimeoutException:
            result["detail"] = "Ne hata mesajı ne de 'Devam Et' butonu bulunamadı — sayfa durumu belirsiz."
            logging.warning(f"[{name}] Ambiguous page state after form submission.")

    return result
