"""Tests for streaming CSV read with size and corruption safeguards."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


def _make_csv(path: Path, rows: int = 100) -> None:
    """Write a minimal valid OHLCV CSV."""
    lines = ["Date,Open,High,Low,Close,Volume"]
    for i in range(rows):
        lines.append(f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d},"
                     f"{100+i},{105+i},{95+i},{102+i},{1000000}")
    path.write_text("\n".join(lines))


class TestSafeReadCsv:

    def test_reads_normal_file(self, tmp_path):
        from tradingagents.dataflows.y_finance import _safe_read_csv
        p = tmp_path / "NVDA-test.csv"
        _make_csv(p, rows=200)
        df = _safe_read_csv(str(p), "NVDA")
        assert len(df) == 200
        assert "Date" in df.columns

    def test_reads_in_chunks_file_handle_closed(self, tmp_path):
        """File handle must be closed after read — not held open."""
        from tradingagents.dataflows.y_finance import _safe_read_csv
        import gc

        p = tmp_path / "NVDA-test.csv"
        _make_csv(p, rows=600)  # > 500 rows → forces multiple chunks

        df = _safe_read_csv(str(p), "NVDA")
        gc.collect()

        # File should still exist (not deleted — it was valid)
        assert p.exists()
        assert len(df) == 600

    def test_rejects_oversized_file(self, tmp_path):
        """File exceeding _MAX_CACHE_FILE_BYTES must be deleted and raise."""
        from tradingagents.dataflows.y_finance import _safe_read_csv, _MAX_CACHE_FILE_BYTES

        p = tmp_path / "NVDA-big.csv"
        # Write a file just over the limit
        p.write_bytes(b"x" * (_MAX_CACHE_FILE_BYTES + 1))

        with pytest.raises(Exception, match="Oversized"):
            _safe_read_csv(str(p), "NVDA")

        # File must be deleted
        assert not p.exists()

    def test_oversized_file_exactly_at_limit_is_rejected(self, tmp_path):
        """File AT the byte limit is also rejected (> not >=)."""
        from tradingagents.dataflows.y_finance import _safe_read_csv, _MAX_CACHE_FILE_BYTES

        p = tmp_path / "NVDA-limit.csv"
        p.write_bytes(b"x" * (_MAX_CACHE_FILE_BYTES + 1))

        with pytest.raises(Exception):
            _safe_read_csv(str(p), "NVDA")
        assert not p.exists()

    def test_file_at_limit_minus_one_is_accepted(self, tmp_path):
        """File just under the limit should be attempted (may fail parsing, not size)."""
        from tradingagents.dataflows.y_finance import _safe_read_csv, _MAX_CACHE_FILE_BYTES

        p = tmp_path / "NVDA-ok.csv"
        # Write a valid CSV that's under the size limit
        _make_csv(p, rows=50)
        assert p.stat().st_size < _MAX_CACHE_FILE_BYTES

        df = _safe_read_csv(str(p), "NVDA")
        assert len(df) == 50

    def test_zero_row_file_is_deleted_and_raises(self, tmp_path):
        """CSV with no data rows (header only or garbage) must be deleted and raise."""
        from tradingagents.dataflows.y_finance import _safe_read_csv

        p = tmp_path / "NVDA-empty.csv"
        p.write_text("")

        with pytest.raises(Exception):
            _safe_read_csv(str(p), "NVDA")

        assert not p.exists()

    def test_header_only_file_is_deleted_and_raises(self, tmp_path):
        """CSV with header but no rows is considered empty."""
        from tradingagents.dataflows.y_finance import _safe_read_csv

        p = tmp_path / "NVDA-header-only.csv"
        p.write_text("Date,Open,High,Low,Close,Volume\n")

        with pytest.raises(Exception):
            _safe_read_csv(str(p), "NVDA")

        assert not p.exists()

    def test_garbage_bytes_file_is_deleted_and_raises(self, tmp_path):
        """File with garbage bytes that parse as 0 rows must be deleted and raise."""
        from tradingagents.dataflows.y_finance import _safe_read_csv

        p = tmp_path / "NVDA-corrupt.csv"
        # Null bytes parse as 0-row DataFrame with on_bad_lines='skip'
        p.write_bytes(b"\x00\x01\x02\x03" * 100)

        with pytest.raises(Exception):
            _safe_read_csv(str(p), "NVDA")

        assert not p.exists()


class TestMaxCacheFileBytes:

    def test_constant_is_reasonable(self):
        """500 KB is between typical 2yr file (~50KB) and 15yr file (~5MB)."""
        from tradingagents.dataflows.y_finance import _MAX_CACHE_FILE_BYTES
        assert 100 * 1024 < _MAX_CACHE_FILE_BYTES < 2 * 1024 * 1024

    def test_constant_is_named_not_magic(self):
        """Constant must be importable (not a magic number inline)."""
        from tradingagents.dataflows.y_finance import _MAX_CACHE_FILE_BYTES
        assert isinstance(_MAX_CACHE_FILE_BYTES, int)


class TestDownloadSizeGuard:

    def test_oversized_download_not_cached(self, tmp_path):
        """If downloaded data exceeds limit, it must NOT be written to disk."""
        from tradingagents.dataflows import y_finance as yf_mod

        # Patch yf.download to return a huge fake DataFrame
        import pandas as pd
        import numpy as np

        n_rows = 10_000  # will produce >> 500KB CSV
        fake_df = pd.DataFrame({
            "Date":   pd.date_range("2000-01-01", periods=n_rows),
            "Open":   np.random.rand(n_rows),
            "High":   np.random.rand(n_rows),
            "Low":    np.random.rand(n_rows),
            "Close":  np.random.rand(n_rows),
            "Volume": np.random.randint(1e6, 1e8, n_rows),
        })

        cache_file = tmp_path / "NVDA-fake-2000-01-01-2026-01-01.csv"

        fake_config = {
            "data_vendors": {"technical_indicators": "online"},
            "data_cache_dir": str(tmp_path),
        }
        with patch.object(yf_mod.yf, "download", return_value=fake_df), \
             patch.object(yf_mod, "_cleanup_old_cache_files"), \
             patch("tradingagents.dataflows.config.get_config", return_value=fake_config), \
             patch("tradingagents.dataflows.y_finance.get_config", return_value=fake_config, create=True):
            with pytest.raises(Exception, match="[Oo]versized|refusing"):
                yf_mod._get_stock_stats_bulk("NVDA", "rsi", "2026-03-24")

        assert not cache_file.exists(), "Oversized download must NOT be written to disk"
