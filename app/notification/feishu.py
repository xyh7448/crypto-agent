"""Feishu (Lark) bot notification client - sends beautifully formatted interactive cards."""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
import re
import time
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Known symbol patterns for detecting section headers
SYMBOL_PATTERNS = re.compile(r"(BTCUSDT|ETHUSDT|SOLUSDT)")
# Section header pattern: "### 📈 市场概览" or "## 市场概览"
SECTION_HEADER = re.compile(r"^#{1,3}\s+(.*)")
# Table row: "| A | B | C |"
TABLE_ROW = re.compile(r"^\|.+\|$")
# Horizontal rule
HR_LINE = re.compile(r"^---+$")
# Emoji at start of line
EMOJI_MAP = {
    "📈": "📈",
    "🔍": "🔍",
    "💰": "💰",
    "🏦": "🏦",
    "📉": "📉",
    "💡": "💡",
    "🎯": "🎯",
    "🔧": "🔧",
    "📊": "📊",
    "🌡️": "🌡️",
    "🧠": "🧠",
    "📦": "📦",
    "📊": "📊",
}


class FeishuNotifier:
    """Sends notifications to Feishu (Lark) via custom bot webhook."""

    def __init__(self) -> None:
        self.webhook_url = settings.FEISHU_WEBHOOK_URL if hasattr(settings, 'FEISHU_WEBHOOK_URL') else ""
        self.secret = settings.FEISHU_SIGNING_SECRET if hasattr(settings, 'FEISHU_SIGNING_SECRET') else ""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        return self._client

    def _sign(self, timestamp: int) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}"
        return hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def send_text(self, text: str) -> bool:
        """Send a plain text message."""
        return await self._send({"msg_type": "text", "content": {"text": text}})

    # ── Public API ─────────────────────────────────────────────────────

    async def send_markdown(self, title: str, content: str) -> bool:
        """Send AI-generated report as a beautifully formatted interactive card."""
        sections = self._split_into_symbol_sections(content)
        card = self._build_card(sections)
        return await self.send_interactive(card)

    # ── Parsing ─────────────────────────────────────────────────────────

    def _split_into_symbol_sections(self, content: str) -> list[dict[str, Any]]:
        """Split the combined report into per-symbol sections.

        Each section dict::
            {"symbol": "BTCUSDT", "header": "...", "blocks": [("section_title", "text"), ...]}
        """
        lines = content.strip().split("\n")
        result = []
        current_symbol = None
        current_header = ""
        current_blocks: list[tuple[str, str]] = []
        current_section_title = ""
        current_section_lines: list[str] = []

        def _flush_section() -> None:
            if current_section_lines:
                text = self._clean_text("\n".join(current_section_lines))
                if text:
                    current_blocks.append((current_section_title, text))
                current_section_lines.clear()

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Detect symbol header: "📊 **BTCUSDT 每日分析报告**"
            sym_match = SYMBOL_PATTERNS.search(line)
            if sym_match and ("每日" in line or "分析" in line or "**" in line):
                _flush_section()
                if current_symbol and current_blocks:
                    result.append({
                        "symbol": current_symbol,
                        "header": current_header,
                        "blocks": list(current_blocks),
                    })
                current_symbol = sym_match.group(1)
                current_header = line
                current_blocks = []
                current_section_title = ""
                continue

            # Detect section header: "### 📈 市场概览"
            sec_match = SECTION_HEADER.match(line)
            if sec_match:
                _flush_section()
                current_section_title = sec_match.group(1).strip()
                continue

            # Skip HR
            if HR_LINE.match(line):
                continue

            # Skip table rows (Feishu cards don't support tables)
            if TABLE_ROW.match(line):
                # Convert table to inline text
                cells = [c.strip() for c in line.strip("|").split("|")]
                if not any(c.startswith("---") for c in cells):  # not header separator
                    clean = " · ".join(cells)
                    current_section_lines.append(clean)
                continue

            current_section_lines.append(line)

        # Flush last section and symbol
        _flush_section()
        if current_symbol and current_blocks:
            result.append({
                "symbol": current_symbol,
                "header": current_header,
                "blocks": list(current_blocks),
            })

        return result

    def _clean_text(self, text: str) -> str:
        """Remove raw markdown artifacts, keep readable content."""
        # Remove trailing `符号` artifacts like `（`留下的多余内容
        text = re.sub(r"\*\*", "", text)  # remove stray **
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ── Card Building ───────────────────────────────────────────────────

    def _build_card(self, sections: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a beautiful Feishu interactive card from parsed sections."""
        elements: list[dict[str, Any]] = []

        # ── Global Header ───────────────────────────────────────────────
        symbols_str = ", ".join(s["symbol"] for s in sections) if sections else "Crypto"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        elements.append({
            "tag": "markdown",
                "content": f"**📊 分析标的**：{symbols_str}\n🕐 {now}",
        })

        # ── Per-symbol content ──────────────────────────────────────────
        for idx, sec in enumerate(sections):
            if idx > 0:
                elements.append({"tag": "hr"})

            # Symbol name as a coloured tag
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🔹 {sec['symbol']}**",
                },
            })

            for section_title, text in sec.get("blocks", []):
                if not text:
                    continue
                # Build clean markdown block
                md_text = f"**{section_title}**\n{text}" if section_title else text
                elements.append({
                    "tag": "markdown",
                    "content": md_text,
                })

        # ── Footer ──────────────────────────────────────────────────────
        elements.append({
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": "🤖 Crypto Quant Agent · AI自动分析 · 仅供参考"}
            ],
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 Crypto 每日行情分析"},
                "template": "blue",
            },
            "elements": elements,
        }

    # ── Sending ─────────────────────────────────────────────────────────

    async def send_interactive(self, card: dict[str, Any]) -> bool:
        """Send an interactive card message."""
        payload = {"msg_type": "interactive", "card": card}
        return await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return False
        try:
            client = await self._get_client()
            timestamp = int(time.time())
            data = {
                "timestamp": str(timestamp),
                "sign": self._sign(timestamp) if self.secret else "",
                **payload,
            }
            response = await client.post(self.webhook_url, json=data)
            result = response.json()
            if result.get("code") == 0:
                logger.info("Feishu notification sent: success")
                return True
            else:
                logger.error("Feishu API error: %s", result)
                return False
        except Exception as e:
            logger.error("Feishu send error: %s", e, exc_info=True)
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
