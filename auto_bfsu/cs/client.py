import json
import re
import datetime
import urllib.parse
from bs4 import BeautifulSoup
import requests
from ..config import Config

class CSClient:
    def __init__(self, cas_client):
        self.cas_client = cas_client
        self.session = cas_client.session

    def login(self) -> bool:
        """
        Authenticate with CS website using the CAS session.
        """
        entry_url = "https://cs.bfsu.edu.cn/student/course/HwListPage.jsp"
        print(f"[CSClient] Authenticating to CS website...")
        try:
            # Hit the entry URL to see if it triggers CAS login or if it's already authenticated
            resp = self.session.get(entry_url, allow_redirects=True, timeout=15)
            
            # Simple check: if the page contains a specific homework string or the student title
            if resp.status_code == 200 and ("作业" in resp.text or "欢迎光临" in resp.text):
                print("[CSClient] CS Website login successful.")
                return True
            else:
                print(f"[CSClient] CS Website login check failed. Final URL: {resp.url}, Status: {resp.status_code}")
                return False
        except Exception as e:
            print(f"[CSClient] CS Website authentication error: {e}")
            return False

    def fetch_homework(self) -> list:
        """
        Fetch assignments from the CS homework page for all enrolled courses.
        """
        all_hw = []
        try:
            print("[CSClient] Fetching CS course list...")
            courses_url = "https://cs.bfsu.edu.cn/student/MyCoursePage.jsp"
            resp = self.session.get(courses_url, timeout=15)
            resp.encoding = 'gb18030'
            
            if resp.status_code != 200:
                print(f"[CSClient] Failed to fetch courses with status {resp.status_code}")
                return []
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            course_ids = set()
            for a in soup.find_all('a', href=True):
                match = re.search(r'GotoCourse\.jsp\?crs_id=(\d+)', a['href'])
                if match:
                    course_ids.add(match.group(1))
                    
            if not course_ids:
                print("[CSClient] No courses found on MyCoursePage.jsp. Falling back to direct fetch.")
                return self._fetch_homework_for_current_session()
                
            for crs_id in course_ids:
                print(f"[CSClient] Switching backend session to course ID {crs_id}...")
                goto_url = f"https://cs.bfsu.edu.cn/student/GotoCourse.jsp?crs_id={crs_id}"
                # The backend handles the session override and returns a 302 redirect
                self.session.get(goto_url, allow_redirects=True, timeout=15)
                
                # Now that the session is bound to this course, fetch its homework list
                course_hw = self._fetch_homework_for_current_session()
                all_hw.extend(course_hw)
                
            return all_hw
            
        except Exception as e:
            print(f"[CSClient] Error fetching CS homework list: {e}")
            return []

    def _fetch_homework_for_current_session(self) -> list:
        url = "https://cs.bfsu.edu.cn/student/course/HwListPage.jsp"
        all_hw = []
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'gb18030'
            if resp.status_code != 200:
                return []
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            course_name = "计算机系未知课程"
            
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                if "课程:" in text:
                    match = re.search(r"课程:([^\s（(]+(?:[（(].*?[)）])?)", text)
                    if match:
                        course_name = match.group(1).strip()
                        break
            
            hw_table = None
            for table in tables:
                headers = [th.get_text(strip=True) for th in table.find_all(['th', 'td'])]
                if '作业' in headers and '作业布置日期' in headers and '我的状态' in headers:
                    hw_table = table
                    break
            
            if not hw_table:
                return []
                
            rows = hw_table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if not cols or len(cols) < 4:
                    continue
                
                if cols[0].get_text(strip=True) == '作业':
                    continue
                    
                hw_title = cols[0].get_text(strip=True)
                hw_date = cols[1].get_text(strip=True)
                hw_status = cols[2].get_text(strip=True)
                
                try:
                    dt = datetime.datetime.strptime(hw_date, "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = datetime.date.today().strftime("%Y-%m-%d")
                    
                hw_id = f"cs_hw_{course_name}_{hw_title}_{hw_date}"
                
                all_hw.append({
                    'id': hw_id,
                    'title': f"[{course_name}] {hw_title}",
                    'publisher': "计算机系教学网站",
                    'date_str': date_str,
                    'url': url,
                    'summary': f"课程：{course_name}\n作业名：{hw_title}\n布置时间：{hw_date}\n当前状态：{hw_status}",
                    'category': "作业提交提醒",
                    'relevance': 100,
                    'relevance_summary': "计算机系系统检测到的未上交作业。",
                    'status': hw_status
                })
                
            return all_hw
        except Exception as e:
            print(f"[CSClient] Error parsing session homework: {e}")
            return []
