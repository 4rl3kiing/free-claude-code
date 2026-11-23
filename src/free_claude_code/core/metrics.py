"""Process-local request metrics rendered in Prometheus text format.

Recording is a dictionary update under a lock and happens once per finished
inference request, after delivery, so it adds no work to the streaming path.
Label cardinality is bounded because model names come from clients.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from threading import Lock

MAX_SERIES = 512
OVERFLOW_LABEL = "other"
UNKNOWN_LABEL = "unknown"
DURATION_BUCKETS_SECONDS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)

SeriesKey = tuple[str, str, str, str]


@dataclass(slots=True)
class _Series:
    count: int = 0
    duration_sum: float = 0.0
    buckets: list[int] | None = None

    def observe(self, seconds: float) -> None:
        if self.buckets is None:
            self.buckets = [0] * len(DURATION_BUCKETS_SECONDS)
        self.count += 1
        self.duration_sum += seconds
        for index, bound in enumerate(DURATION_BUCKETS_SECONDS):
            if seconds <= bound:
                self.buckets[index] += 1


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class RequestMetrics:
    """Counters and a duration histogram keyed by provider, model, API and outcome."""

    def __init__(self, *, max_series: int = MAX_SERIES) -> None:
        self._max_series = max_series
        self._lock = Lock()
        self._series: dict[SeriesKey, _Series] = {}

    def record(
        self,
        *,
        provider_id: str | None,
        model: str | None,
        wire_api: str | None,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        key: SeriesKey = (
            provider_id or UNKNOWN_LABEL,
            model or UNKNOWN_LABEL,
            wire_api or UNKNOWN_LABEL,
            outcome,
        )
        with self._lock:
            series = self._series.get(key)
            if series is None:
                if len(self._series) >= self._max_series:
                    key = (OVERFLOW_LABEL, OVERFLOW_LABEL, key[2], key[3])
                    series = self._series.get(key)
                if series is None:
                    series = self._series[key] = _Series()
            series.observe(max(duration_seconds, 0.0))

    def reset(self) -> None:
        with self._lock:
            self._series.clear()

    def snapshot(self) -> dict[SeriesKey, tuple[int, float]]:
        with self._lock:
            return {k: (s.count, s.duration_sum) for k, s in self._series.items()}

    def render(self) -> str:
        with self._lock:
            items = sorted(
                (k, s.count, s.duration_sum, list(s.buckets or ()))
                for k, s in self._series.items()
            )
        lines: list[str] = [
            "# HELP fcc_requests_total Finished inference requests.",
            "# TYPE fcc_requests_total counter",
        ]
        lines.extend(
            f"fcc_requests_total{{{_labels(key)}}} {count}"
            for key, count, _, _ in items
        )
        lines += [
            "# HELP fcc_request_duration_seconds Inference request duration.",
            "# TYPE fcc_request_duration_seconds histogram",
        ]
        for key, count, total, buckets in items:
            labels = _labels(key)
            for bound, value in zip(DURATION_BUCKETS_SECONDS, buckets, strict=False):
                lines.append(
                    f'fcc_request_duration_seconds_bucket{{{labels},le="{bound}"}} {value}'
                )
            lines.append(
                f'fcc_request_duration_seconds_bucket{{{labels},le="+Inf"}} {count}'
            )
            lines.append(f"fcc_request_duration_seconds_sum{{{labels}}} {total:.6f}")
            lines.append(f"fcc_request_duration_seconds_count{{{labels}}} {count}")
        return "\n".join(lines) + "\n"


def _labels(key: Iterable[str]) -> str:
    names = ("provider", "model", "api", "outcome")
    return ",".join(
        f'{name}="{_escape(value)}"' for name, value in zip(names, key, strict=True)
    )


REQUEST_METRICS = RequestMetrics()
