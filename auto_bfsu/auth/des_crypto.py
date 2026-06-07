import execjs
from pathlib import Path

# Path to des.js
CURRENT_DIR = Path(__file__).resolve().parent
JS_PATH = CURRENT_DIR / "des.js"

class DESCryptographer:
    _ctx = None

    @classmethod
    def _get_context(cls):
        """Compile and cache the JS execution context."""
        if cls._ctx is None:
            if not JS_PATH.exists():
                raise FileNotFoundError(f"Missing required file: {JS_PATH}")
            with open(JS_PATH, "r", encoding="utf-8") as f:
                js_code = f.read()
            cls._ctx = execjs.compile(js_code)
        return cls._ctx

    @classmethod
    def encrypt(cls, username: str, password: str, lt: str) -> str:
        """
        Encrypt username, password and lt (login ticket) using the BFSU custom DES algorithm.
        Equivalent to strEnc(u+p+lt, '1', '2', '3') in des.js.
        """
        ctx = cls._get_context()
        payload = username + password + lt
        # Call the Javascript strEnc function with keys '1', '2', '3'
        encrypted = ctx.call("strEnc", payload, '1', '2', '3')
        return encrypted
