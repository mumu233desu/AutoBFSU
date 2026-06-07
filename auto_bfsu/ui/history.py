import customtkinter as ctk
import webbrowser
from .theme import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_LIGHT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_BLUE, COLOR_RED, COLOR_ORANGE, get_font
)
from .core import run_on_main_thread, get_root_coordinator

class NoticeCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=8, **kwargs)
        
        # Header (Category + Date)
        self.hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.hdr_frame.pack(fill="x", padx=12, pady=(8, 2))
        
        self.cat_lbl = ctk.CTkLabel(self.hdr_frame, text="", font=get_font(size=13, weight="bold"), text_color=COLOR_BLUE)
        self.cat_lbl.pack(side="left")
        
        self.meta_lbl = ctk.CTkLabel(self.hdr_frame, text="", font=get_font(size=13), justify="right", wraplength=550, text_color=COLOR_TEXT_SECONDARY, anchor="ne")
        self.meta_lbl.pack(side="right", fill="x", expand=True)
        
        # Title
        self.title_lbl = ctk.CTkLabel(self, text="", font=get_font(size=18, weight="bold"), justify="left", wraplength=800, anchor="w")
        self.title_lbl.pack(fill="x", padx=12, pady=(2, 6))
        
        # AI summary frame (Hidden by default)
        self.ai_frame = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=6)
        
        self.ai_lbl = ctk.CTkLabel(self.ai_frame, text="", font=get_font(size=13, weight="bold"), anchor="w")
        self.ai_lbl.pack(fill="x", padx=10, pady=(6, 2))
        
        self.sum_lbl = ctk.CTkLabel(self.ai_frame, text="", font=get_font(size=14), justify="left", wraplength=760, text_color=COLOR_TEXT_LIGHT, anchor="nw")
        self.sum_lbl.pack(fill="x", padx=10, pady=(0, 4))
        
        self.an_lbl = ctk.CTkLabel(self.ai_frame, text="", font=get_font(size=13), justify="left", wraplength=760, text_color=COLOR_TEXT_MUTED, anchor="nw")
        
        # Details button (Hidden by default)
        self.btn = ctk.CTkButton(self, text="🌐 查看详情", height=28, font=get_font(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        
    def update_data(self, item):
        # Always forget optional frames first to reset packing order
        self.ai_frame.pack_forget()
        self.btn.pack_forget()
        
        # Category & Meta
        category = item.get('category', '学校通知')
        self.cat_lbl.configure(text=f"🏷️ {category}")
        
        date_str = item.get('date_str', '')
        pub_str = item.get('publisher', '学校')
        source = item.get('source', '数字北外')
        self.meta_lbl.configure(text=f"🏢 {pub_str}  •  📅 {date_str}  •  来源: {source}")
        
        # Title
        self.title_lbl.configure(text=item.get('title', ''))
        
        # AI Summary
        summary = item.get('summary', '')
        relevance = item.get('relevance', -1)
        relevance_summary = item.get('relevance_summary', '')
        
        if summary:
            rel_level = "低"
            rel_color = COLOR_TEXT_SECONDARY
            if relevance >= 80:
                rel_level = "高"
                rel_color = COLOR_RED
            elif relevance >= 40:
                rel_level = "中"
                rel_color = COLOR_ORANGE
                
            self.ai_lbl.configure(text=f"🤖 AI 智能分析 (🎯 相关度: {rel_level})", text_color=rel_color)
            self.sum_lbl.configure(text=f"摘要: {summary}")
            
            if relevance_summary:
                self.an_lbl.configure(text=f"分析: {relevance_summary}")
                self.an_lbl.pack(fill="x", padx=10, pady=(0, 6))
            else:
                self.an_lbl.pack_forget()
                
            self.ai_frame.pack(fill="x", padx=12, pady=(0, 10))
            
        # Button
        url = item.get('url', '')
        if url:
            # Rebind command dynamically
            self.btn.configure(command=lambda u=url: webbrowser.open(u))
            self.btn.pack(padx=12, pady=(0, 10), anchor="e")

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        
        self.title("通知历史记录 - 北外智能助手")
        self.geometry("920x680")
        self.minsize(800, 550)
        
        # Position in center of screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        w, h = 920, 680
        x = (screen_width - w) // 2
        y = (screen_height - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Configure window background to match dark theme cleanly
        self.configure(fg_color=COLOR_BG)
        
        # Title Header Frame
        hdr_top_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_top_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        # Title Label
        title_lbl = ctk.CTkLabel(
            hdr_top_frame,
            text="📜 历史通知与课堂记录",
            font=get_font(size=22, weight="bold"),
            anchor="w"
        )
        title_lbl.pack(side="left")
        
        # Scrollable Frame for history list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG, border_width=1, border_color=COLOR_BORDER, corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        # Pagination Control Bar Frame
        self.page_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.page_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Previous Page Button
        self.prev_btn = ctk.CTkButton(
            self.page_frame,
            text="◀ 上一页",
            width=90,
            height=30,
            font=get_font(size=13, weight="bold"),
            fg_color=COLOR_CARD,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_LIGHT,
            command=self._prev_page
        )
        self.prev_btn.pack(side="left", padx=10)
        
        # Page Info Label
        self.info_lbl = ctk.CTkLabel(
            self.page_frame,
            text="第 1 / 1 页  (共 0 条记录)",
            font=get_font(size=14),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.info_lbl.pack(side="left", fill="x", expand=True)
        
        # Next Page Button
        self.next_btn = ctk.CTkButton(
            self.page_frame,
            text="下一页 ▶",
            width=90,
            height=30,
            font=get_font(size=13, weight="bold"),
            fg_color=COLOR_CARD,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_LIGHT,
            command=self._next_page
        )
        self.next_btn.pack(side="right", padx=10)
        
        # Page Size Menu Dropdown
        from .components import CTkStandardDropdown, CTkMultiSelectDropdown
        
        self.size_menu = CTkStandardDropdown(
            self.page_frame,
            values=["10 条/页", "20 条/页", "50 条/页", "100 条/页"],
            width=100,
            height=30,
            command=self._on_size_change
        )
        self.size_menu.set("20 条/页")
        self.size_menu.pack(side="left", padx=10)
        
        # Multi-select Importance Filter Dropdown
        self.filter_dropdown = CTkMultiSelectDropdown(
            self.page_frame,
            values=["高重要度", "中重要度", "低重要度"],
            default_values=["高重要度", "中重要度", "低重要度"],
            width=110,
            height=30,
            command=self._on_filter_change
        )
        self.filter_dropdown.pack(side="left", padx=(0, 10))
        
        # Pagination State
        self.current_page = 0
        self.items_per_page = 20
        self.raw_items = []
        self.all_items = []
        
        # Performance & Rendering State
        self.card_pool = []
        self.render_generation = 0
        self.empty_lbl = None
        
        # Load and render initial page
        self._load_items()
        self._render_page()

    def _on_size_change(self, selected_value):
        try:
            # Extract number, e.g. "20 条/页" -> 20
            new_size = int(selected_value.split(" ")[0])
            self.items_per_page = new_size
            self.current_page = 0  # Reset to page 1 to prevent out of bounds
            self._render_page()
            print(f"[HistoryWindow] Page size changed to: {new_size}")
        except Exception as e:
            print(f"[HistoryWindow] Error changing page size: {e}")

    def _on_filter_change(self, value):
        self._apply_filter()
        self.current_page = 0
        self._render_page()
        
    def _apply_filter(self):
        selected_levels = self.filter_dropdown.get()
        filtered = []
        for item in self.raw_items:
            relevance = item.get('relevance', -1)
            # Determine level
            if relevance >= 80:
                level = "高重要度"
            elif relevance >= 40:
                level = "中重要度"
            else:
                level = "低重要度"
                
            if level in selected_levels:
                filtered.append(item)
                
        self.all_items = filtered

    def _load_items(self):
        from ..utils.history import HistoryManager
        
        items = HistoryManager.load_history_cache()
                
        # Show latest first
        items.reverse()
        self.raw_items = items
        self._apply_filter()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = max(1, (len(self.all_items) + self.items_per_page - 1) // self.items_per_page)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def _render_page(self):
        self.render_generation += 1
        current_gen = self.render_generation
        
        # 1. Instantly hide existing cards to prevent blocking
        for card in self.card_pool:
            card.pack_forget()
            
        # 2. Remove empty state label if present
        if self.empty_lbl:
            self.empty_lbl.destroy()
            self.empty_lbl = None
            
        # 3. Reset scrollbar position to top
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass
            
        # 4. Calculate page slice
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.all_items[start_idx:end_idx]
        
        total_pages = max(1, (len(self.all_items) + self.items_per_page - 1) // self.items_per_page)
        
        # 5. Instantly update Pagination Buttons State and Info Label
        self.info_lbl.configure(text=f"第 {self.current_page + 1} / {total_pages} 页  (共 {len(self.all_items)} 条记录)")
        
        if self.current_page > 0:
            self.prev_btn.configure(state="normal", fg_color=COLOR_CARD)
        else:
            self.prev_btn.configure(state="disabled", fg_color=COLOR_BG)
            
        if self.current_page < total_pages - 1:
            self.next_btn.configure(state="normal", fg_color=COLOR_CARD)
        else:
            self.next_btn.configure(state="disabled", fg_color=COLOR_BG)
        
        # 6. Handle empty state
        if not page_items:
            self.empty_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="暂无历史通知消息" if not self.all_items else "本页无数据",
                font=get_font(size=15),
                text_color=COLOR_TEXT_SECONDARY
            )
            self.empty_lbl.pack(pady=50)
            return
            
        # 7. Start chunked streaming render
        self._render_chunk(current_gen, page_items, 0)
        
    def _render_chunk(self, generation, items, index):
        # Abort if user flipped page during render (Generation Lock)
        if generation != self.render_generation:
            return
            
        chunk_size = 10
        end_index = min(index + chunk_size, len(items))
        
        for i in range(index, end_index):
            item = items[i]
            
            # Reuse from pool or instantiate new
            if i < len(self.card_pool):
                card = self.card_pool[i]
            else:
                card = NoticeCard(self.scroll_frame)
                self.card_pool.append(card)
                
            card.update_data(item)
            card.pack(fill="x", padx=10, pady=8)
            
        # Yield to main loop and schedule next chunk if needed
        if end_index < len(items):
            self.after(5, lambda: self._render_chunk(generation, items, end_index))


def show_history_window():
    """Post a request to spawn the history window on the main thread."""
    import os
    if os.environ.get("AUTO_BFSU_NO_POPUP") == "1":
        print("[Notifier] [AUTO_BFSU_NO_POPUP=1] Suppressing GUI history window.")
        return

    root = get_root_coordinator()
    if root:
        run_on_main_thread(_spawn_history_window_main)
    else:
        print("[Notifier] GUI loop not running, running standalone History Window...")
        standalone_root = ctk.CTk()
        standalone_root.withdraw()
        _spawn_history_window_main(master=standalone_root)
        standalone_root.mainloop()

def _spawn_history_window_main(master=None):
    parent = master if master is not None else get_root_coordinator()
    HistoryWindow(parent)
