import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading
from .history import show_history_window
from .settings import show_settings_window

_icon = None

def create_bell_image(width=64, height=64) -> Image:
    """Draw a premium bright-blue notification bell icon dynamically in memory."""
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Premium soft-blue circular background glow
    draw.ellipse([4, 4, 60, 60], fill=(10, 132, 255, 25))
    
    # Bell top hanger ring
    draw.ellipse([28, 8, 36, 16], outline=(10, 132, 255, 255), width=2)
    
    # Bell clapper (bottom pendulum circle)
    draw.ellipse([27, 48, 37, 58], fill=(10, 132, 255, 255))
    
    # Bell top dome
    draw.ellipse([18, 14, 46, 42], fill=(10, 132, 255, 255))
    
    # Bell body flare shape
    draw.polygon([
        (18, 28), (46, 28),
        (50, 46), (14, 46)
    ], fill=(10, 132, 255, 255))
    
    # Bell rim plate
    draw.rounded_rectangle([10, 43, 54, 48], radius=2, fill=(10, 132, 255, 255))
    
    return image

def setup_tray(daemon, root_window):
    """Setup and start the pystray icon in a background thread."""
    global _icon
    
    from ..utils.autostart import is_compiled_mode
    is_frozen = is_compiled_mode()
    
    import sys
    def _hot_reload_module(module_name: str):
        if not is_frozen:
            import importlib
            if module_name in sys.modules:
                try:
                    importlib.reload(sys.modules[module_name])
                    print(f"[HotReload] Successfully reloaded {module_name}")
                except Exception as e:
                    print(f"[HotReload] Failed to reload {module_name}: {e}")

    def on_history(icon, item):
        print("[Tray] User clicked '打开历史通知'")
        _hot_reload_module('auto_bfsu.ui.history')
        from .history import show_history_window
        show_history_window()

    def on_check(icon, item):
        print("[Tray] User clicked '立即检查通知'. Instantly waking up daemon...")
        daemon.check_event.set()

    def on_settings(icon, item):
        print("[Tray] User clicked '参数设置'")
        _hot_reload_module('auto_bfsu.ui.settings')
        from .settings import show_settings_window
        show_settings_window()

    def on_autostart(icon, item):
        from ..utils.autostart import is_autostart_enabled, set_autostart
        new_state = not is_autostart_enabled()
        print(f"[Tray] User clicked '开机自启动', toggling to: {new_state}")
        set_autostart(new_state)
        icon.update_menu()

    def on_disable_dev(icon, item):
        from ..config import Config
        print("[Tray] User clicked '关闭开发者模式'")
        Config.DEVELOPER_MODE = False
        Config.ENABLE_SIS_CHECK = False
        
        env_path = Config.BASE_DIR / ".env"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = [l for l in lines if not l.startswith("DEVELOPER_MODE=") 
                         and not l.startswith("ENABLE_SIS_CHECK=")
                         and not l.startswith("SIS_SIGNIN_TIMES=")
                         and not l.startswith("SIS_CHECK_INTERVAL=")]
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                
        # Notify via Tkinter main thread
        from tkinter import messagebox
        root_window.after(0, lambda: messagebox.showinfo("开发者模式已关闭", "相关特殊功能已全部从界面和配置中隐秘抹除。"))
        
        # Note: pystray doesn't natively re-evaluate visible=lambda dynamically after menu creation on Windows sometimes,
        # but icon.update_menu() forces a redraw.
        icon.update_menu()

    def on_exit(icon, item):
        print("[Tray] User clicked '退出程序'. Shutting down application gracefully...")
        # 1. Stop tray icon
        icon.stop()
        # 2. Flag daemon thread to exit, and wake it up
        daemon.stop_event.set()
        daemon.check_event.set()
        # 3. Schedule Tkinter root mainloop exit on the main thread safely
        root_window.after(0, root_window.quit)
        
    def on_mock(icon, item):
        print("[Tray] User clicked '发送 Mock 测试消息'")
        _hot_reload_module('auto_bfsu.ui.notifier')
        from .notifier import show_notification
        import datetime
        show_notification(
            title="这是一条 Mock 测试消息",
            publisher="系统测试",
            date_str=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            url="https://github.com",
            summary="这是一条为了测试通知弹窗渲染和点击回调生成的伪造消息，仅在源码开发模式下可见。",
            category="测试通知",
            relevance=95,
            relevance_summary="极高相关度，因为这是您主动触发的测试。",
            source="本地调试",
            notice_id="mock_id_" + datetime.datetime.now().strftime("%H%M%S")
        )

    from ..utils.autostart import is_autostart_enabled

    from ..config import Config
    menu_items = [
        item("北外智能助手", lambda icon, item: None, enabled=False),
        pystray.Menu.SEPARATOR,
        item("打开历史通知", on_history),
        item("立即检查通知", on_check),
        item("助手参数设置", on_settings),
        item("开机自启动", on_autostart, checked=lambda item: is_autostart_enabled(), visible=lambda item: sys.platform.startswith('win')),
        item("关闭开发者模式", on_disable_dev, visible=lambda item: getattr(Config, 'DEVELOPER_MODE', False))
    ]
    
    if not is_frozen:
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(item("发送 Mock 测试消息", on_mock))
        
    menu_items.extend([
        pystray.Menu.SEPARATOR,
        item("退出程序", on_exit)
    ])

    menu = pystray.Menu(*menu_items)

    _icon = pystray.Icon(
        "AutoBFSU",
        create_bell_image(),
        "北外智能助手",
        menu
    )
    
    # Run pystray's blocking event loop inside a daemon thread
    tray_thread = threading.Thread(target=_icon.run, daemon=True)
    tray_thread.start()
    print("[Tray] System tray icon background thread started successfully.")

def stop_tray():
    """Manually terminate system tray if needed."""
    global _icon
    if _icon:
        _icon.stop()
        print("[Tray] System tray stopped.")

def update_tray_menu():
    """Forces the system tray to refresh its menu items."""
    global _icon
    if _icon:
        try:
            _icon.update_menu()
            print("[Tray] System tray menu updated dynamically.")
        except Exception as e:
            print(f"[Tray] Failed to update tray menu: {e}")
