"""Defaults for contribution_config must match what the README documents."""
from tracker import config


def test_line_stats_is_off_unless_enabled():
    # The README documents `line_stats.enabled` as defaulting to false. It costs one extra API call
    # per commit and per open PR, so it must be opt-in.
    assert config._line_stats_cfg(None)["enabled"] is False
    assert config._line_stats_cfg({})["enabled"] is False
    assert config._line_stats_cfg({"line_stats": {}})["enabled"] is False


def test_line_stats_can_be_enabled():
    assert config._line_stats_cfg({"line_stats": {"enabled": True}})["enabled"] is True


def test_line_stats_threshold_is_passed_through():
    cfg = config._line_stats_cfg({"line_stats": {"enabled": True, "refactor_threshold": 0.25}})
    assert cfg["refactor_threshold"] == 0.25


def test_other_metrics_default_to_on_and_counted():
    for key in ("commits", "open_prs", "closed_prs", "open_issues", "closed_issues", "code_reviews"):
        assert config._metric_cfg(None, key) == {"enabled": True, "count_towards_score": True}


def test_metrics_respect_explicit_settings():
    cfg = {"closed_prs": {"enabled": True, "count_towards_score": False}, "commits": {"enabled": False}}
    assert config._metric_cfg(cfg, "closed_prs") == {"enabled": True, "count_towards_score": False}
    assert config._metric_cfg(cfg, "commits")["enabled"] is False
