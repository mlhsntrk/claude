"""
One-time credential setup script.

Run this once to:
  1. Generate a MASTER_KEY (Fernet key) and write it to .env
  2. Prompt for your VFS Global password (email is read from VFS_EMAIL in .env)
  3. Encrypt the password with the MASTER_KEY
  4. Store the encrypted password in vfs.db

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

    # Import db/config after .env is ready
    import db
    from config import VFS_EMAIL

    db.init_db()

    # Validate that VFS_EMAIL is set in .env
    if not VFS_EMAIL:
        print("Error: VFS_EMAIL is not set in .env")
        print("  Add the line:  VFS_EMAIL=your@email.com  to your .env file first.")
        sys.exit(1)

    # Check if a password is already stored
    existing = db.get_encrypted_password()
    if existing:
        overwrite = input(
            f"A password is already stored for '{VFS_EMAIL}'. Overwrite? [y/N]: "
        ).strip().lower()
        if overwrite != "y":
            print("Aborted. Existing password kept.")
            sys.exit(0)

    # Prompt for VFS password only
    print(f"VFS Email (from .env): {VFS_EMAIL}")
    print("Enter your VFS Global password.")
    print("(Will be stored encrypted — never in plaintext)\n")

    password = getpass.getpass("VFS Password: ")
    if not password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    db.save_credentials(password, master_key)

    print("\n✓ Password saved successfully.")
    print(f"  Email:    {VFS_EMAIL}  (from .env)")
    print(f"  Password: {'*' * len(password)}  (Fernet-encrypted in DB)")
    print(f"  Database: {db.DB_PATH}")
    print("\nNext steps:")
    print("  1. Add GMAIL_APP_PASSWORD and NOTIFICATION_EMAIL to .env")
    print("  2. Run: python main.py --once")


if __name__ == "__main__":
    main()
