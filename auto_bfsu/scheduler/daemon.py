import time
import random
import datetime
import threading
from pathlib import Path
from ..config import Config
from ..auth.cas_client import CASClient
from ..portal.scraper import PortalScraper
from ..llm.summarizer import LLMSummarizer
from ..sis.client import SISClient
from ..ui.dialog import request_sms_code
from ..ui.notifier import show_notification
from ..utils.history import HistoryManager

class BFSUAutomationDaemon:
    def __init__(self):
        self.cas_client = CASClient()
        self.portal_scraper = PortalScraper(self.cas_client)
        self.summarizer = LLMSummarizer()
        self.sis_client = SISClient()
        self.check_event = threading.Event()
        self.stop_event = threading.Event()
        self.completed_sis_slots = set()  # Tracks completed daily check-ins: "YYYY-MM-DD_HH:MM"

    def run_once(self, force_ui_test: bool = False, force_sis_check: bool = False) -> bool:
        """
        Executes a single complete cycle of notification checking and class sign-ins.
        This is typically called by manual UI triggers.
        """
        print(f"\n==================================================")
        print(f"[Daemon] Starting Manual Full Cycle: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"==================================================")

        # Validate Configuration
        errors = Config.validate()
        if errors:
            print("[Daemon] Configuration validation failed:")
            for err in errors:
                print(f"  - {err}")
            return False

        self.run_notifications(force_ui_test=force_ui_test)
        self.run_sis_check(force_sis_check=force_sis_check)

        print(f"==================================================")
        print(f"[Success] Manual Cycle completed successfully!")
        print(f"==================================================\n")
        return True

    def run_notifications(self, force_ui_test: bool = False) -> bool:
        print("\n--- [Daemon - Notification] Digital BFSU & BB Notification Check ---")
        
        # Log in to CAS (will trigger 2FA dialog if device is un-bound)
        login_success = self.cas_client.login(sms_code_callback=request_sms_code)
        
        if login_success:
            # 1. Digital BFSU
            if getattr(Config, 'ENABLE_PORTAL_CHECK', True):
                history_ids = HistoryManager.load_history_ids()
                notices = self.portal_scraper.fetch_notices()
                print(f"[Daemon - Notification] Fetched {len(notices)} notices.")

                threshold_date = datetime.date.today() - datetime.timedelta(days=1)
                threshold_str = threshold_date.strftime("%Y-%m-%d")

                new_notices_count = 0
                for notice in notices:
                    notice_id = notice['id']
                    notice_date = notice['date_str']

                    if notice_date < threshold_str:
                        continue

                    if force_ui_test or notice_id not in history_ids:
                        print(f"[Daemon - Notification] Found new notice: {notice['title']}")
                        content = self.portal_scraper.fetch_notice_detail(notice['url'])
                        analysis = self.summarizer.summarize(notice['title'], content)
                        print(f"[Daemon - Notification] AI Summary Analysis: {analysis}")

                        show_notification(
                            title=notice['title'],
                            publisher=notice['publisher'],
                            date_str=notice['date_str'],
                            url=notice['url'],
                            summary=analysis.get('summary', ''),
                            category=analysis.get('category', '学校通知'),
                            relevance=analysis.get('relevance_score', -1),
                            relevance_summary=analysis.get('relevance_summary', ''),
                            source="数字北外",
                            notice_id=notice_id
                        )

                        HistoryManager.add_to_history_cache({
                            'id': notice_id,
                            'title': notice['title'],
                            'publisher': notice['publisher'],
                            'date_str': notice['date_str'],
                            'url': notice['url'],
                            'summary': analysis.get('summary', ''),
                            'category': analysis.get('category', '学校通知'),
                            'relevance': analysis.get('relevance_score', -1),
                            'relevance_summary': analysis.get('relevance_summary', ''),
                            'source': "数字北外",
                            'acknowledged': False
                        })
                        new_notices_count += 1

                if new_notices_count == 0:
                    print("[Daemon - Notification] No new notifications since last check.")

            # 2. Blackboard
            if getattr(Config, 'ENABLE_BB_CHECK', True):
                print("[Daemon - Notification] Querying Blackboard platform for course updates...")
                try:
                    from ..bb.client import BBClient
                    bb_client = BBClient(self.cas_client)
                    if bb_client.login():
                        bb_notices = bb_client.fetch_alerts()
                        print(f"[Daemon - Notification] Fetched {len(bb_notices)} Blackboard alerts.")
                        
                        history_ids = HistoryManager.load_history_ids() # reload
                        new_bb_count = 0
                        for notice in bb_notices:
                            notice_id = notice['id']
                            notice_date = notice['date_str']
                            
                            if notice_date < threshold_str:
                                continue
                                
                            if force_ui_test or notice_id not in history_ids:
                                print(f"[Daemon - Notification] Found new Blackboard alert: {notice['title']} in {notice['publisher']}")
                                
                                show_notification(
                                    title=notice['title'],
                                    publisher=notice['publisher'],
                                    date_str=notice['date_str'],
                                    url=notice['url'],
                                    summary=notice['summary'],
                                    category=notice['category'],
                                    relevance=notice['relevance'],
                                    relevance_summary=notice['relevance_summary'],
                                    source="BB",
                                    notice_id=notice_id
                                )
                                
                                HistoryManager.add_to_history_cache({
                                    'id': notice_id,
                                    'title': notice['title'],
                                    'publisher': notice['publisher'],
                                    'date_str': notice['date_str'],
                                    'url': notice['url'],
                                    'summary': notice['summary'],
                                    'category': notice['category'],
                                    'relevance': notice['relevance'],
                                    'relevance_summary': notice['relevance_summary'],
                                    'source': "BB",
                                    'acknowledged': False
                                })
                                new_bb_count += 1
                                
                        if new_bb_count == 0:
                            print("[Daemon - Notification] No new Blackboard notifications since last check.")
                    else:
                        print("[Daemon - Notification] Blackboard SSO login failed.")
                except Exception as e:
                    print(f"[Daemon - Notification] Unexpected error in Blackboard check: {e}")

            # 3. CS Website Assignments
            if getattr(Config, 'ENABLE_CS_CHECK', False):
                print("[Daemon - Notification] Querying CS Website for course homework...")
                try:
                    from ..cs.client import CSClient
                    cs_client = CSClient(self.cas_client)
                    if cs_client.login():
                        cs_hw_list = cs_client.fetch_homework()
                        print(f"[Daemon - Notification] Fetched {len(cs_hw_list)} CS homework records.")
                        
                        history_ids = HistoryManager.load_history_ids() # reload
                        new_cs_count = 0
                        for hw in cs_hw_list:
                            hw_id = hw['id']
                            
                            # Filter out already submitted homeworks
                            if hw.get('status', '') == "已上交":
                                continue
                                
                            if force_ui_test or hw_id not in history_ids:
                                print(f"[Daemon - Notification] Found new CS homework: {hw['title']}")
                                
                                show_notification(
                                    title=hw['title'],
                                    publisher=hw['publisher'],
                                    date_str=hw['date_str'],
                                    url=hw['url'],
                                    summary=hw['summary'],
                                    category=hw['category'],
                                    relevance=hw['relevance'],
                                    relevance_summary=hw['relevance_summary'],
                                    source="计算机系",
                                    notice_id=hw_id
                                )
                                
                                HistoryManager.add_to_history_cache({
                                    'id': hw_id,
                                    'title': hw['title'],
                                    'publisher': hw['publisher'],
                                    'date_str': hw['date_str'],
                                    'url': hw['url'],
                                    'summary': hw['summary'],
                                    'category': hw['category'],
                                    'relevance': hw['relevance'],
                                    'relevance_summary': hw['relevance_summary'],
                                    'source': "计算机系",
                                    'acknowledged': False
                                })
                                new_cs_count += 1
                                
                        if new_cs_count == 0:
                            print("[Daemon - Notification] No new or unsubmitted CS homework since last check.")
                    else:
                        print("[Daemon - Notification] CS Website login failed.")
                except Exception as e:
                    print(f"[Daemon - Notification] Unexpected error in CS Website check: {e}")
        else:
            print("[Daemon - Notification] Skipped notification checking due to CAS login failure.")
            return False
        return True

    def run_sis_check(self, force_sis_check: bool = False) -> bool:
        if not getattr(Config, "ENABLE_SIS_CHECK", True):
            print("[Daemon - SIS] SIS Check is globally disabled via settings. Skipping.")
            return True
        print("\n--- [Daemon - SIS] SIS Course Sign-In Check ---")
        
        should_check_sis = force_sis_check
        matched_slot = None
        
        if not should_check_sis:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            for slot_str in Config.SIS_SIGNIN_TIMES:
                try:
                    hour, minute = map(int, slot_str.split(":"))
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    window_start = target_time - datetime.timedelta(minutes=10)
                    window_end = target_time + datetime.timedelta(minutes=30)
                    
                    if window_start <= now <= window_end:
                        check_key = f"{today_str}_{slot_str}"
                        if check_key not in self.completed_sis_slots:
                            should_check_sis = True
                            matched_slot = slot_str
                            break
                except Exception as e:
                    print(f"[Daemon - SIS] Error parsing SIS slot '{slot_str}': {e}")
        
        if should_check_sis:
            if matched_slot:
                print(f"[Daemon - SIS] Triggering scheduled SIS check for slot [{matched_slot}]...")
            else:
                print("[Daemon - SIS] Triggering manual/forced SIS check...")
                
            sis_login_success = self.sis_client.login()
            if sis_login_success:
                jitter_sec = random.randint(5, 30)
                print(f"[Daemon - SIS] Simulating human behavior. Waiting {jitter_sec} seconds before sign-in checks...")
                time.sleep(jitter_sec)
                
                signed_results = self.sis_client.auto_signin_all_courses()
                if signed_results:
                    print(f"[Daemon - SIS] Processed active sign-in tasks: {signed_results}")
                    for i, res in enumerate(signed_results):
                        course_name = res["course_name"]
                        status = res["status"]
                        reason = res["reason"]
                        
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                        
                        title = f"课程签到成功: {course_name}" if status == "success" else f"课程签到失败: {course_name}"
                        summary = f"我们在 {now_str} 自动为您执行了信科学院网站的课程签到操作。结果：{reason}。"
                        
                        event_id = f"sis_signin_{course_name}_{int(time.time())}_{i}"
                        
                        show_notification(
                            title=title,
                            publisher="信科网站签到",
                            date_str=today_str,
                            url="https://cs.bfsu.edu.cn",
                            summary=summary,
                            category="课堂签到",
                            relevance=95 if status == "success" else 99,
                            relevance_summary=f"签到状态: {'成功' if status == 'success' else '失败'} - {reason}",
                            source="信科网站签到",
                            notice_id=event_id
                        )
                        
                        HistoryManager.add_to_history_cache({
                            'id': event_id,
                            'title': title,
                            'publisher': "信科网站签到",
                            'date_str': today_str,
                            'url': "https://cs.bfsu.edu.cn",
                            'summary': summary,
                            'category': "课堂签到",
                            'relevance': 95 if status == "success" else 99,
                            'relevance_summary': f"签到状态: {'成功' if status == 'success' else '失败'} - {reason}",
                            'source': "信科网站签到",
                            'acknowledged': False
                        })
                        
                    if matched_slot:
                        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                        self.completed_sis_slots.add(f"{today_str}_{matched_slot}")
                        print(f"[Daemon - SIS] Slot [{matched_slot}] marked as successfully completed.")
                else:
                    print("[Daemon - SIS] No active sign-in tasks found/processed. Will retry in this window if time permits.")
            else:
                print("[Daemon - SIS] Skipped course sign-in due to SIS login failure.")
        else:
            print(f"[Daemon - SIS] Skipping SIS check (not in any scheduled class slots: {Config.SIS_SIGNIN_TIMES_RAW}, or already checked today).")
        return True

    def start_infinite_loop(self):
        """
        Starts a resident daemon process that polls periodically using decoupled tracking for Notifications and SIS.
        """
        print(f"[Daemon] Daemon started. Decoupled polling for Notifications and SIS.")
        print("[Daemon] To exit, click the system tray icon or press Ctrl+C in terminal.")
        
        now = datetime.datetime.now()
        # Trigger both immediately on the very first daemon boot
        next_notification_time = now 
        
        # Re-trigger unacknowledged notifications within the last 48 hours upon startup
        try:
            cache = HistoryManager.load_history_cache()
            unacknowledged = [item for item in cache if item.get('acknowledged') is False]
            if unacknowledged:
                today = datetime.date.today()
                threshold = today - datetime.timedelta(days=2)
                unacknowledged_recent = []
                for item in unacknowledged:
                    try:
                        date_parts = list(map(int, item.get('date_str', '').split('-')))
                        if len(date_parts) == 3:
                            item_date = datetime.date(date_parts[0], date_parts[1], date_parts[2])
                            if item_date >= threshold:
                                unacknowledged_recent.append(item)
                    except Exception:
                        unacknowledged_recent.append(item)
                
                if unacknowledged_recent:
                    print(f"[Daemon] Found {len(unacknowledged_recent)} unacknowledged recent notifications. Re-triggering reminders...")
                    for item in unacknowledged_recent:
                        show_notification(
                            title=item.get('title', '无标题通知'),
                            publisher=item.get('publisher', '未知来源'),
                            date_str=item.get('date_str', ''),
                            url=item.get('url', ''),
                            summary=item.get('summary', ''),
                            category=item.get('category', ''),
                            relevance=item.get('relevance', -1),
                            relevance_summary=item.get('relevance_summary', ''),
                            source=item.get('source', '数字北外'),
                            notice_id=item.get('id', '')
                        )
        except Exception as e:
            print(f"[Daemon] Error re-triggering unacknowledged notifications on startup: {e}") 
        
        while not self.stop_event.is_set():
            now = datetime.datetime.now()
            
            # --- 1. Notification Check ---
            if now >= next_notification_time:
                try:
                    # Only validate once per cycle to avoid spamming
                    if not Config.validate():
                        self.run_notifications()
                except Exception as e:
                    print(f"[Daemon] Unexpected error in notification loop: {e}")
                
                # Reschedule
                next_notification_time = datetime.datetime.now() + datetime.timedelta(minutes=Config.NOTIFICATION_INTERVAL)
            
            # --- 2. SIS Check ---
            # We don't need a single 'next_sis_time' because SIS windows are fixed time ranges. 
            # We just check if we are in a window right now, and if so, run it.
            should_run_sis = False
            today_str = now.strftime("%Y-%m-%d")
            for slot_str in Config.SIS_SIGNIN_TIMES:
                try:
                    hour, minute = map(int, slot_str.split(":"))
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    window_start = target_time - datetime.timedelta(minutes=10)
                    window_end = target_time + datetime.timedelta(minutes=30)
                    
                    check_key = f"{today_str}_{slot_str}"
                    if check_key in self.completed_sis_slots:
                        continue
                        
                    if window_start <= now <= window_end:
                        should_run_sis = True
                        break
                except Exception:
                    pass
                    
            if should_run_sis:
                try:
                    if not Config.validate():
                        self.run_sis_check()
                except Exception as e:
                    print(f"[Daemon] Unexpected error in SIS check loop: {e}")

            # --- 3. Calculate dynamic sleep time ---
            now = datetime.datetime.now()
            
            # Sleep until next notification run
            sleep_seconds = (next_notification_time - now).total_seconds()
            
            # Re-evaluate SIS to see if a window is approaching or active
            in_sis_window = False
            for slot_str in Config.SIS_SIGNIN_TIMES:
                try:
                    hour, minute = map(int, slot_str.split(":"))
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    window_start = target_time - datetime.timedelta(minutes=10)
                    window_end = target_time + datetime.timedelta(minutes=30)
                    
                    check_key = f"{today_str}_{slot_str}"
                    if check_key in self.completed_sis_slots:
                        continue
                        
                    if now < window_start:
                        time_to_window = (window_start - now).total_seconds()
                        if time_to_window < sleep_seconds:
                            sleep_seconds = time_to_window
                    elif window_start <= now <= window_end:
                        in_sis_window = True
                except Exception:
                    pass
                    
            if in_sis_window:
                # If we are in the window, we should sleep for SIS_CHECK_INTERVAL instead
                sis_interval_sec = Config.SIS_CHECK_INTERVAL * 60
                if sis_interval_sec < sleep_seconds:
                    sleep_seconds = sis_interval_sec
                    
            # Safety clamp: min 10 seconds, max NOTIFICATION_INTERVAL
            sleep_seconds = max(10, min(sleep_seconds, Config.NOTIFICATION_INTERVAL * 60))
            
            if self.stop_event.is_set():
                break

            print(f"[Daemon] Sleeping for {int(sleep_seconds)} seconds...")
            woken_up = self.check_event.wait(timeout=sleep_seconds)
            
            if woken_up:
                print("[Daemon] Woken up on-demand!")
                self.check_event.clear()
                # On manual wake up via UI, usually run_once is called separately, so this just interrupts sleep.
