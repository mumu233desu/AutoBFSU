import sys
import os
from pathlib import Path
from ..config import Config

# Safe import of winreg for Windows platforms
if sys.platform.startswith('win'):
    import winreg
else:
    winreg = None

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoBFSU"

def is_compiled_mode() -> bool:
    """Check if the application is running in compiled mode (Nuitka standalone or PyInstaller)."""
    is_nuitka = "__compiled__" in globals()
    is_pyinstaller = getattr(sys, "frozen", False)
    return is_nuitka or is_pyinstaller

def get_autostart_command() -> str:
    """Get the absolute path/command to run on Windows startup."""
    if is_compiled_mode():
        # In Nuitka compiled mode, sys.executable points to an internal python.exe
        # We must use sys.argv[0] to get the actual path to the AutoBFSU.exe binary
        exe_path = os.path.abspath(sys.argv[0])
        return f'"{exe_path}"'
    else:
        # In source-code mode, point to the autostart.bat file in the project directory
        bat_path = Config.BASE_DIR / "autostart.bat"
        return f'"{bat_path}"'

def update_autostart_bat():
    """Dynamically update autostart.bat in source-code mode to point to the current project directory."""
    if is_compiled_mode():
        return
        
    bat_path = Config.BASE_DIR / "autostart.bat"
    
    # Generate the updated batch file content with current absolute project directory
    content = f"""@echo off
rem ====================================================================
rem AutoBFSU Windows 开机静默自启脚本 (极速闪烁模式)
rem ====================================================================
rem 重要提示: 如果您将此文件复制到了 Windows 启动文件夹中，
rem 请确保将下方括号中的路径修改为您的项目文件夹实际绝对路径！
rem ====================================================================

set PROJECT_DIR={Config.BASE_DIR}

cd /d "%PROJECT_DIR%"
if exist .venv\\Scripts\\pythonw.exe (
    start "" ".venv\\Scripts\\pythonw.exe" main.py --daemon
) else (
    start "" pythonw main.py --daemon
)
exit
"""
    try:
        # Avoid unnecessary writes if content is identical
        if bat_path.exists():
            with open(bat_path, "r", encoding="utf-8") as f:
                old_content = f.read()
            if old_content.strip() == content.strip():
                return
                
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Autostart] Successfully updated autostart.bat with PROJECT_DIR={Config.BASE_DIR}")
    except Exception as e:
        print(f"[Autostart] Failed to update autostart.bat: {e}")

def is_autostart_enabled() -> bool:
    """Check if the autostart registry entry exists and is correct."""
    if not winreg:
        return False
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            expected = get_autostart_command()
            # Compare registry value with expected startup command (case insensitive and strip quotes)
            return val.strip('"').lower() == expected.strip('"').lower()
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[Autostart] Error checking registry key: {e}")
        return False

def set_autostart(enabled: bool) -> bool:
    """Enable or disable Windows startup registration."""
    if not winreg:
        print("[Autostart] winreg is not available (non-Windows system). Cannot set autostart.")
        return False
        
    # In source-code mode, dynamically update autostart.bat path to ensure it is correct!
    if not is_compiled_mode() and enabled:
        update_autostart_bat()
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        try:
            if enabled:
                cmd = get_autostart_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                print(f"[Autostart] Registered startup command: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("[Autostart] Deleted startup registry key.")
                except FileNotFoundError:
                    pass
            return True
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        print(f"[Autostart] Failed to set autostart registry value: {e}")
        return False
