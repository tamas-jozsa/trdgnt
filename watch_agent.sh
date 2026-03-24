#!/bin/bash
# watch_agent.sh — live dashboard for the TradingAgents loop

LOG_DIR="/Users/tjozsa/cf-repos/github/trdagnt/trading_loop_logs"
STDOUT="$LOG_DIR/stdout.log"
STDERR="$LOG_DIR/stderr.log"

# Colors
RESET="\033[0m"
BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
DIM="\033[2m"

clear_screen() { printf "\033[2J\033[H"; }

status_line() {
    local pid status
    pid=$(launchctl list | grep tradingagents | awk '{print $1}')
    status=$(launchctl list | grep tradingagents | awk '{print $2}')

    printf "${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}\n"
    printf "${BOLD}║         TRADINGAGENTS — LIVE DASHBOARD                  ║${RESET}\n"
    printf "${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}\n"
    printf "  Time   : ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${RESET}\n"

    if [[ "$pid" == "-" || -z "$pid" ]]; then
        printf "  Agent  : ${RED}${BOLD}STOPPED${RESET}\n"
    else
        printf "  Agent  : ${GREEN}${BOLD}RUNNING${RESET}  (PID $pid, exit code $status)\n"
    fi
    printf "\n"
}

watchlist_panel() {
    printf "${BOLD}  WATCHLIST${RESET}\n"
    printf "  ─────────────────────────────────────────────────────────\n"

    /Users/tjozsa/miniconda3/envs/tradingagents/bin/python3 - <<'EOF'
import sys
sys.path.insert(0, "/Users/tjozsa/cf-repos/github/trdagnt")
from trading_loop import WATCHLIST, get_sector, get_tier

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
DIM    = "\033[2m"
RED    = "\033[31m"

TIER_COLOR = {"CORE": GREEN, "TACTICAL": YELLOW, "SPECULATIVE": RED, "HEDGE": YELLOW}

groups = {"CORE": [], "TACTICAL": [], "SPECULATIVE": [], "HEDGE": []}
for ticker in WATCHLIST:
    tier = get_tier(ticker)
    groups.setdefault(tier, []).append((ticker, get_sector(ticker)))

order = ["CORE", "TACTICAL", "SPECULATIVE", "HEDGE"]
for grp in order:
    items = groups.get(grp, [])
    if not items:
        continue
    col = TIER_COLOR.get(grp, GREEN)
    print(f"  {col}{BOLD}{grp} ({len(items)}){RESET}")
    row = []
    for ticker, sector in items:
        row.append(f"{col}{ticker:<6}{RESET}{DIM}{sector[:18]:<19}{RESET}")
        if len(row) == 3:
            print("  " + "  ".join(row))
            row = []
    if row:
        print("  " + "  ".join(row))
    print()

print(f"  {DIM}Total: {len(WATCHLIST)} tickers{RESET}")
EOF
    printf "\n"
}

today_summary() {
    local today
    today=$(date '+%Y-%m-%d')
    local log_file="$LOG_DIR/$today.json"

    printf "${BOLD}  TODAY'S TRADES ($today)${RESET}\n"
    printf "  ─────────────────────────────────────────────────────────\n"

    if [[ ! -f "$log_file" ]]; then
        printf "  ${DIM}No trades yet today.${RESET}\n\n"
        return
    fi

    # Parse JSON with python
    /Users/tjozsa/miniconda3/envs/tradingagents/bin/python3 - <<EOF
import json, sys
with open("$log_file") as f:
    data = json.load(f)
trades = data.get("trades", [])
buys  = [t for t in trades if t.get("decision") == "BUY"]
sells = [t for t in trades if t.get("decision") == "SELL"]
holds = [t for t in trades if t.get("decision") == "HOLD"]
errors= [t for t in trades if t.get("order", {}) and t.get("error")]

print(f"  Total analysed : {len(trades)}")
print(f"  \033[32mBUY  ({len(buys)})\033[0m : {', '.join(t['ticker'] for t in buys) or 'none'}")
print(f"  \033[31mSELL ({len(sells)})\033[0m : {', '.join(t['ticker'] for t in sells) or 'none'}")
print(f"  \033[33mHOLD ({len(holds)})\033[0m : {', '.join(t['ticker'] for t in holds) or 'none'}")
if errors:
    print(f"  \033[31mERRORS ({len(errors)})\033[0m : {', '.join(t['ticker'] for t in errors)}")
EOF
    printf "\n"
}

recent_log() {
    printf "${BOLD}  AGENT OUTPUT${RESET}\n"
    printf "  ─────────────────────────────────────────────────────────\n"

    if [[ ! -f "$STDOUT" ]]; then
        printf "  ${DIM}No output yet.${RESET}\n\n"
        return
    fi

    # Show the single most recent [WAIT] line as a status line, not 20 copies
    local wait_line
    wait_line=$(grep '\[WAIT\]' "$STDOUT" | tail -1)
    if [[ -n "$wait_line" ]]; then
        printf "  ${YELLOW}${wait_line}${RESET}\n"
    fi

    # Show last 10 non-WAIT lines (actual trading activity)
    local activity
    activity=$(grep -v '^\[WAIT\]' "$STDOUT" | tail -10)
    if [[ -n "$activity" ]]; then
        echo "$activity" | sed 's/^/  /'
    fi

    printf "\n"
}

recent_errors() {
    if [[ -f "$STDERR" ]] && [[ -s "$STDERR" ]]; then
        printf "${BOLD}${RED}  RECENT ERRORS (stderr)${RESET}\n"
        printf "  ─────────────────────────────────────────────────────────\n"
        tail -10 "$STDERR" | sed 's/^/  /'
        printf "\n"
    fi
}

footer() {
    printf "  ${DIM}Refreshing every 60s — Ctrl+C to exit${RESET}\n"
}

# Main loop
while true; do
    clear_screen
    status_line
    watchlist_panel
    today_summary
    recent_log
    recent_errors
    footer
    sleep 60
done
