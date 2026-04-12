"""HTML message formatting helpers for the bot.

All bot messages use HTML parse_mode (consistent with app/services/telegram_service.py).
HTML must be escaped before embedding user-supplied text.

Usage:
    from bot.utils.formatters import code_block, bold, status_line
    text = bold("Site:") + " example.com\n" + status_line("Crawl", "OK", ok=True)
    await update.message.reply_html(text)
"""


def _escape(text: str) -> str:
    """Escape characters that have special meaning in Telegram HTML parse_mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code_block(text: str) -> str:
    """Wrap text in a monospace <pre> block (HTML parse_mode)."""
    return f"<pre>{_escape(text)}</pre>"


def bold(text: str) -> str:
    """Return text wrapped in <b> tags (HTML parse_mode)."""
    return f"<b>{_escape(text)}</b>"


def italic(text: str) -> str:
    """Return text wrapped in <i> tags (HTML parse_mode)."""
    return f"<i>{_escape(text)}</i>"


def status_line(label: str, value: str, ok: bool = True) -> str:
    """Return a formatted status line with a checkmark or cross icon.

    Example output: "✅ <b>Crawl:</b> running"
    """
    # Unicode HTML entities: ✅ = &#9989;  ❌ = &#10060;
    icon = "&#9989;" if ok else "&#10060;"
    return f"{icon} <b>{_escape(label)}:</b> {_escape(value)}"
