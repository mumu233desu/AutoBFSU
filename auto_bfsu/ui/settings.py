import os
import sys
import customtkinter as ctk
from ..config import Config
from ..auth.crypto import encrypt_password, decrypt_password
from .theme import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_LIGHT, COLOR_ACCENT, COLOR_ACCENT_HOVER, get_font
)
from .core import get_root_coordinator, run_on_main_thread

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        
        self.title("助手参数配置中心")
        self.geometry("660x720")
        self.resizable(False, False)
        
        # Position in center of screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        w, h = 700, 680
        x = (screen_width - w) // 2
        y = (screen_height - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.configure(fg_color=COLOR_BG)
        
        # Make it modal/grab focus
        self.transient(master)
        self.grab_set()
        
        # Header Title
        title_lbl = ctk.CTkLabel(
            self,
            text="⚙️ 助手参数配置中心",
            font=get_font(size=22, weight="bold"),
            anchor="w"
        )
        title_lbl.pack(fill="x", padx=25, pady=(20, 10))
        
        # --- Developer Mode Easter Egg ---
        self.dev_click_count = 0
        def on_title_click(event):
            from ..config import Config
            if getattr(Config, 'DEVELOPER_MODE', False):
                return
            self.dev_click_count += 1
            if self.dev_click_count >= 5:
                Config.DEVELOPER_MODE = True
                self._show_msgbox("彩蛋", "已进入开发者模式！隐藏的特殊教务功能已解锁。", is_error=False)
                self.chk_sis.grid()
                self.sis_frame.pack(fill="x")
                
                try:
                    from .tray import update_tray_menu
                    update_tray_menu()
                except Exception as e:
                    print(f"[Settings] Failed to update tray menu on unlock: {e}")
                
        title_lbl.bind("<Button-1>", on_title_click)
        # ---------------------------------
        
        # ------------------ BOTTOM BAR: SAVE/CANCEL ------------------
        # Pack this first with side="bottom" so it is fixed and doesn't jump
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=25, pady=(0, 20))
        
        # Cancel Button
        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text="取消",
            width=100,
            height=32,
            font=get_font(size=13, weight="bold"),
            fg_color=COLOR_CARD,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_LIGHT,
            command=self.destroy
        )
        self.cancel_btn.pack(side="left")
        
        # Save Button
        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="💾 保存并应用设置",
            width=160,
            height=32,
            font=get_font(size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            command=self._save_settings
        )
        self.save_btn.pack(side="right")

        # CTkTabview for categorized configuration
        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            segmented_button_unselected_color=COLOR_CARD,
            segmented_button_unselected_hover_color=COLOR_BORDER,
            fg_color=COLOR_CARD,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.tabview.pack(fill="both", expand=True, padx=25, pady=(0, 20))
        
        # Add Tabs (with spaces for wider appearance)
        self.tab_auth = self.tabview.add("   🔐 账号凭证   ")
        self.tab_scheduler = self.tabview.add("   ⏱️ 运行参数   ")
        self.tab_ai = self.tabview.add("   🤖 AI 总结   ")
        
        # ------------------ TAB 1: 🔐 账号凭证 ------------------
        # Digital BFSU Username
        ctk.CTkLabel(self.tab_auth, text="数字北外账号 (Username):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(15, 2))
        self.ent_user = ctk.CTkEntry(self.tab_auth, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_user.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_user.insert(0, Config.USERNAME)
        
        # Digital BFSU Password
        ctk.CTkLabel(self.tab_auth, text="数字北外密码 (Password):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_pass = ctk.CTkEntry(self.tab_auth, width=380, show="*", fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_pass.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_pass.insert(0, Config.PASSWORD)
        
        # SIS Student ID
        ctk.CTkLabel(self.tab_auth, text="信科学院学号 (Student ID):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_sis_user = ctk.CTkEntry(self.tab_auth, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_sis_user.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_sis_user.insert(0, Config.STUDENT_ID)
        
        # SIS Password
        ctk.CTkLabel(self.tab_auth, text="信科平台密码 (SIS Password - 留空默认与数字北外相同):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_sis_pass = ctk.CTkEntry(self.tab_auth, width=380, show="*", fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_sis_pass.pack(anchor="w", padx=20, pady=(0, 20))
        
        # Load raw/decrypted SIS password, but only if it's explicitly different from normal password
        if os.getenv("SIS_PASSWORD"):
            self.ent_sis_pass.insert(0, Config.SIS_PASSWORD)
            
        # ------------------ TAB 2: ⏱️ 运行参数 ------------------
        # Module Switches Container (2x2 Grid)
        self.switches_frame = ctk.CTkFrame(self.tab_scheduler, fg_color="transparent")
        self.switches_frame.pack(fill="x", padx=20, pady=(15, 10))

        self.chk_portal = ctk.CTkCheckBox(self.switches_frame, text="开启数字北外 (Portal) 通知拉取", font=get_font(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.chk_portal.grid(row=0, column=0, padx=(0, 20), pady=(0, 10), sticky="w")
        if getattr(Config, 'ENABLE_PORTAL_CHECK', True):
            self.chk_portal.select()

        self.chk_bb = ctk.CTkCheckBox(self.switches_frame, text="开启教学平台 Blackboard (BB) 课程警报", font=get_font(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.chk_bb.grid(row=0, column=1, pady=(0, 10), sticky="w")
        if getattr(Config, 'ENABLE_BB_CHECK', True):
            self.chk_bb.select()
            
        self.chk_cs = ctk.CTkCheckBox(self.switches_frame, text="开启计算机系 (CS) 网站课程作业雷达", font=get_font(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.chk_cs.grid(row=1, column=0, padx=(0, 20), sticky="w")
        if getattr(Config, 'ENABLE_CS_CHECK', True):
            self.chk_cs.select()
            
        self.chk_sis = ctk.CTkCheckBox(self.switches_frame, text="开启计算机系 (CS) 网站自动课堂签到", font=get_font(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.chk_sis.grid(row=1, column=1, sticky="w")
        if getattr(Config, 'ENABLE_SIS_CHECK', True):
            self.chk_sis.select()
            
        # Background Polling Interval
        ctk.CTkLabel(self.tab_scheduler, text="通知公告轮询检测间隔 (分钟，不得少于 10 分钟):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 2))
        self.ent_interval = ctk.CTkEntry(self.tab_scheduler, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_interval.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_interval.insert(0, str(Config.NOTIFICATION_INTERVAL))
        
        # SIS Frame (Developer Mode Only)
        self.sis_frame = ctk.CTkFrame(self.tab_scheduler, fg_color="transparent")
        
        ctk.CTkLabel(self.sis_frame, text="信科平台定时自动签到时段 (上课时间段，英文逗号分隔):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(10, 2))
        self.ent_sis_times = ctk.CTkEntry(self.sis_frame, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_sis_times.pack(anchor="w", padx=20, pady=(0, 15))
        self.ent_sis_times.insert(0, getattr(Config, 'SIS_SIGNIN_TIMES_RAW', '08:00,10:00,14:00,16:00,18:00'))

        ctk.CTkLabel(self.sis_frame, text="签到窗口探测间隔 (分钟，上课时生效，建议 5 分钟):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_sis_interval = ctk.CTkEntry(self.sis_frame, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_sis_interval.pack(anchor="w", padx=20, pady=(0, 15))
        self.ent_sis_interval.insert(0, str(getattr(Config, 'SIS_CHECK_INTERVAL', 5)))
        
        self.tips_frame = ctk.CTkFrame(self.sis_frame, fg_color=COLOR_BG, border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        self.tips_frame.pack(fill="x", padx=20, pady=(10, 15))
        tips_lbl = ctk.CTkLabel(
            self.tips_frame,
            text="💡 提示: 为防错过，系统会在设定的签到时间「提前10分钟」进入自动打卡窗口期。\n建议直接配置为实际的上课标准时间（如: 08:00, 10:00, 14:00）。",
            font=get_font(size=12),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left",
            anchor="w"
        )
        tips_lbl.pack(padx=12, pady=10)
        
        if getattr(Config, 'DEVELOPER_MODE', False):
            self.sis_frame.pack(fill="x")
        else:
            self.chk_sis.grid_remove()
        
        # ------------------ TAB 3: 🤖 AI 总结 ------------------
        # LLM API Key
        ctk.CTkLabel(self.tab_ai, text="LLM API Key (大模型授权密钥 - 选填):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(15, 2))
        self.ent_llm_key = ctk.CTkEntry(self.tab_ai, width=380, show="*", fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_llm_key.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_llm_key.insert(0, Config.LLM_API_KEY)
        
        # LLM Base URL
        ctk.CTkLabel(self.tab_ai, text="LLM API 请求端点 (Base URL):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_llm_base = ctk.CTkEntry(self.tab_ai, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_llm_base.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_llm_base.insert(0, Config.LLM_BASE_URL)
        
        # LLM Model Name
        ctk.CTkLabel(self.tab_ai, text="模型名称 (Model):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_llm_model = ctk.CTkEntry(self.tab_ai, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_llm_model.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_llm_model.insert(0, Config.LLM_MODEL)
        
        # Notification Relevance Keywords
        ctk.CTkLabel(self.tab_ai, text="个人高关注相关度过滤关键字 (英文逗号分隔):", font=get_font(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(5, 2))
        self.ent_keywords = ctk.CTkEntry(self.tab_ai, width=380, fg_color=COLOR_BG, border_color=COLOR_BORDER, text_color=COLOR_TEXT_LIGHT)
        self.ent_keywords.pack(anchor="w", padx=20, pady=(0, 15))
        self.ent_keywords.insert(0, Config.KEYWORDS_RAW)
        
        # (Bottom bar moved to top for fixed layout)
        
    def _save_settings(self):
        # 1. Fetch input values
        username = self.ent_user.get().strip()
        password = self.ent_pass.get().strip()
        student_id = self.ent_sis_user.get().strip()
        sis_password = self.ent_sis_pass.get().strip()
        enable_portal = self.chk_portal.get() == 1
        enable_bb = self.chk_bb.get() == 1
        enable_cs = self.chk_cs.get() == 1
        enable_sis = self.chk_sis.get() == 1
        
        sis_times = self.ent_sis_times.get().strip()
        interval_val = self.ent_interval.get().strip()
        sis_interval_val = self.ent_sis_interval.get().strip()
        
        llm_key = self.ent_llm_key.get().strip()
        llm_base = self.ent_llm_base.get().strip()
        llm_model = self.ent_llm_model.get().strip()
        keywords = self.ent_keywords.get().strip()
        
        # Validate critical items
        if not username or not password:
            self._show_msgbox("错误", "统一身份认证账号与密码不能为空！", is_error=True)
            return
        if not student_id:
            student_id = "YOUR_STUDENT_ID_HERE"
            
        # Validate background polling interval (must be >= 10)
        try:
            interval_int = int(interval_val)
            if interval_int < 10:
                raise ValueError()
        except Exception:
            self._show_msgbox("错误", "通知公告轮询检测间隔必须为大于等于 10 的整数（单位：分钟）！", is_error=True)
            return
            
        # Validate SIS check interval (must be >= 1)
        try:
            sis_interval_int = int(sis_interval_val)
            if sis_interval_int < 1:
                raise ValueError()
        except Exception:
            self._show_msgbox("错误", "签到窗口探测间隔必须为大于等于 1 的整数（单位：分钟）！", is_error=True)
            return
            
        # 2. Encrypt sensitive credentials (including usernames and API keys)
        enc_username = encrypt_password(username)
        enc_password = encrypt_password(password)
        enc_student_id = encrypt_password(student_id)
        enc_sis_password = encrypt_password(sis_password) if sis_password else ""
        enc_llm_key = encrypt_password(llm_key) if llm_key else ""
        
        # 3. Build .env content lines
        lines = [
            "# ====================================================================",
            "# AutoBFSU 本地安全配置文件 (通过参数设置窗口自动生成)",
            "# ====================================================================",
            "",
            "# 1. 统一身份认证登录凭证",
            f"BFSU_USERNAME={enc_username}",
            f"BFSU_PASSWORD={enc_password}",
            "",
            "# 2. 信科学院教学平台登录凭证",
            f"BFSU_STUDENT_ID={enc_student_id}",
            f"SIS_PASSWORD={enc_sis_password}",
            f"SIS_SIGNIN_TIMES={sis_times}",
            f"NOTIFICATION_INTERVAL={interval_int}",
            f"SIS_CHECK_INTERVAL={sis_interval_int}",
            "",
            "# 3. LLM AI 通知总结服务配置",
            f"LLM_API_KEY={enc_llm_key}",
            f"LLM_BASE_URL={llm_base}",
            f"LLM_MODEL={llm_model}",
            f"NOTIFICATION_KEYWORDS={keywords}",
            "",
            "# 4. 功能模块推送开关",
            f"ENABLE_PORTAL_CHECK={'True' if enable_portal else 'False'}",
            f"ENABLE_BB_CHECK={'True' if enable_bb else 'False'}",
            f"ENABLE_CS_CHECK={'True' if enable_cs else 'False'}",
            ""
        ]
        
        from ..config import Config
        if getattr(Config, 'DEVELOPER_MODE', False):
            lines.insert(lines.index("# 4. 功能模块推送开关"), f"DEVELOPER_MODE=True")
            lines.insert(lines.index("# 4. 功能模块推送开关"), f"ENABLE_SIS_CHECK={'True' if enable_sis else 'False'}")
            lines.insert(lines.index("# 4. 功能模块推送开关"), f"SIS_SIGNIN_TIMES={sis_times}")
            lines.insert(lines.index("# 4. 功能模块推送开关"), f"SIS_CHECK_INTERVAL={sis_interval_int}")
        else:
            # Clean up default lines that might have them
            lines = [l for l in lines if not l.startswith("SIS_SIGNIN_TIMES=") and not l.startswith("SIS_CHECK_INTERVAL=")]
        
        # Write to .env
        path = Config.BASE_DIR / ".env"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print("[Settings] Config saved to .env successfully.")
        except Exception as e:
            self._show_msgbox("保存失败", f"写入 .env 配置文件失败: {e}", is_error=True)
            return
            
        # 4. Instantly reload config into the active memory (Dynamic hot-reload!)
        try:
            from dotenv import load_dotenv
            load_dotenv(path, override=True)
            
            Config.USERNAME_RAW = enc_username
            Config.USERNAME = username
            Config.PASSWORD_RAW = enc_password
            Config.PASSWORD = password
            Config.STUDENT_ID_RAW = enc_student_id
            Config.STUDENT_ID = student_id
            Config.SIS_PASSWORD_RAW = enc_sis_password
            Config.SIS_PASSWORD = sis_password or password
            
            Config.LLM_API_KEY_RAW = enc_llm_key
            Config.LLM_API_KEY = llm_key
            Config.LLM_BASE_URL = llm_base
            Config.LLM_MODEL = llm_model
            Config.KEYWORDS_RAW = keywords
            Config.KEYWORDS = [k.strip() for k in keywords.split(",") if k.strip()]
            Config.SIS_SIGNIN_TIMES_RAW = sis_times
            Config.SIS_SIGNIN_TIMES = [t.strip() for t in sis_times.split(",") if t.strip()]
            
            Config.ENABLE_PORTAL_CHECK = enable_portal
            Config.ENABLE_BB_CHECK = enable_bb
            Config.ENABLE_CS_CHECK = enable_cs
            Config.ENABLE_SIS_CHECK = enable_sis if getattr(Config, 'DEVELOPER_MODE', False) else False
            
            Config.NOTIFICATION_INTERVAL = interval_int
            Config.SIS_CHECK_INTERVAL = sis_interval_int
            
            print("[Settings] Running Config dynamically reloaded.")
        except Exception as e:
            print(f"[Settings] Error hot-reloading Config: {e}")
            
        # 5. Success feedback and close window
        self._show_msgbox("保存成功", "参数配置已成功保存！\n密码已通过 Windows DPAPI 硬件级深度安全加密。\n\n配置已在后台静默即时生效，无需重启软件。", is_error=False)
        self.grab_release()
        self.destroy()
        
    def _show_msgbox(self, title: str, text: str, is_error: bool = False):
        """Pop up a native thread-safe messagebox while safely suspending Tkinter grabs to prevent click lockouts."""
        has_grab = False
        try:
            # Detect if this window currently grabs all events
            # grab_status() returns "local", "global", or None
            if self.grab_status():
                self.grab_release()
                has_grab = True
        except Exception:
            pass

        if sys.platform.startswith("win"):
            import ctypes
            icon_flag = 0x10 if is_error else 0x40 # MB_ICONERROR vs MB_ICONINFORMATION
            
            # Try to get the window handle to parent the messagebox properly
            hwnd = 0
            try:
                # CTkToplevel winfo_id() usually gives the HWND on Windows
                hwnd = self.winfo_id()
            except Exception:
                pass
                
            ctypes.windll.user32.MessageBoxW(hwnd, text, title, icon_flag)
        else:
            # Non-Windows fallback using tkinter.messagebox
            from tkinter import messagebox
            if is_error:
                messagebox.showerror(title, text)
            else:
                messagebox.showinfo(title, text)

        # Restore the event grab if it was active before the pop-up
        if has_grab:
            try:
                if self.winfo_exists():
                    self.grab_set()
            except Exception:
                pass


def show_settings_window():
    """Post a request to spawn the settings configuration window on the main thread."""
    import os
    if os.environ.get("AUTO_BFSU_NO_POPUP") == "1":
        print("[Settings] [AUTO_BFSU_NO_POPUP=1] Suppressing GUI settings window.")
        return

    root = get_root_coordinator()
    if root:
        run_on_main_thread(_spawn_settings_window_main)
    else:
        print("[Settings] GUI loop not running, running standalone Settings Window...")
        standalone_root = ctk.CTk()
        standalone_root.withdraw()
        _spawn_settings_window_main(master=standalone_root)
        standalone_root.mainloop()

def _spawn_settings_window_main(master=None):
    parent = master if master is not None else get_root_coordinator()
    window = SettingsWindow(parent)
