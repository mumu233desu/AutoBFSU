import sys
import io
import os
import subprocess

# Prevent console flashing on Windows when spawning subprocesses (e.g. pyexecjs compiling/running des.js via cscript)
if sys.platform.startswith('win'):
    _original_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        creationflags = kwargs.get("creationflags", 0)
        # 0x08000000 corresponds to subprocess.CREATE_NO_WINDOW
        creationflags |= 0x08000000
        kwargs["creationflags"] = creationflags
        return _original_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen


# Redirect standard streams to a log file when running under pythonw (without console) or when compiled without console
if sys.platform.startswith('win'):
    _is_gui_mode = False
    if getattr(sys, "frozen", False) or hasattr(sys, "nuitka_executable"):
        _is_gui_mode = True
    elif sys.stdout is None or sys.stderr is None:
        _is_gui_mode = True
    else:
        try:
            sys.stdout.write("")
            sys.stdout.flush()
        except Exception:
            _is_gui_mode = True

    if _is_gui_mode:
        try:
            # Determine correct directory (executable directory if compiled, or workspace root if not)
            if getattr(sys, "frozen", False) or hasattr(sys, "nuitka_executable"):
                _base_path = os.path.dirname(sys.executable)
            else:
                # auto_bfsu/main.py is located at E:\Coding\AutoBFSU\auto_bfsu\main.py
                # base path should be E:\Coding\AutoBFSU
                _base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            _log_path = os.path.join(_base_path, "auto_bfsu.log")
            log_file = open(_log_path, "a", encoding="utf-8")
            sys.stdout = log_file
            sys.stderr = log_file
        except Exception:
            # Fallback to devnull
            try:
                devnull = open(os.devnull, 'w')
                sys.stdout = devnull
                sys.stderr = devnull
            except Exception:
                pass

# Reconfigure stdout/stderr on Windows to use UTF-8 and safely replace characters, preventing terminal crashes
if sys.platform.startswith('win'):
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        except AttributeError:
            try:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            except AttributeError:
                pass
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
        except AttributeError:
            try:
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            except AttributeError:
                pass

from .scheduler.daemon import BFSUAutomationDaemon
import argparse


class SingleInstanceLock:
    """Ensures only a single background daemon instance is running to prevent login lockouts."""
    def __init__(self, name="AutoBFSU_SingleInstance_Mutex"):
        self.name = name
        self.is_locked = False
        self._mutex = None
        self._socket = None

    def acquire(self) -> bool:
        if sys.platform.startswith("win"):
            import ctypes
            try:
                # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
                self._mutex = ctypes.windll.kernel32.CreateMutexW(None, True, self.name)
                last_error = ctypes.windll.kernel32.GetLastError()
                # ERROR_ALREADY_EXISTS = 183
                if last_error == 183:
                    if self._mutex:
                        ctypes.windll.kernel32.CloseHandle(self._mutex)
                        self._mutex = None
                    return False
                self.is_locked = True
                return True
            except Exception:
                pass

        # Fallback for non-Windows or if ctypes fails: Socket-based lock
        import socket
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.bind(("127.0.0.1", 48271))
            self.is_locked = True
            return True
        except socket.error:
            self._socket = None
            return False

    def release(self):
        if not self.is_locked:
            return
        if self._mutex and sys.platform.startswith("win"):
            import ctypes
            try:
                ctypes.windll.kernel32.ReleaseMutex(self._mutex)
                ctypes.windll.kernel32.CloseHandle(self._mutex)
            except Exception:
                pass
            self._mutex = None
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self.is_locked = False


def enable_windows_efficiency_mode() -> bool:
    """
    Enables Windows 11 Efficiency Mode (Eco Mode) for the current process.
    This tells Windows to schedule the process on energy-efficient cores (E-Cores),
    and reduces process, I/O, and page priorities to background levels.
    Windows Task Manager will display the green leaf icon for this process.
    
    Returns:
        bool: True if QoS Efficiency Mode was successfully set, False otherwise.
    """
    if not sys.platform.startswith("win"):
        return False
        
    try:
        import ctypes
        from ctypes import wintypes

        # Define PROCESS_POWER_THROTTLING_STATE structure
        class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
            _fields_ = [
                ("Version", ctypes.c_ulong),
                ("ControlMask", ctypes.c_ulong),
                ("StateMask", ctypes.c_ulong),
            ]

        # Windows constants
        PROCESS_POWER_THROTTLING = 4
        PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
        
        # PROCESS_MODE_BACKGROUND_BEGIN: 0x00100000
        # Lowers CPU priority, I/O priority, and Page priority to background levels
        PROCESS_MODE_BACKGROUND_BEGIN = 0x00100000

        kernel32 = ctypes.windll.kernel32
        h_process = kernel32.GetCurrentProcess()

        success = True

        # 1. Enable Power Throttling (tells OS to prioritize E-cores for this background task)
        power_state = PROCESS_POWER_THROTTLING_STATE()
        power_state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
        power_state.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        power_state.StateMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED

        res_throttling = kernel32.SetProcessInformation(
            h_process,
            PROCESS_POWER_THROTTLING,
            ctypes.byref(power_state),
            ctypes.sizeof(power_state)
        )
        if not res_throttling:
            print(f"[AutoBFSU] [QoS] SetProcessInformation failed with error code: {kernel32.GetLastError()}")
            success = False
        else:
            print("[AutoBFSU] [QoS] Power Throttling (E-core scheduling) successfully enabled.")

        # 2. Set Background Priority (Lowers CPU/IO/Page scheduling priorities)
        res_priority = kernel32.SetPriorityClass(h_process, PROCESS_MODE_BACKGROUND_BEGIN)
        if not res_priority:
            print(f"[AutoBFSU] [QoS] SetPriorityClass (Background Mode) failed with error code: {kernel32.GetLastError()}")
            success = False
        else:
            print("[AutoBFSU] [QoS] Process priority class set to background mode.")

        if success:
            print("[AutoBFSU] [QoS] Windows Efficiency Mode (Eco Mode) is fully active.")
        return success

    except Exception as e:
        print(f"[AutoBFSU] [QoS] Failed to enable Efficiency Mode: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="AutoBFSU - 北京外国语大学自动化服务工具")
    parser.add_argument("--once", action="store_true", help="立即运行一次检测与签到，然后退出")
    parser.add_argument("--daemon", action="store_true", default=True, help="常驻后台周期性轮询运行（默认模式）")
    parser.add_argument("--test-ui", action="store_true", help="强制触发 Mock 消息通知，测试右下角悬浮窗视觉效果")
    parser.add_argument("--interval", type=int, default=60, help="后台轮询间隔（分钟，默认60分钟）")
    
    if len(sys.argv) == 1:
        args = parser.parse_args(["--daemon"])
    else:
        args = parser.parse_args()

    if args.test_ui:
        print("[AutoBFSU] Running in UI Test Mode (Mock Popup Display)...")
        from .ui.notifier import show_notification
        show_notification(
            title="📢 AutoBFSU 界面视觉效果与悬浮气泡功能测试通知",
            publisher="助手开发团队",
            date_str="2026-05-23",
            url="https://github.com/mumu/AutoBFSU",
            summary="这是一条专用于测试右下角悬浮气泡、字体大小排版、双按钮平衡布局（包含新恢复的“忽略此通知”按钮）以及 AI 智能分析卡片的模拟测试通知。请放心，此通知非学校官方教务发布，不代表任何课程或日程变动。",
            category="系统测试",
            relevance=99,
            relevance_summary="AI分析：这是一条 99% 高相关度的完美测试通知！它成功命中您亲自下达的“UI测试命令”，用来验证系统升级后的安全架构和交互反馈是否百分之百达标。"
        )
    elif args.once:
        daemon = BFSUAutomationDaemon()
        print("[AutoBFSU] Running single check cycle...")
        daemon.run_once(force_sis_check=True)
    else:
        # Enforce single instance lock for background daemon mode
        lock = SingleInstanceLock()
        if not lock.acquire():
            print("[AutoBFSU] [Warning] Another instance of AutoBFSU is already running. Exiting.")
            if sys.platform.startswith("win"):
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "AutoBFSU 已经在后台运行中！\n您可以在 Windows 任务栏右下角的系统托盘（蓝色铃铛图标）中找到它并进行管理。\n\n请勿同时启动多个后台进程，以防频繁并发登录导致您的教务账号被锁定，或发生文件写入冲突。",
                    "AutoBFSU 已在运行",
                    0x40  # MB_OK | MB_ICONINFORMATION
                )
            sys.exit(0)

        import atexit
        atexit.register(lock.release)

        # Enable Windows 11 Efficiency Mode (Eco Mode) to run on E-cores and lower scheduling priority
        enable_windows_efficiency_mode()

        import threading
        import customtkinter as ctk
        from .ui.core import init_gui_coordinator
        from .ui.tray import setup_tray

        print("[AutoBFSU] Initializing background daemon and system tray...")
        
        # 1. Initialize hidden Tkinter root window
        root = ctk.CTk()
        root.withdraw()
        
        # 2. Initialize GUI queue coordinator
        init_gui_coordinator(root)
        
        # 3. Initialize Automation Daemon
        from .config import Config
        daemon = BFSUAutomationDaemon()
        
        # Check if config is validated. If not, automatically launch Settings window to guide user!
        config_errors = Config.validate()
        if config_errors:
            print("[AutoBFSU] [Warning] Configuration invalid. Automatically opening parameters settings window...")
            from .ui.settings import show_settings_window
            root.after(100, show_settings_window)
        
        # Override NOTIFICATION_INTERVAL if user specified it via CLI argument explicitly
        if args.interval != 60:
            Config.NOTIFICATION_INTERVAL = args.interval
            
        # 4. Start daemon polling loop in a background thread
        daemon_thread = threading.Thread(
            target=daemon.start_infinite_loop,
            daemon=True
        )
        daemon_thread.start()
        print("[AutoBFSU] Background daemon thread started successfully.")
        
        # 5. Start system tray icon in a background thread
        setup_tray(daemon, root)
        
        # 6. Start the blocking Tkinter event loop on the main thread
        print("[AutoBFSU] Entering main GUI event loop. Running...")
        try:
            root.mainloop()
        except KeyboardInterrupt:
            print("\n[AutoBFSU] Exiting daemon gracefully via KeyboardInterrupt.")

if __name__ == "__main__":
    main()
