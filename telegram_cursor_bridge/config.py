import json
import os
import time

BASE_DIR = os.path.expanduser("~/telegrambot")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PID_FILE = os.path.join(BASE_DIR, "daemon.pid")
LOG_FILE = os.path.join(BASE_DIR, "daemon.log")
OFFSET_FILE = os.path.join(BASE_DIR, ".offset")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")

DEFAULT_CONFIG = {
    "bot_token": "",
    "bot_username": "",
    "cursor_model": "claude-4.6-opus",
    "poll_interval": 3,
    "working_dir": BASE_DIR,
    "proxy": "",  # socks5h://127.0.0.1:1086 or http://host:port
    "cursor_api_key": "",
}


def ensure_base_dir():
    os.makedirs(BASE_DIR, exist_ok=True)


def load_config() -> dict:
    ensure_base_dir()
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged


def save_config(cfg: dict):
    ensure_base_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def load_offset() -> int:
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    return 0


def save_offset(offset: int):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


# ── Session management ──
# Structure: { "<chat_id>": { "workspace": "/path", "session_id": "uuid", "history": [...] } }

def _load_sessions() -> dict:
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_sessions(data: dict):
    ensure_base_dir()
    with open(SESSIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_chat_session(chat_id) -> dict:
    sessions = _load_sessions()
    return sessions.get(str(chat_id), {})


def set_chat_workspace(chat_id, workspace):
    sessions = _load_sessions()
    key = str(chat_id)
    entry = sessions.get(key, {})
    entry["workspace"] = workspace
    entry["session_id"] = ""  # reset session on workspace change
    # track in history
    history = entry.get("history", [])
    if not history or history[-1]["path"] != workspace:
        history.append({"path": workspace, "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
    entry["history"] = history
    sessions[key] = entry
    _save_sessions(sessions)


def set_chat_session_id(chat_id, session_id):
    sessions = _load_sessions()
    key = str(chat_id)
    entry = sessions.get(key, {})
    entry["session_id"] = session_id
    sessions[key] = entry
    _save_sessions(sessions)


def clear_chat_session(chat_id):
    sessions = _load_sessions()
    key = str(chat_id)
    entry = sessions.get(key, {})
    entry["session_id"] = ""
    sessions[key] = entry
    _save_sessions(sessions)
