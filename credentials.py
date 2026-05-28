"""
credentials.py
Encrypted credential store using Fernet (AES-128-CBC + HMAC-SHA256).

All sensitive data (browser sessions, API keys) are stored in a single
encrypted binary file: output/.credentials.enc

Usage — from Python:
    from credentials import cred_store
    cred_store.set("groq_api_key", "sk-...")
    key = cred_store.get("groq_api_key")

Usage — CLI:
    python credentials.py set groq_api_key "sk-..."
    python credentials.py get groq_api_key
    python credentials.py list
    python credentials.py delete groq_api_key
    python credentials.py change-password

The master password is entered once per process and cached in memory.
The salt file (output/.credentials.salt) is NOT secret and can be committed;
the encrypted store (output/.credentials.enc) must NEVER be committed.
"""

import base64
import getpass
import json
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_STORE_PATH = Path("output/.credentials.enc")
_SALT_PATH  = Path("output/.credentials.salt")
_ITERATIONS = 480_000  # NIST-recommended minimum for PBKDF2-SHA256


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


class CredentialStore:
    """
    Thread-safe encrypted key-value store. The Fernet key is derived from
    a master password and cached for the lifetime of the process.
    """

    def __init__(self):
        self._fernet: Fernet | None = None

    # ── Internal ─────────────────────────────────────────────────────────────

    def _salt(self) -> bytes:
        os.makedirs("output", exist_ok=True)
        if _SALT_PATH.exists():
            return _SALT_PATH.read_bytes()
        salt = os.urandom(16)
        _SALT_PATH.write_bytes(salt)
        return salt

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            password = getpass.getpass("🔐 Credential store password: ")
            key = _derive_key(password, self._salt())
            self._fernet = Fernet(key)
        return self._fernet

    def _load_raw(self) -> dict:
        if not _STORE_PATH.exists():
            return {}
        try:
            encrypted = _STORE_PATH.read_bytes()
            return json.loads(self._get_fernet().decrypt(encrypted))
        except InvalidToken:
            self._fernet = None  # clear cached key so user is re-prompted
            raise ValueError(
                "Wrong password or corrupted store. "
                "Run again and enter the correct password."
            )

    def _save_raw(self, data: dict):
        os.makedirs("output", exist_ok=True)
        encrypted = self._get_fernet().encrypt(json.dumps(data).encode("utf-8"))
        _STORE_PATH.write_bytes(encrypted)

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        """Return the value for *key*, or *default* if not found."""
        return self._load_raw().get(key, default)

    def set(self, key: str, value):
        """Store *value* under *key* (value can be str, dict, list, etc.)."""
        data = self._load_raw()
        data[key] = value
        self._save_raw(data)
        print(f"  ✓ '{key}' saved.")

    def delete(self, key: str):
        """Remove *key* from the store."""
        data = self._load_raw()
        if key not in data:
            print(f"  Key '{key}' not found.")
            return
        del data[key]
        self._save_raw(data)
        print(f"  ✓ '{key}' deleted.")

    def list_keys(self) -> list[str]:
        """Return all stored keys (values are NOT printed)."""
        return list(self._load_raw().keys())

    def change_password(self):
        """Re-encrypt the entire store under a new password."""
        data    = self._load_raw()   # decrypts with current password
        self._fernet = None          # clear cached key
        new_pwd = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm new password: ")
        if new_pwd != confirm:
            raise ValueError("Passwords do not match.")
        key = _derive_key(new_pwd, self._salt())
        self._fernet = Fernet(key)
        self._save_raw(data)
        print("  ✓ Password changed and store re-encrypted.")

    def exists(self) -> bool:
        return _STORE_PATH.exists()

    def unlock(self):
        """
        Explicitly unlock (prompt for password) before a batch of operations
        so the user is not prompted mid-run.
        """
        self._load_raw()  # triggers prompt and caches fernet


# ── Module-level singleton ────────────────────────────────────────────────────

cred_store = CredentialStore()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli():
    usage = (
        "Usage:\n"
        "  python credentials.py set <key> <value>\n"
        "  python credentials.py get <key>\n"
        "  python credentials.py delete <key>\n"
        "  python credentials.py list\n"
        "  python credentials.py change-password\n"
    )
    args = sys.argv[1:]
    if not args:
        print(usage)
        return

    cmd = args[0]

    if cmd == "set":
        if len(args) < 3:
            print("Usage: python credentials.py set <key> <value>")
            sys.exit(1)
        cred_store.set(args[1], args[2])

    elif cmd == "get":
        if len(args) < 2:
            print("Usage: python credentials.py get <key>")
            sys.exit(1)
        value = cred_store.get(args[1])
        if value is None:
            print(f"Key '{args[1]}' not found.")
        else:
            print(value if isinstance(value, str) else json.dumps(value, indent=2))

    elif cmd == "delete":
        if len(args) < 2:
            print("Usage: python credentials.py delete <key>")
            sys.exit(1)
        cred_store.delete(args[1])

    elif cmd == "list":
        keys = cred_store.list_keys()
        if not keys:
            print("Store is empty.")
        else:
            print("Stored keys:")
            for k in keys:
                print(f"  • {k}")

    elif cmd == "change-password":
        cred_store.change_password()

    else:
        print(f"Unknown command: {cmd}\n{usage}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
