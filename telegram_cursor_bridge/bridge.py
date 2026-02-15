import json
import logging
import os
import subprocess
import time

from .config import load_config, load_offset, save_offset

logger = logging.getLogger("telegram-cursor-bridge")


# ── Telegram API via curl (reliable SOCKS5 support) ──


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
    """Extract host:port from socks5h://host:port format."""
    if not proxy_url:
        return ""
    proxy_url = proxy_url.replace("socks5h://", "").replace("socks5://", "")
    return proxy_url


def get_updates(token, offset, proxy=""):
    return tg_api(token, "getUpdates", {"offset": offset, "timeout": 5}, proxy)


def send_message(token, chat_id, text, proxy=""):
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk}, proxy)


# ── Cursor CLI helper ──


def run_cursor(prompt, model, working_dir, api_key=""):
    cmd = [
        "agent",
        "-p", "-f", "--trust",
        "--model", model,
        "--output-format", "text",
    ]
    if api_key:
        cmd += ["--api-key", api_key]
    logger.info("Running cursor agent (model=%s) ...", model)
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
            timeout=300,
            cwd=working_dir,
            env=env,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n\n[stderr]: {result.stderr.strip()}"
        return output if output else "(empty response from cursor)"
    except subprocess.TimeoutExpired:
        return "(cursor timed out after 300s)"
    except FileNotFoundError:
        return "(cursor agent CLI not found – run: curl https://cursor.com/install -fsSS | bash)"
    except Exception as e:
        return f"(cursor error: {e})"


# ── Main poll loop ──


def poll_loop():
    cfg = load_config()
    token = cfg["bot_token"]
    model = cfg.get("cursor_model", "claude-4.6-opus")
    interval = cfg.get("poll_interval", 3)
    working_dir = cfg.get("working_dir", ".")
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

                    if text.startswith("/start"):
                        send_message(token, chat_id, "Ready. Send me a prompt and I'll forward it to Cursor Agent.", proxy)
                        continue

                    send_message(token, chat_id, "⏳ Processing with Cursor Agent...", proxy)

                    reply = run_cursor(text, model, working_dir, api_key)
                    logger.info("Cursor reply length: %d", len(reply))
                    send_message(token, chat_id, reply, proxy)

        except Exception as e:
            logger.error("Poll loop error: %s", e)

        time.sleep(interval)
