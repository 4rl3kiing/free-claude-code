"""Request metrics stay bounded, escaped and Prometheus-shaped."""

from free_claude_code.core.metrics import (
    OVERFLOW_LABEL,
    UNKNOWN_LABEL,
    RequestMetrics,
)


def _record(metrics, model="m", outcome="success", seconds=1.0, provider="p"):
    metrics.record(
        provider_id=provider,
        model=model,
        wire_api="messages",
        outcome=outcome,
        duration_seconds=seconds,
    )


def test_counts_and_histogram_buckets_are_cumulative():
    metrics = RequestMetrics()
    _record(metrics, seconds=0.2)
    _record(metrics, seconds=3.0)
    text = metrics.render()
    labels = 'provider="p",model="m",api="messages",outcome="success"'
    assert f"fcc_requests_total{{{labels}}} 2" in text
    assert f'fcc_request_duration_seconds_bucket{{{labels},le="0.5"}} 1' in text
    assert f'fcc_request_duration_seconds_bucket{{{labels},le="5.0"}} 2' in text
    assert f'fcc_request_duration_seconds_bucket{{{labels},le="+Inf"}} 2' in text
    assert f"fcc_request_duration_seconds_count{{{labels}}} 2" in text


def test_missing_route_uses_unknown_labels():
    metrics = RequestMetrics()
    metrics.record(
        provider_id=None,
        model=None,
        wire_api=None,
        outcome="failure",
        duration_seconds=0.1,
    )
    assert (UNKNOWN_LABEL, UNKNOWN_LABEL, UNKNOWN_LABEL, "failure") in (
        metrics.snapshot()
    )


def test_cardinality_is_bounded_without_losing_counts():
    metrics = RequestMetrics(max_series=3)
    for index in range(10):
        _record(metrics, model=f"model-{index}")
    snapshot = metrics.snapshot()
    assert len(snapshot) == 4
    assert sum(count for count, _ in snapshot.values()) == 10
    assert (OVERFLOW_LABEL, OVERFLOW_LABEL, "messages", "success") in snapshot


def test_label_values_are_escaped():
    metrics = RequestMetrics()
    _record(metrics, model='a"b\\c\nd')
    assert 'model="a\\"b\\\\c\\nd"' in metrics.render()


def test_negative_durations_are_clamped():
    metrics = RequestMetrics()
    _record(metrics, seconds=-5)
    assert next(iter(metrics.snapshot().values())) == (1, 0.0)
