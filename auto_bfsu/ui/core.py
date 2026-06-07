import queue

# ====================================================================
# AutoBFSU UI Core - Main Thread Queue Coordinator
# ====================================================================

gui_queue = queue.Queue()
_root = None

def init_gui_coordinator(root_window):
    """Initialize the thread-safe GUI coordinator with the main Tkinter root window."""
    global _root
    _root = root_window
    poll_gui_queue()

def poll_gui_queue():
    """Poll the thread-safe queue for GUI execution tasks on the main thread."""
    while not gui_queue.empty():
        try:
            callback, args, kwargs = gui_queue.get_nowait()
            callback(*args, **kwargs)
        except queue.Empty:
            break
        except Exception as e:
            print(f"[GUI Coordinator] Error executing callback: {e}")
    if _root:
        _root.after(100, poll_gui_queue)

def get_root_coordinator():
    """Return the global root Tkinter reference."""
    return _root

def run_on_main_thread(callback, *args, **kwargs):
    """Schedule a callback to run on the main thread via the coordinator queue."""
    if _root:
        gui_queue.put((callback, args, kwargs))
    else:
        # Fallback if no root is running (e.g. standalone execution)
        print("[GUI Coordinator] Warning: GUI loop not running, executing callback inline.")
        callback(*args, **kwargs)
