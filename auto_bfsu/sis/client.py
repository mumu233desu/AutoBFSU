import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from ..config import Config

class SISClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://cs.bfsu.edu.cn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.base_url}/index.jsp",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session.headers.update(self.headers)
        # Force GBK encoding for all request decodings where not specified
        self.session.encoding = 'gbk'

    def login(self) -> bool:
        """
        Log in to the SIS platform using the student ID and password.
        Note: The login parameters must be GBK-encoded.
        """
        login_action_url = f"{self.base_url}/action/login.jsp"
        print(f"[SISClient] Logging in to SIS Platform with Student ID: {Config.STUDENT_ID}...")

        # Ensure credentials are set
        if not Config.STUDENT_ID or Config.STUDENT_ID == "YOUR_STUDENT_ID_HERE":
            print("[SISClient] Error: Student ID not configured in .env!")
            return False

        # Build form parameters
        payload = {
            "user_type": "student",
            "user_id": Config.STUDENT_ID,
            "user_pw": Config.SIS_PASSWORD
        }

        try:
            # We encode data using GBK manually just in case, but requests handles dict encoding based on headers or defaults.
            encoded_payload = urllib.parse.urlencode(payload, encoding='gbk')
            
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            resp = self.session.post(login_action_url, data=encoded_payload, headers=headers, allow_redirects=True, timeout=15)
            
            # Since the site is GBK, decode properly
            html_text = resp.content.decode('gbk', errors='ignore')
            
            # If the response URL redirects to index.jsp with message=0, it means login failed
            if "message=0" in resp.url or "密码错误" in html_text or "用户不存在" in html_text:
                print(f"[SISClient] Login failed! Please verify your student ID ({Config.STUDENT_ID}) and password.")
                return False

            # Check if login is successful (look for typical student portal markers: "退出", "学生", "我的课程")
            if any(x in html_text for x in ["退出", "学生", "我的课程", "修改密码", "个人资料", Config.STUDENT_ID]):
                print("[SISClient] Login successful!")
                return True
            
            # Diagnostic save
            import os
            os.makedirs("scratch", exist_ok=True)
            with open("scratch/sis_login_response.html", "w", encoding="utf-8") as f:
                f.write(html_text)

            print("[SISClient] Warning: Could not find clear success indicator, but no error URL was found. Proceeding with caution.")
            return True

        except Exception as e:
            print(f"[SISClient] Login exception: {e}")
            return False

    def auto_signin_all_courses(self) -> list:
        """
        Scan all active courses and perform automatic sign-in if any active sign-in task is found.
        Returns a list of dicts: [{"course_name": str, "status": "success"/"failed", "reason": str}]
        """
        print("[SISClient] Scanning courses for active sign-in tasks...")
        results = []
        
        try:
            # Step 1: Fetch student courses list from MyCoursePage.jsp
            student_courses_url = f"{self.base_url}/student/MyCoursePage.jsp"
            resp = self.session.get(student_courses_url, timeout=15)
            html_text = resp.content.decode('gbk', errors='ignore')

            # Parse courses
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # Heuristic: Find all links pointing to courses. Usually contain "GotoCourse.jsp"
            course_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                course_name = a.get_text(strip=True).replace('\xa0', ' ')
                if any(x in href for x in ['GotoCourse.jsp', 'crs_id=', 'course.jsp', 'courseId=']):
                    full_url = urllib.parse.urljoin(student_courses_url, href)
                    # Deduplicate course URLs
                    if full_url not in [c['url'] for c in course_links]:
                        course_links.append({'name': course_name, 'url': full_url})

            print(f"[SISClient] Found {len(course_links)} courses in your profile.")

            # Step 2: Loop through each course page to scan for active sign-ins on SignListPage.jsp
            for course in course_links:
                print(f"[SISClient] Entering course context: {course['name']}...")
                
                # 1. Fetch GotoCourse.jsp to set Tomcat course session context
                goto_resp = self.session.get(course['url'], timeout=10)
                if goto_resp.status_code != 200:
                    print(f"[SISClient] Failed to set session context for course {course['name']}.")
                    continue
                
                # 2. Fetch the SignListPage.jsp in the course context
                sign_list_url = urllib.parse.urljoin(goto_resp.url, "SignListPage.jsp")
                print(f"[SISClient] Checking sign-in page: {sign_list_url}...")
                
                sign_resp = self.session.get(sign_list_url, timeout=10)
                sign_html = sign_resp.content.decode('gbk', errors='ignore')
                sign_soup = BeautifulSoup(sign_html, 'html.parser')

                # Target only the main content area (table with class="content") to avoid matching sidebar navigation links
                content_area = sign_soup.find('table', class_='content')
                if not content_area:
                    content_area = sign_soup

                # Heuristic: Find if there's any active sign-in button or link
                signin_found = False
                
                # 1. Check all <input> buttons with value="签到" that are NOT disabled in the main content area
                for btn in content_area.find_all('input', {'type': ['button', 'submit']}):
                    val = btn.get('value', '')
                    is_disabled = btn.has_attr('disabled')
                    if "签到" in val and not is_disabled:
                        print(f"[SISClient] Found enabled sign-in button in course: {course['name']}!")
                        # Parse onclick attribute
                        onclick = btn.get('onclick', '')
                        if onclick:
                            # Match location.href = '...' or window.location = '...'
                            match = re.search(r"(?:window\.)?location(?:\.href)?\s*=\s*['\"](.*?)['\"]", onclick)
                            if match:
                                target_href = match.group(1)
                                target_url = urllib.parse.urljoin(sign_list_url, target_href)
                                print(f"[SISClient] Clicking button link: {target_url}")
                                if self._click_signin_link(target_url, sign_list_url):
                                    results.append({"course_name": course['name'], "status": "success", "reason": "点击签到按钮成功"})
                                    signin_found = True
                                else:
                                    results.append({"course_name": course['name'], "status": "failed", "reason": "点击签到按钮失败"})
                                    signin_found = True
                                break
                            else:
                                print(f"[SISClient] Warning: Could not parse URL from button onclick: {onclick}")
                        
                        # Fallback: if it's inside a form or a submit button
                        parent_form = btn.find_parent('form')
                        if parent_form and not signin_found:
                            print("[SISClient] Submitting sign-in form containing button...")
                            if self._submit_signin_form(parent_form, sign_list_url):
                                results.append({"course_name": course['name'], "status": "success", "reason": "提交签到表单成功"})
                                signin_found = True
                            else:
                                results.append({"course_name": course['name'], "status": "failed", "reason": "提交签到表单失败"})
                                signin_found = True
                            break

                # 2. Check all forms in the main content area if button didn't resolve
                if not signin_found:
                    for form in content_area.find_all('form'):
                        action = form.get('action', '')
                        form_text = form.get_text()
                        if any(x in action.lower() or x in form_text for x in ['签到', 'signin', 'checkin', 'sign']):
                            print(f"[SISClient] Found active sign-in form in course: {course['name']}")
                            if self._submit_signin_form(form, sign_list_url):
                                results.append({"course_name": course['name'], "status": "success", "reason": "提交表单成功"})
                                signin_found = True
                            else:
                                results.append({"course_name": course['name'], "status": "failed", "reason": "提交表单失败"})
                                signin_found = True
                            break

                # 3. Check all links in the main content area, excluding navigation links
                if not signin_found:
                    for a in content_area.find_all('a', href=True):
                        href = a['href']
                        link_text = a.get_text(strip=True)
                        # Exclude self-referencing SignListPage to prevent false success from navigation
                        if "signlistpage" in href.lower():
                            continue
                        if any(x in href.lower() or x in link_text for x in ['签到', 'signin', 'checkin', 'sign_action']):
                            print(f"[SISClient] Found active sign-in link in course: {course['name']} -> {link_text}")
                            target_url = urllib.parse.urljoin(sign_list_url, href)
                            if self._click_signin_link(target_url, sign_list_url):
                                results.append({"course_name": course['name'], "status": "success", "reason": f"点击签到链接成功 ({link_text})"})
                                signin_found = True
                            else:
                                results.append({"course_name": course['name'], "status": "failed", "reason": f"点击签到链接失败 ({link_text})"})
                                signin_found = True
                            break
            
            if not results:
                print("[SISClient] No active live sign-in activities found on the teaching platform right now.")
                
        except Exception as e:
            print(f"[SISClient] Error during auto sign-in process: {e}")

        return results

    def _submit_signin_form(self, form_soup, referer_url) -> bool:
        """Submit a found sign-in HTML form."""
        action = form_soup.get('action')
        target_url = urllib.parse.urljoin(referer_url, action)
        
        # Build form data
        data = {}
        for inp in form_soup.find_all(['input', 'select', 'textarea']):
            name = inp.get('name')
            if name:
                # Use default value or text
                data[name] = inp.get('value', '')

        # Standard sign-in values if missing
        if 'action' not in data and 'act' not in data:
            data['action'] = 'signin'

        headers = self.headers.copy()
        headers["Referer"] = referer_url
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            encoded_data = urllib.parse.urlencode(data, encoding='gbk')
            resp = self.session.post(target_url, data=encoded_data, headers=headers, timeout=10)
            resp_text = resp.content.decode('gbk', errors='ignore')
            if "成功" in resp_text or resp.status_code == 200:
                print("[SISClient] Form sign-in successful!")
                return True
        except Exception as e:
            print(f"[SISClient] Error submitting sign-in form: {e}")
        return False

    def _click_signin_link(self, href, referer_url) -> bool:
        """Submit/Fetch a found sign-in hyperlink."""
        target_url = urllib.parse.urljoin(referer_url, href)
        headers = self.headers.copy()
        headers["Referer"] = referer_url

        try:
            resp = self.session.get(target_url, headers=headers, timeout=10)
            resp_text = resp.content.decode('gbk', errors='ignore')
            if "成功" in resp_text or resp.status_code == 200:
                print("[SISClient] Link sign-in successful!")
                return True
        except Exception as e:
            print(f"[SISClient] Error invoking sign-in link: {e}")
        return False
