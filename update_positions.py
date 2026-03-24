"""
update_positions.py
===================
Fetches current Alpaca paper positions and:
  1. Saves them to positions.json
  2. Injects them into MARKET_RESEARCH_PROMPT.md so the prompt
     always reflects current holdings when you paste it to an AI.

Run manually or add to a cron/LaunchAgent to keep in sync.

Usage:
  python update_positions.py
"""

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import requests, urllib3, json, os, re
from datetime import datetime
from pathlib import Path
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings()


class NoVerifyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def get_session():
    s = requests.Session()
    s.verify = False
    s.mount("https://", NoVerifyAdapter())
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    if not api_key or not api_secret:
        raise EnvironmentError(
            "Missing ALPACA_API_KEY or ALPACA_API_SECRET. "
            "Add them to your .env file. See .env.example."
        )
    s.headers.update({
        "APCA-API-KEY-ID":     api_key,
        "APCA-API-SECRET-KEY": api_secret,
    })
    return s


def fetch_positions():
    s = get_session()
    account   = s.get("https://paper-api.alpaca.markets/v2/account").json()
    positions = s.get("https://paper-api.alpaca.markets/v2/positions").json()

    result = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "account": {
            "equity":        float(account["equity"]),
            "cash":          float(account["cash"]),
            "buying_power":  float(account["buying_power"]),
        },
        "positions": []
    }

    for p in positions:
        result["positions"].append({
            "ticker":           p["symbol"],
            "qty":              float(p["qty"]),
            "avg_entry_price":  float(p["avg_entry_price"]),
            "market_value":     float(p["market_value"]),
            "unrealized_pl":    float(p["unrealized_pl"]),
            "unrealized_pl_pct": round(float(p["unrealized_plpc"]) * 100, 2),
            "side":             p["side"],
        })

    return result


def save_positions(data: dict):
    path = Path(__file__).parent / "positions.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Saved {len(data['positions'])} positions to positions.json")
    return path


def build_positions_markdown(data: dict) -> str:
    account = data["account"]
    positions = data["positions"]
    updated = data["updated_at"]

    lines = [f"_Last updated: {updated}_\n"]
    lines.append(f"**Portfolio:** Equity ${account['equity']:,.2f} | "
                 f"Cash ${account['cash']:,.2f} | "
                 f"Buying Power ${account['buying_power']:,.2f}\n")

    if not positions:
        lines.append("**No open positions. Portfolio is 100% cash.**")
    else:
        lines.append(f"**{len(positions)} open position(s):**\n")
        lines.append("| Ticker | Qty | Avg Cost | Mkt Value | Unrealized P/L | P/L % |")
        lines.append("|--------|-----|----------|-----------|----------------|-------|")
        for p in sorted(positions, key=lambda x: x["market_value"], reverse=True):
            pl_sign = "+" if p["unrealized_pl"] >= 0 else ""
            lines.append(
                f"| {p['ticker']} | {p['qty']:.4f} | ${p['avg_entry_price']:.2f} "
                f"| ${p['market_value']:,.2f} "
                f"| {pl_sign}${p['unrealized_pl']:,.2f} "
                f"| {pl_sign}{p['unrealized_pl_pct']:.2f}% |"
            )

    return "\n".join(lines)


def inject_into_prompt(markdown: str):
    prompt_path = Path(__file__).parent / "MARKET_RESEARCH_PROMPT.md"
    content = prompt_path.read_text()

    # Replace everything between the placeholder tags
    pattern = r"<!-- POSITIONS_PLACEHOLDER -->.*?<!-- /POSITIONS_PLACEHOLDER -->"
    replacement = f"<!-- POSITIONS_PLACEHOLDER -->\n{markdown}\n<!-- /POSITIONS_PLACEHOLDER -->"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    prompt_path.write_text(new_content)
    print(f"[OK] Injected positions into MARKET_RESEARCH_PROMPT.md")


def print_summary(data: dict):
    account = data["account"]
    positions = data["positions"]
    print("\n" + "=" * 55)
    print("  CURRENT PAPER PORTFOLIO")
    print("=" * 55)
    print(f"  Equity      : ${account['equity']:>12,.2f}")
    print(f"  Cash        : ${account['cash']:>12,.2f}")
    print(f"  Buying power: ${account['buying_power']:>12,.2f}")
    if positions:
        print(f"\n  {'Ticker':<8} {'Qty':>8} {'Avg':>8} {'Value':>10} {'P/L':>10} {'%':>7}")
        print("  " + "-" * 53)
        for p in sorted(positions, key=lambda x: x["market_value"], reverse=True):
            s = "+" if p["unrealized_pl"] >= 0 else ""
            print(f"  {p['ticker']:<8} {p['qty']:>8.3f} "
                  f"${p['avg_entry_price']:>7.2f} "
                  f"${p['market_value']:>9,.2f} "
                  f"{s}${p['unrealized_pl']:>8,.2f} "
                  f"{s}{p['unrealized_pl_pct']:>5.2f}%")
    else:
        print("\n  No open positions.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    data = fetch_positions()
    save_positions(data)
    md = build_positions_markdown(data)
    inject_into_prompt(md)
    print_summary(data)
