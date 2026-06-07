import customtkinter as ctk
import threading
from .core import gui_queue, get_root_coordinator
from .theme import COLOR_BG, COLOR_TEXT_SECONDARY, get_font

class SMSDialog(ctk.CTkToplevel):
    def __init__(self, master, mobile_number: str, evt: threading.Event, result: dict, is_standalone: bool = False):
        super().__init__(master)
        
        self.evt = evt
        self.result = result
        self.is_standalone = is_standalone

        # Configure window
        self.title("数字北外 - 统一认证二次绑定")
        self.geometry("480x280")
        self.resizable(False, False)
        
        # Bring to front
        self.attributes("-topmost", True)
        
        # Set dark theme background and remove native borders
        self.configure(fg_color=COLOR_BG)
        
        # Handle close event cleanly to prevent thread lock
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Layout UI
        self._build_ui(mobile_number)

    def _build_ui(self, mobile_number: str):
        # Master frame
        master_frame = ctk.CTkFrame(self, fg_color=COLOR_BG, border_width=0)
        master_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Title Label
        title_label = ctk.CTkLabel(
            master_frame, 
            text="🔐 统一身份认证设备绑定", 
            font=get_font(size=20, weight="bold")
        )
        title_label.pack(pady=(10, 10))

        # 2. Description Label
        desc_text = (
            f"系统检测到您的设备尚未完成短信绑定。\n"
            f"验证码已成功发送至您的手机：{mobile_number}\n"
            "请输入 6 位短信验证码，绑定后即可实现长期静默自启。"
        )
        desc_label = ctk.CTkLabel(
            master_frame, 
            text=desc_text, 
            font=get_font(size=13),
            justify="center",
            text_color=COLOR_TEXT_SECONDARY
        )
        desc_label.pack(pady=10)

        # 3. Input Frame
        input_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        input_frame.pack(pady=10)

        self.entry = ctk.CTkEntry(
            input_frame, 
            placeholder_text="输入 6 位验证码", 
            width=180,
            height=38,
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            justify="center"
        )
        self.entry.pack(side="left", padx=5)
        self.entry.focus()
        
        # Bind Enter key to submit
        self.entry.bind("<Return>", lambda event: self._on_confirm())

        # 4. Confirm Button
        confirm_btn = ctk.CTkButton(
            master_frame, 
            text="确认绑定", 
            width=140,
            height=38,
            font=get_font(size=14, weight="bold"),
            command=self._on_confirm
        )
        confirm_btn.pack(pady=(10, 10))

    def _on_confirm(self):
        code = self.entry.get().strip()
        if code:
            self.result["code"] = code
            self.destroy()
            if self.evt:
                self.evt.set()
            if self.is_standalone and self.master:
                self.master.quit()

    def _on_close(self):
        self.destroy()
        if self.evt:
            self.evt.set()
        if self.is_standalone and self.master:
            self.master.quit()


def _spawn_sms_dialog_main(mobile_number: str, evt: threading.Event, result: dict, master=None):
    root_ref = get_root_coordinator()
    parent = master if master is not None else root_ref
    is_standalone = master is not None
    dialog = SMSDialog(parent, mobile_number, evt, result, is_standalone=is_standalone)

def request_sms_code(mobile_number: str) -> str:
    """Convenience function to pop the SMS dialog and return the code, thread-safely."""
    root_ref = get_root_coordinator()
    if root_ref:
        print("[Dialog] Spawning SMS Dialog via GUI coordinator queue...")
        evt = threading.Event()
        result = {"code": ""}
        gui_queue.put((_spawn_sms_dialog_main, (mobile_number, evt, result), {}))
        # Block calling worker thread until user confirms or cancels
        evt.wait()
        return result["code"]
    else:
        print("[Dialog] GUI loop not running, running standalone CTk SMS Dialog...")
        root = ctk.CTk()
        root.withdraw()
        evt = threading.Event()
        result = {"code": ""}
        _spawn_sms_dialog_main(mobile_number, evt, result, master=root)
        root.mainloop()
        return result["code"]
