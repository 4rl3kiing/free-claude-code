"""Generate GitHub Actions test matrices from the workflow's shard counts.

Besides the full matrix per suite, it prints a Linux-only matrix and one for
the other systems: the workflow runs Windows and macOS only after Linux passes.

To replay a shard locally, set PYTEST_ADDOPTS to
"--splits 5 --group 2 --splitting-algorithm=least_duration" and run the
pytest or playwright check through scripts/ci.ps1 or scripts/ci.sh.
"""

import argparse
import json

RUNNERS = {
    "Linux": "ubuntu-latest",
    "Windows": "windows-latest",
    "macOS": "macos-latest",
}
MAX_SHARDS = 256 // len(RUNNERS)


def shard_count(value: str) -> int:
    count = int(value)
    if not 1 <= count <= MAX_SHARDS:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_SHARDS}")
    return count


GATE_OS = "Linux"


def matrix(
    counts: dict[str, int], systems: tuple[str, ...] | None = None
) -> dict[str, list[dict[str, str | int]]]:
    return {
        "include": [
            {"os": os_name, "runner": runner, "shard": shard, "shards": counts[os_name]}
            for os_name, runner in RUNNERS.items()
            if systems is None or os_name in systems
            for shard in range(1, counts[os_name] + 1)
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for suite in ("pytest", "playwright"):
        for os_name in RUNNERS:
            parser.add_argument(
                f"--{suite}-{os_name.lower()}-shards", required=True, type=shard_count
            )
    args = parser.parse_args()
    for suite in ("pytest", "playwright"):
        counts = {
            os_name: getattr(args, f"{suite}_{os_name.lower()}_shards")
            for os_name in RUNNERS
        }
        others = tuple(os_name for os_name in RUNNERS if os_name != GATE_OS)
        for name, systems in (
            ("matrix", None),
            ("linux_matrix", (GATE_OS,)),
            ("other_matrix", others),
        ):
            value = json.dumps(matrix(counts, systems), separators=(",", ":"))
            print(f"{suite}_{name}={value}")


if __name__ == "__main__":
    main()
