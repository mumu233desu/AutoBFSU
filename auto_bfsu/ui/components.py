import customtkinter as ctk
from .theme import (
    COLOR_BG, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_TEXT_LIGHT, COLOR_ACCENT, COLOR_ACCENT_HOVER, get_font
)

class CTkCustomDropdownBase(ctk.CTkButton):
    """Base unified button style for all custom dropdowns."""
    def __init__(self, master, width=120, height=30, **kwargs):
        btn_kwargs = {
            "width": width,
            "height": height,
            "font": get_font(size=13),
            "fg_color": COLOR_CARD,
            "hover_color": COLOR_BORDER,
            "text_color": COLOR_TEXT_LIGHT,
            "border_width": 1,
            "border_color": COLOR_BORDER,
            "anchor": "w"
        }
        btn_kwargs.update(kwargs)
        super().__init__(master, **btn_kwargs)
        
        # Unified arrow indicator
        self._arrow_lbl = ctk.CTkLabel(self, text="▼", font=get_font(size=10), text_color=COLOR_TEXT_SECONDARY)
        self._arrow_lbl.place(relx=0.88, rely=0.5, anchor="center")

    def _create_popup_window(self):
        window = ctk.CTkToplevel(self.winfo_toplevel())
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(fg_color=COLOR_BORDER)
        return window
        
    def _get_popup_position(self):
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        return x, y

    def _bind_focus_loss(self, window, close_func):
        def _check_focus_out(event):
            self.after(50, _do_close_if_focus_lost)
        def _do_close_if_focus_lost():
            if window and window.winfo_exists():
                focused = window.focus_get()
                if focused != window and (not focused or focused.winfo_toplevel() != window):
                    close_func()
        window.bind("<FocusOut>", _check_focus_out)
        window.focus_set()


class CTkMultiSelectDropdown(CTkCustomDropdownBase):
    def __init__(self, master, values, default_values=None, command=None, width=120, height=30, **kwargs):
        self.values = values
        self.selected_values = set(default_values if default_values is not None else values)
        self.command = command
        self.dropdown_window = None
        
        super().__init__(master, text=self._get_display_text(), command=self._toggle_dropdown, width=width, height=height, **kwargs)

    def _get_display_text(self):
        if len(self.selected_values) == len(self.values):
            return "全部"
        elif len(self.selected_values) == 0:
            return "无"
        else:
            return f"已选 {len(self.selected_values)} 项"

    def _toggle_dropdown(self):
        if self.dropdown_window is not None and self.dropdown_window.winfo_exists():
            self._close_dropdown()
            return

        self.dropdown_window = self._create_popup_window()
        inner_frame = ctk.CTkFrame(self.dropdown_window, fg_color=COLOR_CARD, corner_radius=4)
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        for val in self.values:
            var = ctk.BooleanVar(value=val in self.selected_values)
            chk = ctk.CTkCheckBox(
                inner_frame, 
                text=val, 
                variable=var, 
                command=lambda v=val, var=var: self._on_check(v, var),
                font=get_font(size=13),
                text_color=COLOR_TEXT_LIGHT,
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER,
                checkbox_width=20,
                checkbox_height=20
            )
            chk.pack(anchor="w", padx=12, pady=8)
            
        self.dropdown_window.update_idletasks()
        req_width = max(self.winfo_width(), inner_frame.winfo_reqwidth())
        req_height = inner_frame.winfo_reqheight() + 2
        x, y = self._get_popup_position()
        self.dropdown_window.geometry(f"{req_width}x{req_height}+{x}+{y}")
        
        self._bind_focus_loss(self.dropdown_window, self._close_dropdown)

    def _on_check(self, val, var):
        if var.get():
            self.selected_values.add(val)
        else:
            self.selected_values.discard(val)
        self.configure(text=self._get_display_text())
        if self.command:
            self.command(list(self.selected_values))
            
    def _close_dropdown(self):
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.destroy()
            self.dropdown_window = None

    def get(self):
        return list(self.selected_values)


class CTkStandardDropdown(CTkCustomDropdownBase):
    """A custom single-select dropdown unified perfectly with the multi-select dropdown style."""
    def __init__(self, master, values, command=None, width=100, height=30, **kwargs):
        self.values = values
        self.selected_value = values[0] if values else ""
        self.command = command
        self.dropdown_window = None
        
        super().__init__(master, text=self.selected_value, command=self._toggle_dropdown, width=width, height=height, **kwargs)

    def set(self, value):
        self.selected_value = value
        self.configure(text=value)

    def get(self):
        return self.selected_value

    def _toggle_dropdown(self):
        if self.dropdown_window is not None and self.dropdown_window.winfo_exists():
            self._close_dropdown()
            return

        self.dropdown_window = self._create_popup_window()
        inner_frame = ctk.CTkFrame(self.dropdown_window, fg_color=COLOR_CARD, corner_radius=4)
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        for val in self.values:
            btn = ctk.CTkButton(
                inner_frame, 
                text=val, 
                fg_color="transparent", 
                hover_color=COLOR_BORDER, 
                text_color=COLOR_TEXT_PRIMARY if val == self.selected_value else COLOR_TEXT_LIGHT,
                anchor="w", 
                font=get_font(size=13, weight="bold" if val == self.selected_value else "normal"),
                command=lambda v=val: self._on_select(v)
            )
            btn.pack(fill="x", padx=4, pady=2)
            
        self.dropdown_window.update_idletasks()
        req_width = max(self.winfo_width(), inner_frame.winfo_reqwidth())
        req_height = inner_frame.winfo_reqheight() + 2
        x, y = self._get_popup_position()
        self.dropdown_window.geometry(f"{req_width}x{req_height}+{x}+{y}")
        
        self._bind_focus_loss(self.dropdown_window, self._close_dropdown)

    def _on_select(self, val):
        self.set(val)
        if self.command:
            self.command(val)
        self._close_dropdown()

    def _close_dropdown(self):
        if self.dropdown_window and self.dropdown_window.winfo_exists():
            self.dropdown_window.destroy()
            self.dropdown_window = None
