import os
from pathlib import Path
from dotenv import load_dotenv

import threading
from .auth.crypto import decrypt_password

import sys

# Load .env file
if getattr(sys, "frozen", False) or hasattr(sys, "nuitka_executable"):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

class Config:
    BASE_DIR = BASE_DIR
    # 1. Credentials (now supports DPAPI-encrypted usernames)
    USERNAME_RAW = os.getenv("BFSU_USERNAME", "").strip()
    USERNAME = decrypt_password(USERNAME_RAW)
    
    PASSWORD_RAW = os.getenv("BFSU_PASSWORD", "").strip()
    PASSWORD = decrypt_password(PASSWORD_RAW)
    
    STUDENT_ID_RAW = os.getenv("BFSU_STUDENT_ID", "").strip()
    STUDENT_ID = decrypt_password(STUDENT_ID_RAW)
    
    SIS_PASSWORD_RAW = os.getenv("SIS_PASSWORD", "").strip()
    SIS_PASSWORD = decrypt_password(SIS_PASSWORD_RAW) or PASSWORD

    # 2. LLM Config (now supports DPAPI-encrypted API Key)
    LLM_API_KEY_RAW = os.getenv("LLM_API_KEY", "").strip()
    LLM_API_KEY = decrypt_password(LLM_API_KEY_RAW)
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat").strip()

    # 3. Notification Keywords
    KEYWORDS_RAW = os.getenv("NOTIFICATION_KEYWORDS", "选课,签到,考试,放假,学分,讲座,实训,成绩")
    KEYWORDS = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]

    # 4. Storage paths (relative to root)
    SESSION_PATH = BASE_DIR / "session.json"
    MAX_HISTORY_CACHE = 500


    # 5. SIS Course Sign-In Scheduled Times (Default slots)
    SIS_SIGNIN_TIMES_RAW = os.getenv("SIS_SIGNIN_TIMES", "08:00,10:00,14:00,16:00,18:00").strip()
    SIS_SIGNIN_TIMES = [t.strip() for t in SIS_SIGNIN_TIMES_RAW.split(",") if t.strip()]

    # 6. Global Module Switches
    DEVELOPER_MODE = os.getenv("DEVELOPER_MODE", "False").strip().lower() == "true"
    ENABLE_PORTAL_CHECK = os.getenv("ENABLE_PORTAL_CHECK", "True").strip().lower() == "true"
    ENABLE_BB_CHECK = os.getenv("ENABLE_BB_CHECK", os.getenv("ENABLE_BB", "True")).strip().lower() == "true"
    ENABLE_CS_CHECK = os.getenv("ENABLE_CS_CHECK", "True").strip().lower() == "true"
    ENABLE_SIS_CHECK = os.getenv("ENABLE_SIS_CHECK", "False").strip().lower() == "true"

    # 7. Background Polling Notification Interval (in minutes, min 10m)
    try:
        # Backward compatibility with old CHECK_INTERVAL
        NOTIFICATION_INTERVAL = int(os.getenv("NOTIFICATION_INTERVAL", os.getenv("CHECK_INTERVAL", "60")).strip())
        if NOTIFICATION_INTERVAL < 10:
            NOTIFICATION_INTERVAL = 10
    except Exception:
        NOTIFICATION_INTERVAL = 60

    # 8. SIS Window Polling Interval (in minutes, min 1m)
    try:
        SIS_CHECK_INTERVAL = int(os.getenv("SIS_CHECK_INTERVAL", "5").strip())
        if SIS_CHECK_INTERVAL < 1:
            SIS_CHECK_INTERVAL = 1
    except Exception:
        SIS_CHECK_INTERVAL = 5


    @classmethod
    def validate(cls):
        """Validate crucial configurations."""
        errors = []
        if not cls.USERNAME:
            errors.append("BFSU_USERNAME is missing in .env")
        if not cls.PASSWORD:
            errors.append("BFSU_PASSWORD is missing in .env")
        if not cls.STUDENT_ID or cls.STUDENT_ID == "YOUR_STUDENT_ID_HERE":
            errors.append("BFSU_STUDENT_ID is not configured in .env. Please fill in your Student ID.")
        return errors


def auto_encrypt_plain_env():
    """Automatically and proactively encrypt plain-text credentials in the .env file on startup."""
    import re
    from .auth.crypto import encrypt_password
    
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
        
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        new_lines = []
        for line in content.splitlines():
            line_str = line.strip()
            # Match keys: BFSU_USERNAME, BFSU_PASSWORD, BFSU_STUDENT_ID, SIS_PASSWORD, LLM_API_KEY
            match = re.match(r"^([A-Z_]+)\s*=\s*(.*)$", line_str)
            if match:
                key, val = match.group(1), match.group(2).strip()
                if key in ["BFSU_USERNAME", "BFSU_PASSWORD", "BFSU_STUDENT_ID", "SIS_PASSWORD", "LLM_API_KEY"]:
                    # Check if value exists and is NOT already encrypted
                    if val and not val.startswith("DPAPI:") and not val.startswith("OBF:"):
                        enc_val = encrypt_password(val)
                        line = f"{key}={enc_val}"
                        modified = True
            new_lines.append(line)
            
        if modified:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            print("[Config] Plain-text credentials in .env have been automatically encrypted via DPAPI.")
    except Exception as e:
        print(f"[Config] Error auto-encrypting plain-text .env: {e}")

# Run proactive encryption on startup
auto_encrypt_plain_env()
