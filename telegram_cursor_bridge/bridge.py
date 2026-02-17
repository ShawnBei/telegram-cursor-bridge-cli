import json
import logging
import os
import subprocess
import time

from .config import (
    load_config, load_offset, save_offset,
    get_chat_session, set_chat_workspace, set_chat_session_id, clear_chat_session,
)

logger = logging.getLogger("telegram-cursor-bridge")


# ── Telegram API via curl ──


def tg_api(token, method, params=None, proxy=""):
    url = f"https://api.telegram.org/bot{token}/{method}"
    cmd = ["curl", "-s", "--connect-timeout", "10", "--max-time", "30"]
    if proxy:
        cmd += ["--socks5-hostname", proxy]
    if params:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(params)]
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.returncode != 0:
            logger.error("curl failed: %s", result.stderr.strip())
            return None
        return json.loads(result.stdout)
    except Exception as e:
        logger.error("Telegram request failed: %s", e)
        return None


def _parse_proxy(proxy_url):
    if not proxy_url:
        return ""
    return proxy_url.replace("socks5h://", "").replace("socks5://", "")


def get_updates(token, offset, proxy=""):
    return tg_api(token, "getUpdates", {"offset": offset, "timeout": 5}, proxy)


def send_message(token, chat_id, text, proxy=""):
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk}, proxy)


# ── Cursor CLI ──


def run_cursor(prompt, model, working_dir, api_key="", session_id=""):
    cmd = [
        "agent",
        "-p", "-f", "--trust",
        "--model", model,
        "--output-format", "stream-json",
        "--stream-partial-output",
    ]
    if session_id:
        cmd += ["--resume", session_id]
    if api_key:
        cmd += ["--api-key", api_key]

    logger.info("Running cursor agent (model=%s, workspace=%s, session=%s) ...",
                model, working_dir, session_id[:8] if session_id else "new")
    env = dict(os.environ)
    env["PATH"] = os.environ.get("PATH", "") + ":/Users/beining/.local/bin"
    if api_key:
        env["CURSOR_API_KEY"] = api_key
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=working_dir,
            env=env,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip() if result.stderr else ""
        if stderr:
            logger.warning("agent stderr (rc=%d): %s", result.returncode, stderr[:500])
        if result.returncode != 0:
            logger.error("agent exited with rc=%d", result.returncode)
        if not stdout:
            logger.error("agent returned empty stdout (rc=%d)", result.returncode)
            return {"text": f"(empty response, rc={result.returncode})\n{stderr}", "session_id": session_id}

        return _parse_stream_json(stdout, session_id)

    except subprocess.TimeoutExpired:
        logger.error("agent timed out after 600s (workspace=%s)", working_dir)
        return {"text": "(cursor timed out after 600s)", "session_id": session_id}
    except FileNotFoundError:
        logger.error("agent CLI not found in PATH")
        return {"text": "(cursor agent CLI not found)", "session_id": session_id}
    except Exception as e:
        logger.error("agent exception: %s", e, exc_info=True)
        return {"text": f"(cursor error: {e})", "session_id": session_id}


def _parse_stream_json(stdout, fallback_session_id):
    text_parts = []
    new_session = fallback_session_id
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "session_id" in data:
                new_session = data["session_id"]
            if "result" in data:
                text_parts = [data["result"]]
            elif "text" in data:
                text_parts.append(data["text"])
            elif "content" in data:
                text_parts.append(data["content"])
        except json.JSONDecodeError:
            text_parts.append(line)
    text = "".join(text_parts) if text_parts else stdout
    return {"text": text, "session_id": new_session}


# ── Bot commands ──

HELP_TEXT = """Available commands:
/project <path> - switch workspace
/new - start new session in current workspace
/ls - show current workspace & session
/history - list all workspaces you've used
/help - show this message

Any other text is sent to Cursor Agent."""


def handle_command(text, chat_id, token, proxy, model, api_key, default_workspace):
    session = get_chat_session(chat_id)
    workspace = session.get("workspace", default_workspace)
    session_id = session.get("session_id", "")

    if text == "/help" or text == "/start":
        send_message(token, chat_id, HELP_TEXT, proxy)
        return

    if text.startswith("/project"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(token, chat_id, f"Usage: /project <path>\nCurrent: {workspace}", proxy)
            return
        path = os.path.expanduser(parts[1].strip())
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            send_message(token, chat_id, f"Created: {path}", proxy)
        set_chat_workspace(chat_id, path)
        send_message(token, chat_id, f"Workspace: {path}\nSession reset. Send a message to begin.", proxy)
        return

    if text == "/new":
        clear_chat_session(chat_id)
        send_message(token, chat_id, f"New session started.\nWorkspace: {workspace}", proxy)
        return

    if text == "/ls":
        info = f"Workspace: {workspace}\nSession: {session_id[:12] + '...' if session_id else '(none)'}\nModel: {model}"
        send_message(token, chat_id, info, proxy)
        return

    if text == "/history":
        history = session.get("history", [])
        if not history:
            send_message(token, chat_id, "No workspace history.", proxy)
            return
        lines = [f"{i+1}. {h['path']}  ({h['ts']})" for i, h in enumerate(history)]
        send_message(token, chat_id, "Workspace history:\n" + "\n".join(lines), proxy)
        return

    # Regular prompt → forward to cursor agent
    send_message(token, chat_id, "⏳ Processing...", proxy)

    result = run_cursor(text, model, workspace, api_key, session_id)
    reply = result["text"]
    new_session_id = result.get("session_id", "")

    if new_session_id and new_session_id != session_id:
        set_chat_session_id(chat_id, new_session_id)
        logger.info("Session updated: %s", new_session_id[:12])

    logger.info("Cursor reply length: %d", len(reply))
    send_message(token, chat_id, reply, proxy)


# ── Main poll loop ──


def poll_loop():
    cfg = load_config()
    token = cfg["bot_token"]
    model = cfg.get("cursor_model", "claude-4.6-opus")
    interval = cfg.get("poll_interval", 3)
    default_workspace = cfg.get("working_dir", ".")
    proxy = _parse_proxy(cfg.get("proxy", ""))
    api_key = cfg.get("cursor_api_key", "")

    if not token:
        logger.error("bot_token not set in config.json")
        return

    if proxy:
        logger.info("Using SOCKS5 proxy: %s", proxy)

    offset = load_offset()
    logger.info("Starting poll loop (model=%s, interval=%ds, offset=%d)", model, interval, offset)

    while True:
        try:
            resp = get_updates(token, offset, proxy)
            if resp and resp.get("ok"):
                for update in resp.get("result", []):
                    update_id = update["update_id"]
                    offset = update_id + 1
                    save_offset(offset)

                    msg = update.get("message")
                    if not msg or "text" not in msg:
                        continue

                    chat_id = msg["chat"]["id"]
                    text = msg["text"]
                    user = msg.get("from", {}).get("username", "unknown")
                    logger.info("Message from @%s: %s", user, text[:80])

                    handle_command(text, chat_id, token, proxy, model, api_key, default_workspace)

        except Exception as e:
            logger.error("Poll loop error: %s", e)

        time.sleep(interval)
