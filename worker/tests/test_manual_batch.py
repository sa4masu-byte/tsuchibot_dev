import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
BATCH = ROOT / "scripts" / "explore.sh"


def run_batch(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["TSUCHIBOT_SOURCE_MODE"] = "disabled"
    return subprocess.run(
        [str(BATCH), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_manual_batch_defaults_to_incremental() -> None:
    result = run_batch()
    assert result.returncode == 0
    assert '"mode": "incremental"' in result.stdout


def test_manual_batch_rejects_unknown_mode() -> None:
    result = run_batch("unexpected")
    assert result.returncode == 2
    assert "unsupported exploration mode" in result.stderr


def test_manual_batch_requires_retry_target() -> None:
    result = run_batch("retry_failed")
    assert result.returncode == 2
    assert "requires a target run ID" in result.stderr
