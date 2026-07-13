import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
BATCH = ROOT / "scripts" / "research-mercari.sh"
BROWSER_BATCH = ROOT / "scripts" / "research-mercari-browser.sh"
RECOMMEND_BATCH = ROOT / "scripts" / "recommend.sh"


def test_manual_research_batch_requires_arguments() -> None:
    result = subprocess.run(
        [str(BATCH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "mercari-manual-v1" in result.stderr


def test_browser_research_batch_requires_arguments() -> None:
    result = subprocess.run(
        [str(BROWSER_BATCH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "CAPTCHA" in result.stderr


def test_recommendation_batch_requires_arguments() -> None:
    result = subprocess.run(
        [str(RECOMMEND_BATCH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "research-session-id" in result.stderr
