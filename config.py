"""
Central configuration — loads .env and exposes typed constants.
VFS credentials are NOT stored here; they live encrypted in vfs.db.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Encryption ---
MASTER_KEY: str = os.environ.get("MASTER_KEY", "")

# --- VFS Global login credentials ---
VFS_EMAIL: str = os.environ.get("VFS_EMAIL", "")

# --- Gmail IMAP (for OTP) + SMTP (for result notifications) ---
GMAIL_ADDRESS: str = os.environ.get("GMAIL_ADDRESS", "claudeconnector23@gmail.com")
GMAIL_APP_PASSWORD: str = os.environ.get("GMAIL_APP_PASSWORD", "")

# --- Notification email (results are sent here after each cycle) ---
NOTIFICATION_EMAIL: str = os.environ.get("NOTIFICATION_EMAIL", "")

# --- Tuning ---
OTP_WAIT_SECONDS: int = int(os.getenv("OTP_WAIT_SECONDS", "30"))
HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"

# --- Database ---
DB_PATH: str = os.getenv("DB_PATH", "vfs.db")

# --- Target countries ---
TARGET_COUNTRIES: list[dict] = [
    {"code": "che", "name": "İsviçre (Switzerland)",   "url": "https://visa.vfsglobal.com/tur/tr/che/login"},
    {"code": "fra", "name": "Fransa (France)",          "url": "https://visa.vfsglobal.com/tur/tr/fra/login"},
    {"code": "aut", "name": "Avusturya (Austria)",      "url": "https://visa.vfsglobal.com/tur/tr/aut/login"},
    {"code": "nld", "name": "Hollanda (Netherlands)",   "url": "https://visa.vfsglobal.com/tur/tr/nld/login"},
    {"code": "dnk", "name": "Danimarka (Denmark)",      "url": "https://visa.vfsglobal.com/tur/tr/dnk/login"},
    {"code": "bgr", "name": "Bulgaristan (Bulgaria)",   "url": "https://visa.vfsglobal.com/tur/tr/bgr/login"},
]

# --- Form dropdown match strings (case-insensitive substring) ---
FORM_APPLICATION_CENTER: str = "istanbul"
FORM_CATEGORY: str           = "turizm"
FORM_SUB_CATEGORY: str       = "turistik"

# --- Result detection ---
NO_APPOINTMENT_TEXT: str  = "Üzgünüz, şu an için uygun randevu bulunamamaktadır"
CONTINUE_BUTTON_TEXT: str = "Devam Et"

# --- Loop interval (minutes) when not running with --once ---
REPEAT_INTERVAL_MINUTES: int = int(os.getenv("REPEAT_INTERVAL_MINUTES", "15"))
