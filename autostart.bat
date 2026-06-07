@echo off
rem ====================================================================
rem AutoBFSU Windows 开机静默自启脚本 (极速闪烁模式)
rem ====================================================================
rem 重要提示: 请不要移动此文件！
rem 如果您想手动设置开机启动，请为本文件创建一个“快捷方式”，
rem 然后将“快捷方式”放入 Windows 的“启动”文件夹 (shell:startup) 中。
rem ====================================================================

cd /d "%~dp0"
if exist .venv\Scripts\pythonw.exe (
    start "" ".venv\Scripts\pythonw.exe" main.py --daemon
) else (
    start "" pythonw main.py --daemon
)
exit
