import json
import re
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import requests
from ..config import Config

class BBClient:
    def __init__(self, cas_client):
        self.cas_client = cas_client
        self.session = cas_client.session

    def login(self) -> bool:
        """
        Authenticate with Blackboard by hitting the SSO entry URL.
        This reuses the CAS session cookies.
        """
        sso_entry_url = "https://bb.bfsu.edu.cn/webapps/bb-ssoS-BBLEARN/execute/authValidate/customLogin?returnUrl=https://bb.bfsu.edu.cn/webapps/portal/execute/defaultTab&authProviderId=_41_1"
        print(f"[BBClient] Authenticating to Blackboard via SSO Entry...")
        try:
            # Hit the SSO entry URL and follow all redirects
            resp = self.session.get(sso_entry_url, allow_redirects=True, timeout=15)
            
            # Verify if login succeeded by checking for Blackboard domain cookies
            cookies_dict = self.session.cookies.get_dict(domain="bb.bfsu.edu.cn")
            has_cookies = "s_session_id" in cookies_dict or "JSESSIONID" in cookies_dict or any("bb.bfsu.edu.cn" in c.domain for c in self.session.cookies)
            
            if has_cookies:
                print("[BBClient] Blackboard SSO login successful.")
                return True
            else:
                # Check status code and redirects as fallback
                if resp.status_code == 200 and ("mybb" in resp.url or "execute/defaultTab" in resp.url or "tabs/tabAction" in resp.url):
                    print("[BBClient] Blackboard SSO login successful (detected via URL redirect).")
                    return True
                print(f"[BBClient] Blackboard login check failed. Final URL: {resp.url}, Status: {resp.status_code}")
                return False
        except Exception as e:
            print(f"[BBClient] Blackboard authentication error: {e}")
            return False

    def fetch_alerts(self) -> list:
        """
        Fetch alerts from Blackboard stream.
        """
        url = "https://bb.bfsu.edu.cn/webapps/streamViewer/streamViewer"
        
        # 1. Initial POST request
        providers = {}
        params = {
            "cmd": "loadStream",
            "streamName": "alerts",
            "providers": json.dumps(providers),
            "forOverview": "false"
        }
        
        all_entries = []
        course_map = {}  # Mapping of course_id -> course_name
        
        try:
            print("[BBClient] Fetching initial Blackboard alerts stream...")
            resp = self.session.post(url, data=params, timeout=15)
            if resp.status_code != 200:
                print(f"[BBClient] Initial fetch failed with status {resp.status_code}")
                return []
                
            data = resp.json()
            sv_providers = data.get("sv_providers", [])
            providers_dict = {p["sp_provider"]: p for p in sv_providers}
            
            entries = data.get("sv_streamEntries", [])
            all_entries.extend(entries)
            
            # Extract course mapping from initial call
            self._update_course_map(course_map, data)
            
            # 2. Run poll loop to gather more alerts if sv_moreData is True
            max_polls = 5
            for i in range(1, max_polls + 1):
                if not data.get("sv_moreData", False):
                    break
                    
                print(f"[BBClient] More alerts available. Polling batch {i}...")
                poll_params = {
                    "cmd": "loadStream",
                    "streamName": "alerts",
                    "providers": json.dumps(providers_dict),
                    "forOverview": "false",
                    "retrieveOnly": "true"
                }
                
                resp_poll = self.session.post(url, data=poll_params, timeout=15)
                if resp_poll.status_code != 200:
                    print(f"[BBClient] Poll {i} failed with status {resp_poll.status_code}")
                    break
                    
                poll_data = resp_poll.json()
                poll_entries = poll_data.get("sv_streamEntries", [])
                if poll_entries:
                    all_entries.extend(poll_entries)
                    
                # Update course mapping from poll response
                self._update_course_map(course_map, poll_data)
                
                # Update providers dict
                new_providers = poll_data.get("sv_providers", [])
                for p in new_providers:
                    prov_id = p["sp_provider"]
                    if prov_id not in providers_dict:
                        providers_dict[prov_id] = p
                    else:
                        existing = providers_dict[prov_id]
                        if p.get("sp_newest", -1) > existing.get("sp_newest", -1):
                            existing["sp_newest"] = p["sp_newest"]
                        if p.get("sp_oldest", 9007199254740992) < existing.get("sp_oldest", 9007199254740992):
                            existing["sp_oldest"] = p["sp_oldest"]
                        if p.get("sp_refreshDate", 0) > existing.get("sp_refreshDate", 0):
                            existing["sp_refreshDate"] = p["sp_refreshDate"]
                
                # Update loop data reference
                data = poll_data
                
        except Exception as e:
            print(f"[BBClient] Error during alerts fetching: {e}")
            
        print(f"[BBClient] Fetched {len(all_entries)} raw stream entries.")
        
        # 3. Parse and clean entries
        parsed_alerts = []
        for entry in all_entries:
            try:
                alert_id = entry.get("se_id")
                if not alert_id:
                    continue
                    
                timestamp_ms = entry.get("se_timestamp")
                if timestamp_ms:
                    date_str = datetime.datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
                else:
                    date_str = datetime.date.today().strftime("%Y-%m-%d")
                    
                course_id = entry.get("se_courseId")
                publisher = course_map.get(course_id) if course_id else None
                if not publisher:
                    # Try to fall back to title in itemSpecificData
                    item_data = entry.get("itemSpecificData", {})
                    publisher = item_data.get("title") if item_data else None
                if not publisher:
                    publisher = "Blackboard"
                    
                publisher = publisher.strip()
                
                # HTML cleanup for title
                raw_context = entry.get("se_context", "")
                if raw_context:
                    soup = BeautifulSoup(raw_context, "html.parser")
                    # Remove inlineContextMenu (dismiss/browse buttons)
                    for menu in soup.find_all(class_="inlineContextMenu"):
                        menu.decompose()
                    cleaned_title = soup.get_text(separator=" ", strip=True)
                else:
                    cleaned_title = "未命名 Blackboard 通知"
                
                # Resolve details/summary
                cleaned_details = ""
                raw_details = entry.get("se_details", "")
                if raw_details:
                    soup_details = BeautifulSoup(raw_details, "html.parser")
                    cleaned_details = soup_details.get_text(separator=" ", strip=True)
                
                # Build detail action URL
                item_uri = entry.get("se_itemUri", "")
                if item_uri:
                    if item_uri.startswith("http"):
                        url_full = item_uri
                    else:
                        url_full = urllib.parse.urljoin("https://bb.bfsu.edu.cn", item_uri)
                else:
                    url_full = "https://bb.bfsu.edu.cn/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_1_1"
                
                parsed_alerts.append({
                    "id": alert_id,
                    "title": cleaned_title,
                    "publisher": publisher,
                    "date_str": date_str,
                    "url": url_full,
                    "summary": cleaned_details or cleaned_title,
                    "category": "课程学习",
                    "relevance": 90,
                    "relevance_summary": f"课程通知: {publisher}",
                    "source": "BB"
                })
            except Exception as ex:
                print(f"[BBClient] Error parsing alert entry {entry.get('se_id')}: {ex}")
                
        # Sort by date descending
        parsed_alerts.sort(key=lambda x: x["date_str"], reverse=True)
        return parsed_alerts

    def _update_course_map(self, course_map: dict, data: dict):
        """Helper to extract course mappings from response data."""
        extras = data.get("sv_extras", {})
        if not extras:
            return
            
        # 1. Look under sx_filters choices
        filters = extras.get("sx_filters", [])
        for f in filters:
            if f.get("attribute") == "se_courseId":
                choices = f.get("choices", {})
                if choices:
                    for cid, cname in choices.items():
                        course_map[cid] = cname
                        
        # 2. Look under sx_courses list of dicts
        courses = extras.get("sx_courses", [])
        for c in courses:
            cid = c.get("id")
            cname = c.get("name")
            if cid and cname:
                course_map[cid] = cname

if __name__ == "__main__":
    # Test execution
    import sys
    from pathlib import Path
    # Add root directory to path so we can import auto_bfsu
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from auto_bfsu.auth.cas_client import CASClient
    cas = CASClient()
    # Attempt to load saved session
    if cas._load_saved_session():
        bb = BBClient(cas)
        if bb.login():
            alerts = bb.fetch_alerts()
            print(f"Successfully fetched {len(alerts)} alerts:")
            for a in alerts[:5]:
                print(f"- [{a['date_str']}] [{a['publisher']}] {a['title']} -> {a['url']}")
        else:
            print("Blackboard login failed.")
    else:
        print("No saved CAS session. Please run login first.")
