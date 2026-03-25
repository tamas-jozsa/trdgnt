"""Tests for TICKET-029: Reddit post body and comment fetching."""

import json
import pytest
from unittest.mock import patch, MagicMock


def _make_post_response(body: str, comments: list[str]) -> bytes:
    """Build a minimal Reddit post+comments JSON response."""
    comment_children = [
        {"kind": "t1", "data": {"body": c, "score": 100 - i * 10}}
        for i, c in enumerate(comments)
    ]
    data = [
        {"data": {"children": [{"data": {"selftext": body, "is_self": True}}]}},
        {"data": {"children": comment_children}},
    ]
    return json.dumps(data).encode()


def _mock_urlopen(response_bytes: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestGetRedditPostBody:

    def test_returns_body_and_comments(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body
        payload = _make_post_response(
            body="GME short float is 22%. Catalyst: earnings beat incoming. Here's the DD...",
            comments=["I'm in for 100 shares", "This is the way"],
        )
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   return_value=_mock_urlopen(payload)):
            body, comments = get_reddit_post_body("/r/wallstreetbets/comments/abc/")

        assert "GME" in body
        assert "short float" in body
        assert len(comments) == 2
        assert "100 shares" in comments[0]

    def test_empty_body_for_deleted_post(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body
        payload = _make_post_response(body="[deleted]", comments=[])
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   return_value=_mock_urlopen(payload)):
            body, comments = get_reddit_post_body("/r/stocks/comments/xyz/")
        assert body == ""
        assert comments == []

    def test_empty_body_for_link_post(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body
        payload = _make_post_response(body="", comments=["interesting article"])
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   return_value=_mock_urlopen(payload)):
            body, comments = get_reddit_post_body("/r/investing/comments/def/")
        assert body == ""
        assert len(comments) == 1

    def test_body_truncated_to_max_chars(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body, MAX_BODY_CHARS
        long_body = "x" * (MAX_BODY_CHARS + 500)
        payload = _make_post_response(body=long_body, comments=[])
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   return_value=_mock_urlopen(payload)):
            body, _ = get_reddit_post_body("/r/wsb/comments/ghi/")
        assert len(body) == MAX_BODY_CHARS

    def test_returns_empty_on_network_error(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body
        from urllib.error import URLError
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   side_effect=URLError("timeout")):
            body, comments = get_reddit_post_body("/r/wsb/comments/jkl/")
        assert body == ""
        assert comments == []

    def test_max_two_comments_returned(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_post_body
        payload = _make_post_response(
            body="thesis here",
            comments=["comment 1", "comment 2", "comment 3", "comment 4"],
        )
        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   return_value=_mock_urlopen(payload)):
            _, comments = get_reddit_post_body("/r/wsb/comments/mno/")
        assert len(comments) <= 2


class TestRedditSentimentWithBodies:

    def test_top_posts_include_body_in_summary(self):
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment

        # Mock search results
        search_payload = json.dumps({"data": {"children": [
            {"data": {
                "title": "NVDA bull case — AI supercycle",
                "score": 1500,
                "num_comments": 200,
                "permalink": "/r/wallstreetbets/comments/abc/",
                "link_flair_text": "DD",
                "created_utc": 1711234567,
                "is_self": True,
            }}
        ]}}).encode()

        # Mock post body response
        post_payload = _make_post_response(
            body="NVDA earnings beat incoming. AI datacenter orders up 40% QoQ.",
            comments=["Great DD", "I'm in"],
        )

        mock_search = _mock_urlopen(search_payload)
        mock_post   = _mock_urlopen(post_payload)

        call_count = [0]
        def side_effect(req, timeout=None):
            call_count[0] += 1
            # First calls are search; subsequent calls are post body
            if "search.json" in req.full_url:
                return mock_search
            return mock_post

        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   side_effect=side_effect):
            result = get_reddit_sentiment("NVDA", days=7)

        assert "NVDA" in result
        # Body content should appear in output
        assert "AI datacenter" in result or "earnings beat" in result or "Body:" in result

    def test_summary_still_works_when_body_fetch_fails(self):
        """If body fetch fails, summary still returns titles-only."""
        from tradingagents.dataflows.reddit_utils import get_reddit_sentiment
        from urllib.error import URLError

        search_payload = json.dumps({"data": {"children": [
            {"data": {
                "title": "NVDA is going to the moon",
                "score": 500,
                "num_comments": 50,
                "permalink": "/r/stocks/comments/xyz/",
                "link_flair_text": "",
                "created_utc": 1711234567,
                "is_self": True,
            }}
        ]}}).encode()

        def side_effect(req, timeout=None):
            if "search.json" in req.full_url:
                return _mock_urlopen(search_payload)
            raise URLError("body fetch failed")

        with patch("tradingagents.dataflows.reddit_utils.urlopen",
                   side_effect=side_effect):
            result = get_reddit_sentiment("NVDA", days=7)

        assert "NVDA" in result
        assert "moon" in result  # title still present
