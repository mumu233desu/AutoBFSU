import json
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from ..config import Config
from .des_crypto import DESCryptographer
from .crypto import encrypt_password, decrypt_password

# Suppress insecure request warnings if any
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CASClient:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session.headers.update(self.headers)

    def _load_saved_session(self) -> bool:
        """Load session cookies from local file if they exist (supports DPAPI decrypt)."""
        path = Path(Config.SESSION_PATH)
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_content = f.read().strip()
            
            if not raw_content:
                return False
                
            # Decrypt contents using DPAPI / basic fallback if prefixed
            decrypted_content = decrypt_password(raw_content)
            data = json.loads(decrypted_content)
            
            if isinstance(data, list):
                # Detailed cookie format
                for c in data:
                    self.session.cookies.set(
                        c['name'], c['value'],
                        domain=c.get('domain', ''),
                        path=c.get('path', '/')
                    )
            elif isinstance(data, dict):
                # Flat dict fallback
                for name, value in data.items():
                    self.session.cookies.set(name, value, domain="passport.bfsu.edu.cn")
                    self.session.cookies.set(name, value, domain="my.bfsu.edu.cn")
            return True
        except Exception as e:
            print(f"[CASClient] Error loading session: {e}")
            return False

    def _save_session(self):
        """Save current session cookies to local file under DPAPI encryption."""
        path = Path(Config.SESSION_PATH)
        try:
            cookies = []
            for cookie in self.session.cookies:
                cookies.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path
                })
            session_str = json.dumps(cookies, indent=4)
            # Encrypt the JSON data using DPAPI
            encrypted_str = encrypt_password(session_str)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(encrypted_str)
            print("[CASClient] Session cookies saved and encrypted successfully.")
        except Exception as e:
            print(f"[CASClient] Error saving session: {e}")

    def check_login_status(self) -> bool:
        """Check if current session is already logged in to Digital BFSU."""
        try:
            # Attempt to access the portal dashboard
            url = "https://my.bfsu.edu.cn/tp_up/"
            # Do not redirect to see where it wants to take us
            r = self.session.get(url, allow_redirects=False, timeout=10)
            if r.status_code == 200 and any(x in r.text for x in ["数字北外", "北京外国语大学", "退出登录", "/tp_up/logout"]):
                return True
            # If it redirects back to passport.bfsu.edu.cn, it means we are not logged in
            if r.status_code == 302:
                location = r.headers.get("Location", "")
                if "passport.bfsu.edu.cn" not in location:
                    # Some other portal redirect, try following once
                    r2 = self.session.get(location, allow_redirects=False, timeout=10)
                    if r2.status_code == 200 and any(x in r2.text for x in ["数字北外", "北京外国语大学", "退出登录", "/tp_up/logout"]):
                        return True
            return False
        except Exception:
            return False

    def login(self, sms_code_callback=None) -> bool:
        """
        Log in to BFSU Unified Identity Authentication.
        If SMS 2FA is needed, calls `sms_code_callback(mobile_number) -> str` to get the verification code.
        """
        print("[CASClient] Checking session status...")
        if self._load_saved_session():
            if self.check_login_status():
                print("[CASClient] Already logged in using cached session!")
                return True
            else:
                print("[CASClient] Cached session expired. Clearing stale cookies and attempting password login...")
                self.session.cookies.clear()

        # 1. Fetch login page to get lt, execution, _eventId, and form action JSESSIONID
        login_url = "https://passport.bfsu.edu.cn/tpass/login?service=https%3A%2F%2Fmy.bfsu.edu.cn%2Ftp_up%2F"
        try:
            resp = self.session.get(login_url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            lt_elem = soup.find('input', {'id': 'lt'})
            execution_elem = soup.find('input', {'name': 'execution'})
            event_elem = soup.find('input', {'name': '_eventId'})
            form_elem = soup.find('form', {'id': 'loginForm'})

            if not (lt_elem and execution_elem and event_elem and form_elem):
                raise ValueError("Could not find standard CAS login form elements on page.")

            lt = lt_elem.get('value')
            execution = execution_elem.get('value')
            event_id = event_elem.get('value')
            action = form_elem.get('action')

            # 2. Encrypt credentials via custom DES
            rsa_payload = DESCryptographer.encrypt(Config.USERNAME, Config.PASSWORD, lt)

            # 3. Call 'device' validation POST endpoint
            device_url = "https://passport.bfsu.edu.cn/tpass/device"
            device_data = {
                "ul": len(Config.USERNAME),
                "pl": len(Config.PASSWORD),
                "rsa": rsa_payload,
                "method": "login"
            }
            
            device_headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": login_url,
                "Origin": "https://passport.bfsu.edu.cn"
            }
            
            device_resp = self.session.post(device_url, data=device_data, headers=device_headers, timeout=10)
            res_json = device_resp.json()
            print(f"[CASClient] Device check response: {res_json}")

            info = res_json.get("info")
            
            if info in ["unbind", "device_expire"]:
                mobile = res_json.get("mobile", "188*****011")
                print(f"[CASClient] 2FA required for mobile {mobile}. Triggering SMS send...")
                
                # Send the SMS verification code
                send_data = {"method": "sendCode"}
                send_resp = self.session.post(device_url, data=send_data, headers=device_headers, timeout=10)
                send_json = send_resp.json()
                print(f"[CASClient] SMS send response: {send_json}")
                
                if send_json.get("info") == "max":
                    raise RuntimeWarning("SMS sending failed: too frequent requests.")
                elif send_json.get("info") != "ok":
                    raise RuntimeError("SMS sending failed for unknown reasons.")

                # Prompt user for verification code using callback (e.g. GUI dialog)
                if sms_code_callback is None:
                    # Fallback to console input if no callback is supplied
                    sms_code = input(f"Please enter the verification code sent to {mobile}: ").strip()
                else:
                    sms_code = sms_code_callback(mobile)

                if not sms_code:
                    raise ValueError("Verification code cannot be empty.")

                # Submit code to bind device
                bind_data = {
                    "code": sms_code,
                    "saveDevice": "1",  # Request the server to trust this device
                    "method": "bind"
                }
                bind_resp = self.session.post(device_url, data=bind_data, headers=device_headers, timeout=10)
                bind_json = bind_resp.json()
                print(f"[CASClient] Device bind response: {bind_json}")

                if bind_json.get("info") != "ok":
                    raise ValueError("SMS verification code is incorrect or expired.")
                
                print("[CASClient] Device successfully bound!")

            elif info == "ok":
                print("[CASClient] Device is already recognized/trusted. Bypassing 2FA.")
            elif info in ["nf", "err"]:
                raise ValueError("Incorrect username or password.")
            else:
                raise RuntimeError(f"Unexpected device response: {res_json}")

            # 4. Final Form Submission
            post_url = "https://passport.bfsu.edu.cn" + action
            login_data = {
                "rsa": rsa_payload,
                "ul": len(Config.USERNAME),
                "pl": len(Config.PASSWORD),
                "lt": lt,
                "execution": execution,
                "_eventId": event_id
            }
            
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Referer"] = login_url
            
            print("[CASClient] Submitting unified CAS login form...")
            login_resp = self.session.post(post_url, data=login_data, headers=headers, allow_redirects=True, timeout=15)
            
            # 5. Check if successfully logged in (support meta refresh redirect)
            soup_redirect = BeautifulSoup(login_resp.text, 'html.parser')
            meta_tag = soup_redirect.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
            if meta_tag and 'url=' in meta_tag.get('content', '').lower():
                content_attr = meta_tag.get('content', '')
                url_part = re.search(r'url=(.+)', content_attr, re.I)
                if url_part:
                    redirect_url = url_part.group(1).strip()
                    redirect_url = urllib.parse.urljoin(post_url, redirect_url)
                    print(f"[CASClient] Detected meta-refresh redirect to {redirect_url}. Following...")
                    login_resp = self.session.get(redirect_url, timeout=15)

            if any(x in login_resp.text for x in ["数字北外", "北京外国语大学", "退出登录", "/tp_up/logout"]) or self.check_login_status():
                print("[CASClient] Login successful! Persistent session established.")
                self._save_session()
                return True
            else:
                # Dump diagnostic page to scratch
                Path("scratch").mkdir(exist_ok=True)
                with open("scratch/login_failed.html", "w", encoding="utf-8") as f:
                    f.write(login_resp.text)
                raise RuntimeError("Login failed: page did not redirect to Digital BFSU portal dashboard. Diagnostic file saved.")

        except Exception as e:
            print(f"[CASClient] Error during authentication: {e}")
            return False
