"""The windows' outputs joined, without what two windows both found."""

from __future__ import annotations

from voxtrama.engine.window_merge import merge_outputs


def test_lists_are_joined_in_the_windows_order() -> None:
    merged = merge_outputs(
        [
            {"key_points": [{"text": "Budget approved.", "quote": "we approve it"}]},
            {"key_points": [{"text": "Launch moves to May.", "quote": "May then"}]},
        ]
    )

    assert [p["text"] for p in merged["key_points"]] == ["Budget approved.", "Launch moves to May."]


def test_the_same_quote_twice_is_kept_once() -> None:
    merged = merge_outputs(
        [
            {"decisions": [{"text": "Ship Friday.", "quote": "We ship Friday."}]},
            {"decisions": [{"text": "Shipping on Friday.", "quote": "we ship friday"}]},
        ]
    )

    assert len(merged["decisions"]) == 1


def test_nearly_the_same_words_are_kept_once() -> None:
    merged = merge_outputs(
        [
            {
                "themes": [
                    {"title": "Hiring plan", "summary": "Two engineers join in Q3.", "quote": "a"}
                ]
            },
            {
                "themes": [
                    {"title": "Hiring plan", "summary": "Two engineers join in Q3!", "quote": "b"}
                ]
            },
        ]
    )

    assert len(merged["themes"]) == 1


def test_different_points_both_stay() -> None:
    merged = merge_outputs(
        [
            {"key_points": [{"text": "Budget approved.", "quote": "a"}]},
            {"key_points": [{"text": "Hiring freeze lifted.", "quote": "b"}]},
        ]
    )

    assert len(merged["key_points"]) == 2


def test_a_value_that_is_not_a_list_is_the_first_window_s() -> None:
    assert merge_outputs([{"title": "A", "items": []}, {"title": "B", "items": []}])["title"] == "A"
