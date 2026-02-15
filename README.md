# Telegram-Cursor Bridge (tcb)

CLI tool that bridges Telegram Bot and Cursor Agent CLI. Messages sent to the Telegram bot are forwarded to Cursor Agent and responses are sent back.

## Install

```bash
python3 -m pip install -e .

# Add to PATH if needed
export PATH="$PATH:$HOME/Library/Python/3.9/bin"
```

Requires [Cursor Agent CLI](https://cursor.com/cli):
```bash
curl https://cursor.com/install -fsSS | bash
```

## Setup

```bash
tcb init --token "YOUR_BOT_TOKEN" --username "your_bot_username"
```

Config is stored at `~/telegrambot/config.json`.

## Usage

```bash
tcb start      # Start daemon
tcb stop       # Stop daemon
tcb status     # Check daemon status
tcb logs       # View logs (last 50 lines)
tcb logs -f    # Follow logs
tcb config     # Show config
tcb config --model claude-4.6-opus --interval 5  # Update config
```

## How it works

1. Daemon polls Telegram `getUpdates` API periodically
2. New messages are forwarded to `agent -p -m <model>` (Cursor Agent CLI in print mode)
3. Response is sent back to the Telegram chat
