"""
One-time credential setup script.

Run this once to:
  1. Generate a MASTER_KEY (Fernet key) and write it to .env
  2. Prompt for your VFS Global email and password
  3. Encrypt the password with the MASTER_KEY
  4. Store the encrypted credentials in vfs.db

Usage:
    python setup_credentials.py
"""
import os
import sys
import getpass
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Import after setting up path so dotenv is already loaded
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

ENV_FILE = ".env"
load_dotenv(ENV_FILE)


def _ensure_env_file() -> None:
    """Create .env from .env.example if it doesn't exist."""
    if not os.path.exists(ENV_FILE):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ENV_FILE)
            logging.info(".env created from .env.example")
        else:
            open(ENV_FILE, "w").close()
            logging.info(".env created (empty)")


def _get_or_create_master_key() -> str:
    """Return existing MASTER_KEY from .env, or generate and save a new one."""
    existing = os.environ.get("MASTER_KEY", "").strip()
    if existing:
        logging.info("Using existing MASTER_KEY from .env")
        return existing

    new_key = Fernet.generate_key().decode()
    set_key(ENV_FILE, "MASTER_KEY", new_key)
    # Also set in current process environment
    os.environ["MASTER_KEY"] = new_key
    logging.info("New MASTER_KEY generated and saved to .env")
    return new_key


def main() -> None:
    print("\n=== VFS Global Credential Setup ===\n")
    _ensure_env_file()
    master_key = _get_or_create_master_key()

    # Import db after .env is ready (config reads MASTER_KEY from env)
    import db

    db.init_db()

    # Check if credentials already exist
    existing = db.get_credentials()
    if existing:
        email_existing, _ = existing
        overwrite = input(
            f"Credentials already stored for '{email_existing}'. Overwrite? [y/N]: "
        ).strip().lower()
        if overwrite != "y":
            print("Aborted. Existing credentials kept.")
            sys.exit(0)

    # Prompt for VFS credentials
    print("Enter your VFS Global login credentials.")
    print("(These will be stored encrypted — never in plaintext)\n")

    email = input("VFS Email: ").strip()
    if not email:
        print("Error: Email cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("VFS Password: ")
    if not password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    db.save_credentials(email, password, master_key)

    print("\n✓ Credentials saved successfully.")
    print(f"  Email:    {email}")
    print(f"  Password: {'*' * len(password)}")
    print(f"  Database: {db.DB_PATH}")
    print("\nNext steps:")
    print("  1. Add your GMAIL_APP_PASSWORD to .env")
    print("  2. Run: python main.py --once")


if __name__ == "__main__":
    main()
