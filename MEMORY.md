# Telegram-Cursor Bridge CLI

## Project Info
- Location: `/Users/beining/Documents-Local/my-workspace/telegram-bot-cli`
- Base dir at runtime: `~/telegrambot/`
- Config: `~/telegrambot/config.json`
- CLI command: `tcb` (installed via pip)
- Python 3.9 compatible (system Python on this Mac)

## Telegram Bot
- Username: `bn_normal_testing_bot`
- Token: `8401836087:AAHYnu7Ty1irCRHeg56o6F5JKsvaAxRtvY4`

## Cursor Agent CLI
- Binary: `~/.local/bin/agent` (Node.js based)
- IMPORTANT: use `--model` (long flag), NOT `-m` (broken in 2026.02.13)
- IMPORTANT: pipe prompt via stdin (`input=prompt`), not as CLI argument
- IMPORTANT: add `--trust` flag for headless mode
- Command: `echo "prompt" | agent -p -f --trust --model opus-4.6 --output-format text`
- API key: `CURSOR_API_KEY` env var or `--api-key` flag
- Install: `curl https://cursor.com/install -fsSS | bash`
- Docs: https://cursor.com/docs/cli/overview
- Available models: opus-4.6, opus-4.6-thinking, sonnet-4.5, gpt-5.2, etc (`agent models`)

## Network / Proxy
- Telegram API blocked — needs SOCKS5 proxy at 127.0.0.1:1086 (V2BOX)
- Cursor API (api2.cursor.sh) is reachable directly, no proxy needed
- Proxy configured in config.json, bridge uses curl --socks5-hostname

## PATH
- `tcb` installed to `/Users/beining/Library/Python/3.9/bin`
- Added to `~/.zshrc`: `export PATH="$PATH:$HOME/Library/Python/3.9/bin"`

## Architecture
- Pure Python, no external dependencies (uses curl subprocess for Telegram API)
- Daemon uses Unix double-fork
- PID file: `~/telegrambot/daemon.pid`
- Log file: `~/telegrambot/daemon.log`
- Offset tracking: `~/telegrambot/.offset`
