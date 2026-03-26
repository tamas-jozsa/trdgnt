# TradingAgents/graph/signal_processing.py

import logging
import re

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

VALID_SIGNALS = {"BUY", "SELL", "HOLD"}


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """
        Process a full trading signal to extract the core decision.

        Uses regex-only extraction — no secondary LLM call needed because the
        Risk Judge is explicitly instructed to end with "FINAL DECISION: **BUY/SELL/HOLD**".

        Args:
            full_signal: Complete trading signal text (may be None or empty)

        Returns:
            Extracted decision: exactly "BUY", "SELL", or "HOLD".
            Defaults to "HOLD" if no valid signal can be extracted.
        """
        if not full_signal:
            logger.warning("SignalProcessor: received empty/None signal — defaulting to HOLD")
            return "HOLD"
        return self._parse_signal(full_signal, context=full_signal)

    @staticmethod
    def _parse_signal(raw: str, context: str = "") -> str:
        """
        Robustly extract BUY / SELL / HOLD from an LLM response.

        Strategy (in order):
          1. Exact match after stripping whitespace and uppercasing
          2. Regex search for the word anywhere in the response
          3. Regex search in the original full_signal prose as fallback
          4. Default to HOLD with a warning log
        """
        # 1. Exact match
        cleaned = raw.strip().upper()
        if cleaned in VALID_SIGNALS:
            return cleaned

        # 2. Regex in LLM response
        match = re.search(r"\b(BUY|SELL|HOLD)\b", raw, re.IGNORECASE)
        if match:
            signal = match.group(1).upper()
            logger.debug(
                "SignalProcessor: extracted %r from LLM response via regex (raw=%r)",
                signal,
                raw[:80],
            )
            return signal

        # 3. Regex in original prose as last resort
        if context:
            match = re.search(r"\b(BUY|SELL|HOLD)\b", context, re.IGNORECASE)
            if match:
                signal = match.group(1).upper()
                logger.warning(
                    "SignalProcessor: LLM response %r unparseable; "
                    "falling back to signal found in original prose: %r",
                    raw[:80],
                    signal,
                )
                return signal

        # 4. Safe default
        logger.warning(
            "SignalProcessor: could not extract a valid signal from LLM response %r "
            "or original prose. Defaulting to HOLD.",
            raw[:80],
        )
        return "HOLD"
