#!/usr/bin/env python3
import argparse
import json
import sys

from . import __version__
from .config import CONFIG_PATH, load_config, save_config, ensure_base_dir
from .daemon import daemon_start, daemon_stop, daemon_status


def cmd_start(args):
    cfg = load_config()
    if not cfg.get("bot_token"):
        print(f"Error: bot_token not set. Run 'tcb config' or edit {CONFIG_PATH}")
        sys.exit(1)
    daemon_start()


def cmd_stop(args):
    daemon_stop()


def cmd_status(args):
    daemon_status()


def cmd_config(args):
    cfg = load_config()
    if args.show:
        print(json.dumps(cfg, indent=2))
        return
    changed = False
    if args.token:
        cfg["bot_token"] = args.token
        changed = True
    if args.username:
        cfg["bot_username"] = args.username
        changed = True
    if args.model:
        cfg["cursor_model"] = args.model
        changed = True
    if args.interval:
        cfg["poll_interval"] = args.interval
        changed = True
    if args.workdir:
        cfg["working_dir"] = args.workdir
        changed = True
    if args.proxy is not None:
        cfg["proxy"] = args.proxy
        changed = True
    if args.cursor_api_key:
        cfg["cursor_api_key"] = args.cursor_api_key
        changed = True
    if changed:
        save_config(cfg)
        print("Config saved to", CONFIG_PATH)
    else:
        print(json.dumps(cfg, indent=2))


def cmd_init(args):
    ensure_base_dir()
    cfg = load_config()
    if not cfg.get("bot_token") or args.force:
        cfg["bot_token"] = args.token or cfg.get("bot_token", "")
        cfg["bot_username"] = args.username or cfg.get("bot_username", "")
        save_config(cfg)
        print(f"Config initialized at {CONFIG_PATH}")
    else:
        print(f"Config already exists at {CONFIG_PATH} (use --force to overwrite)")


def cmd_logs(args):
    from .config import LOG_FILE
    import os
    if not os.path.exists(LOG_FILE):
        print("No log file found")
        return
    if args.follow:
        import subprocess
        subprocess.run(["tail", "-f", LOG_FILE])
    else:
        n = args.lines or 50
        import subprocess
        subprocess.run(["tail", "-n", str(n), LOG_FILE])


def main():
    parser = argparse.ArgumentParser(
        prog="tcb",
        description="Telegram-Cursor Bridge: forward Telegram messages to Cursor Agent CLI",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # start
    p_start = sub.add_parser("start", help="Start the daemon")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop the daemon")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = sub.add_parser("status", help="Show daemon status")
    p_status.set_defaults(func=cmd_status)

    # config
    p_cfg = sub.add_parser("config", help="View or update config")
    p_cfg.add_argument("--show", action="store_true", help="Show current config")
    p_cfg.add_argument("--token", help="Set bot token")
    p_cfg.add_argument("--username", help="Set bot username")
    p_cfg.add_argument("--model", help="Set cursor model (default: claude-4.6-opus)")
    p_cfg.add_argument("--interval", type=int, help="Set poll interval in seconds")
    p_cfg.add_argument("--workdir", help="Set working directory for cursor agent")
    p_cfg.add_argument("--proxy", help="Set proxy (e.g. socks5h://127.0.0.1:1086)")
    p_cfg.add_argument("--cursor-api-key", help="Set Cursor API key")
    p_cfg.set_defaults(func=cmd_config)

    # init
    p_init = sub.add_parser("init", help="Initialize config")
    p_init.add_argument("--token", help="Bot token")
    p_init.add_argument("--username", help="Bot username")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_init.set_defaults(func=cmd_init)

    # logs
    p_logs = sub.add_parser("logs", help="View daemon logs")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    p_logs.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to show")
    p_logs.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
