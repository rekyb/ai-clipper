import subprocess
import sys
from pathlib import Path


def test_generate_ts_produces_expected_interfaces() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.generate_ts"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    output = (
        Path(__file__).parent.parent.parent
        / "frontend"
        / "src"
        / "features"
        / "import"
        / "types.ts"
    )
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    for name in (
        "VideoDocument",
        "VideoStatus",
        "VideoSource",
        "UrlImportRequest",
        "VideoListResponse",
    ):
        assert name in content, f"expected {name} interface in generated types"
    assert "sourceUrl" in content
    assert "storagePath" in content
    assert "id?:" in content or "id:" in content
