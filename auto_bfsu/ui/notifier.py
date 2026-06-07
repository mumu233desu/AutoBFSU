import webbrowser
import customtkinter as ctk
from .theme import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_LIGHT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_BLUE, COLOR_RED, COLOR_ORANGE, get_font
)
from .core import gui_queue, get_root_coordinator, run_on_main_thread

class NotificationPopup(ctk.CTkToplevel):
    def __init__(self, master, title: str, publisher: str, date_str: str, url: str, summary: str = "", category: str = "", relevance: int = -1, relevance_summary: str = "", source: str = "数字北外", notice_id: str = None):
        super().__init__(master)
        self.notice_id = notice_id

        # Window settings
        self.title(f"{source}通知")
        self.geometry("500x390")
        self.resizable(False, False)
        self.overrideredirect(True)  # Remove title bar for a modern look
        self.attributes("-topmost", True)  # Always on top
        
        # Configure window background to exactly match frame, eliminating the gray border gap!
        self.configure(fg_color=COLOR_BG)

        # Set initial size. Invisible due to alpha=0.0
        window_width = 500
        window_height = 390
        self.geometry(f"{window_width}x{window_height}")
        
        # Initialize dragging state variables
        self._drag_start_x_root = 0
        self._drag_start_y_root = 0

        self.url = url
        self.relevance = relevance
        self.fade_steps = 10
        self.current_alpha = 0.0
        
        # Init opacity
        self.attributes("-alpha", self.current_alpha)

        # Build UI
        self._build_ui(title, publisher, date_str, summary, category, relevance_summary, source)

        # Start fade-in animation
        self._fade_in()

        # Position window in bottom-right corner.
        # All geometry computations are done in LOGICAL pixels, then converted to PHYSICAL
        # for wm_geometry, which (unlike CTk's .geometry()) uses physical pixel coordinates.
        self.update_idletasks()
        scaling = self._get_window_scaling()
        sw = self.winfo_screenwidth()   # logical pixels
        sh = self.winfo_screenheight()  # logical pixels
        WIN_W, WIN_H = 500, 390         # logical (matches our geometry() call)
        MARGIN_R, MARGIN_B = 25, 60    # logical margin from right/bottom edge
        
        x_logical = sw - WIN_W - MARGIN_R
        y_logical = sh - WIN_H - MARGIN_B
        
        # wm_geometry on Windows DPI-aware mode uses physical coordinates
        x_phys = int(x_logical * scaling)
        y_phys = int(y_logical * scaling)
        
        print(f"[Notifier] scale={scaling} screen={sw}x{sh} logical=+{x_logical}+{y_logical} physical=+{x_phys}+{y_phys}")
        self.wm_geometry(f"+{x_phys}+{y_phys}")

        # Setup mouse hover events for premium opacity transition
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)

    def _build_ui(self, title: str, publisher: str, date_str: str, summary: str, category: str, relevance_summary: str, source: str):
        # Master frame with border. Uses padx=0, pady=0 to fully cover the Toplevel and remove gap borders
        master_frame = ctk.CTkFrame(self, border_width=1, border_color=COLOR_BORDER, fg_color=COLOR_BG, corner_radius=12)
        master_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 1. Header Row
        header_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=18, pady=(15, 6))

        category_text = f"🏷️ {category}" if category else "📢 学校公告"
        category_label = ctk.CTkLabel(
            header_frame, 
            text=category_text, 
            font=get_font(size=15, weight="bold"),
            text_color=COLOR_BLUE
        )
        category_label.pack(side="left")
        
        # Bind dragging to header and empty spaces
        self._bind_drag(master_frame)
        self._bind_drag(header_frame)
        self._bind_drag(category_label)

        close_btn = ctk.CTkButton(
            header_frame, 
            text="✕", 
            width=24, 
            height=24, 
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_CARD,
            font=get_font(size=13),
            command=self._fade_out
        )
        close_btn.pack(side="right")

        # 2. Notification Title (Scrollable/Wrap)
        title_label = ctk.CTkLabel(
            master_frame, 
            text=title, 
            font=get_font(size=20, weight="bold"),
            justify="left",
            wraplength=460,
            anchor="w"
        )
        title_label.pack(fill="x", padx=18, pady=(0, 4))

        # 3. Meta Row (Publisher & Date)
        meta_text = f"🏢 {publisher}   •   📅 {date_str}   •   来源: {source}"
        meta_label = ctk.CTkLabel(
            master_frame, 
            text=meta_text, 
            font=get_font(size=14),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        meta_label.pack(fill="x", padx=18, pady=(0, 12))

        # 4. AI Summary Card (If available)
        if summary:
            # Determine card color and relevance text based on relevance score
            card_border_color = COLOR_BORDER
            relevance_level = "低"
            rel_color = COLOR_TEXT_SECONDARY  # Gray for Low
            
            if self.relevance >= 80:
                card_border_color = COLOR_RED  # High relevance = Red
                relevance_level = "高"
                rel_color = COLOR_RED
            elif self.relevance >= 40:
                card_border_color = COLOR_ORANGE  # Medium relevance = Orange
                relevance_level = "中"
                rel_color = COLOR_ORANGE
            
            summary_card = ctk.CTkFrame(
                master_frame, 
                border_width=1, 
                border_color=card_border_color, 
                fg_color=COLOR_CARD, 
                corner_radius=8
            )
            summary_card.pack(fill="both", expand=True, padx=18, pady=(0, 15))

            summary_title = "🤖 AI 智能分析" if relevance_summary else "🤖 AI 摘要智能助手"
            if self.relevance >= 0:
                summary_title += f" (🎯 相关度: {relevance_level})"

            summary_title_label = ctk.CTkLabel(
                summary_card, 
                text=summary_title, 
                font=get_font(size=14, weight="bold"),
                text_color=rel_color,
                anchor="w"
            )
            summary_title_label.pack(fill="x", padx=12, pady=(8, 3))

            summary_content = ctk.CTkLabel(
                summary_card, 
                text=f"摘要: {summary}", 
                font=get_font(size=15),
                justify="left",
                wraplength=440,
                text_color=COLOR_TEXT_LIGHT,
                anchor="nw"
            )
            summary_content.pack(fill="x", padx=12, pady=(0, 5))

            if relevance_summary:
                relevance_label = ctk.CTkLabel(
                    summary_card, 
                    text=f"分析: {relevance_summary}", 
                    font=get_font(size=14),
                    justify="left",
                    wraplength=440,
                    text_color=COLOR_TEXT_LIGHT if self.relevance >= 60 else COLOR_TEXT_MUTED,
                    anchor="nw"
                )
                relevance_label.pack(fill="x", padx=12, pady=(0, 8))

        # 5. Bottom Call to Action Button
        btn_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 15), anchor="s")

        self.ignore_btn = ctk.CTkButton(
            btn_frame, 
            text="✕ 忽略此通知", 
            width=130, 
            height=34, 
            font=get_font(size=14),
            fg_color=COLOR_CARD,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_LIGHT,
            command=self._fade_out
        )
        self.ignore_btn.pack(side="left")

        self.details_btn = ctk.CTkButton(
            btn_frame, 
            text="🌐 查看通知详情", 
            width=160, 
            height=34, 
            font=get_font(size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            command=self._open_url
        )
        self.details_btn.pack(side="right")

    def _open_url(self):
        if self.url:
            webbrowser.open(self.url)
        self._fade_out()

    def _fade_in(self):
        if self.current_alpha < 0.95:
            self.current_alpha += 0.1
            self.attributes("-alpha", self.current_alpha)
            self.after(30, self._fade_in)

    def _fade_out(self):
        if not getattr(self, "fade_out_started", False):
            self.fade_out_started = True
            # Mark as acknowledged when explicitly dismissed by user interaction
            if self.notice_id:
                from ..portal.scraper import PortalScraper
                try:
                    scraper = PortalScraper(None)
                    scraper.mark_notice_acknowledged(self.notice_id)
                    print(f"[Notifier] Notification {self.notice_id} marked as acknowledged.")
                except Exception as e:
                    print(f"[Notifier] Error marking acknowledged for {self.notice_id}: {e}")

        if self.current_alpha > 0.0:
            self.current_alpha -= 0.1
            self.attributes("-alpha", self.current_alpha)
            self.after(20, self._fade_out)
        else:
            self.destroy()

    def _on_hover(self, event):
        self.attributes("-alpha", 1.0)  # Make fully solid on hover

    def _on_leave(self, event):
        self.attributes("-alpha", 0.95)  # Return to premium 0.95 opacity
        
    def _start_move(self, event):
        self._drag_start_x_root = event.x_root
        self._drag_start_y_root = event.y_root

    def _do_move(self, event):
        dx = event.x_root - self._drag_start_x_root
        dy = event.y_root - self._drag_start_y_root
        
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        
        # Bypass CTk's logical scaling wrapper
        self.wm_geometry(f"+{new_x}+{new_y}")
        
        self._drag_start_x_root = event.x_root
        self._drag_start_y_root = event.y_root

    def _bind_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_move)
        widget.bind("<B1-Motion>", self._do_move)


def show_notification(title: str, publisher: str, date_str: str, url: str, summary: str = "", category: str = "", relevance: int = -1, relevance_summary: str = "", source: str = "数字北外", notice_id: str = None):
    """Post a notification popup request to the GUI thread-safe queue."""
    import os
    if os.environ.get("AUTO_BFSU_NO_POPUP") == "1":
        print(f"[Notifier] [AUTO_BFSU_NO_POPUP=1] Suppressing GUI popup notification.")
        print(f"  - Source: {source}")
        print(f"  - Title: {title}")
        return

    root_ref = get_root_coordinator()
    if root_ref:
        run_on_main_thread(_spawn_notification_main, title, publisher, date_str, url, summary, category, relevance, relevance_summary, source, None, notice_id)
    else:
        print("[Notifier] GUI loop not running, running standalone CTk instance...")
        standalone_root = ctk.CTk()
        standalone_root.withdraw()
        _spawn_notification_main(title, publisher, date_str, url, summary, category, relevance, relevance_summary, source, master=standalone_root, notice_id=notice_id)
        standalone_root.mainloop()

def _spawn_notification_main(title, publisher, date_str, url, summary, category, relevance, relevance_summary, source="数字北外", master=None, notice_id=None):
    parent = master if master is not None else get_root_coordinator()
    NotificationPopup(parent, title, publisher, date_str, url, summary, category, relevance, relevance_summary, source, notice_id)
