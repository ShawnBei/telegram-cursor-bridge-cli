import logging
import os
import signal
import sys
import time
from typing import Optional

from .config import BASE_DIR, LOG_FILE, PID_FILE, ensure_base_dir


def _read_pid() -> Optional[int]:
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _setup_logging():
    ensure_base_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
        ],
    )



def daemon_start():
    ensure_base_dir()
    existing_pid = _read_pid()
    if existing_pid and _is_running(existing_pid):
        print(f"Daemon already running (PID {existing_pid})")
        return

    # Fork: parent prints and exits, child becomes daemon
    child_pid = os.fork()
    if child_pid > 0:
        # Wait for daemon to write PID file
        for _ in range(20):
            time.sleep(0.1)
            actual_pid = _read_pid()
            if actual_pid:
                break
        actual_pid = actual_pid or child_pid
        sys.stdout.write(f"Daemon started (PID {actual_pid}, log: {LOG_FILE})\n")
        sys.stdout.flush()
        os._exit(0)

    # First child: create new session
    os.setsid()
    # Second fork
    pid2 = os.fork()
    if pid2 > 0:
        os._exit(0)

    # Redirect stdio
    sys.stdout.flush()
    sys.stderr.flush()
    devnull = open(os.devnull, "r")
    os.dup2(devnull.fileno(), sys.stdin.fileno())
    devnull_w = open(os.devnull, "w")
    os.dup2(devnull_w.fileno(), sys.stdout.fileno())
    os.dup2(devnull_w.fileno(), sys.stderr.fileno())

    _setup_logging()

    logger = logging.getLogger("telegram-cursor-bridge")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    def _shutdown(signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Daemon started (PID %d)", os.getpid())

    from .bridge import poll_loop

    try:
        poll_loop()
    except Exception as e:
        logger.error("Fatal error: %s", e)
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


def daemon_stop():
    pid = _read_pid()
    if not pid or not _is_running(pid):
        print("Daemon is not running")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return

    print(f"Stopping daemon (PID {pid})...")
    os.kill(pid, signal.SIGTERM)

    for _ in range(10):
        time.sleep(0.5)
        if not _is_running(pid):
            break

    if _is_running(pid):
        print("Force killing...")
        os.kill(pid, signal.SIGKILL)

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    print("Daemon stopped")


def daemon_status():
    pid = _read_pid()
    if pid and _is_running(pid):
        print(f"Daemon is running (PID {pid})")
        print(f"  Log: {LOG_FILE}")
        print(f"  Base dir: {BASE_DIR}")
    else:
        print("Daemon is not running")
        if pid:
            os.remove(PID_FILE)
