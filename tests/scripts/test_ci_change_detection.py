"""The CI only skips the test matrix when a PR touches nothing but docs."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.workflow_payload import read_workflow


def _diff_step() -> str:
    job = read_workflow(Path(".github/workflows/tests.yml"))["jobs"]["changes"]
    assert job["outputs"] == {"code": "${{ steps.diff.outputs.code }}"}
    step = next(step for step in job["steps"] if step.get("id") == "diff")
    assert step["env"] == {"BASE_SHA": "${{ github.event.pull_request.base.sha }}"}
    return step["run"].replace("${{ github.sha }}", "HEAD")


@pytest.mark.parametrize(
    ("paths", "code"),
    [
        (["README.md"], "false"),
        (["README.md", "assets/pic.png", "LICENSE"], "false"),
        ([".github/ISSUE_TEMPLATE/bug.yml"], "false"),
        (["README.md", "src/free_claude_code/api/app.py"], "true"),
        (["uv.lock"], "true"),
        (["pyproject.toml"], "true"),
        ([".github/workflows/tests.yml"], "true"),
        (["tests/api/test_api.py"], "true"),
        (["docs/guide.md.py"], "true"),
    ],
)
def test_only_docs_and_templates_skip_the_matrix(
    tmp_path: Path, paths: list[str], code: str
) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("the change detector is a bash step")
    fake_git = tmp_path / "git"
    fake_git.write_text('#!/bin/sh\nprintf "%s\\n" $FAKE_PATHS\n', "utf-8")
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IEXEC)
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-c", _diff_step()],
        env={
            **os.environ,
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "FAKE_PATHS": " ".join(paths),
            "BASE_SHA": "base",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text("utf-8").strip() == f"code={code}"
