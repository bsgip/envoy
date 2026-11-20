import importlib.util
import shutil
from pathlib import Path

import pytest

from envoy.cli.erd import MARKDOWN_FILE_NAME, SVG_FILE_NAME, main

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"

# paracelsus is only installed via the "docs" extra and dot comes from graphviz (system package)
requires_paracelsus = pytest.mark.skipif(
    importlib.util.find_spec("paracelsus") is None, reason="paracelsus not installed (install the docs extra)"
)
requires_dot = pytest.mark.skipif(shutil.which("dot") is None, reason="graphviz (dot) not installed")


@requires_paracelsus
def test_erd_markdown_only(tmp_path: Path):
    assert main(["--config", str(PYPROJECT), "--output-dir", str(tmp_path), "--no-svg"]) == 0

    markdown = (tmp_path / MARKDOWN_FILE_NAME).read_text()
    assert "```mermaid" in markdown
    assert "erDiagram" in markdown
    assert "aggregator" in markdown, "Expected at least one known table to be in the diagram"
    assert not (tmp_path / SVG_FILE_NAME).exists()

    assert main(["--config", str(PYPROJECT), "--output-dir", str(tmp_path), "--no-svg", "--check"]) == 0


@requires_paracelsus
@requires_dot
def test_erd_generate_then_check(tmp_path: Path):
    args = ["--config", str(PYPROJECT), "--output-dir", str(tmp_path)]

    assert main(args) == 0

    assert "erDiagram" in (tmp_path / MARKDOWN_FILE_NAME).read_text()
    svg = (tmp_path / SVG_FILE_NAME).read_text()
    assert "<svg" in svg
    assert "envoy-erd dot source sha256:" in svg

    # Freshly generated files should pass the check
    assert main([*args, "--check"]) == 0

    # Modified files should fail the check
    (tmp_path / MARKDOWN_FILE_NAME).write_text("stale")
    assert main([*args, "--check"]) == 1


@requires_paracelsus
def test_erd_check_missing_files(tmp_path: Path):
    assert main(["--config", str(PYPROJECT), "--output-dir", str(tmp_path), "--check"]) == 1


def test_erd_missing_config(tmp_path: Path):
    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(tmp_path / "does_not_exist.toml"), "--output-dir", str(tmp_path)])
    assert exc_info.value.code != 0
