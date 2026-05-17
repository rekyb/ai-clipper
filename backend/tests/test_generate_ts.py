import subprocess
import sys
from pathlib import Path

import pytest

_FRONTEND_BIN = Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / ".bin"
_JSON2TS = _FRONTEND_BIN / ("json2ts.cmd" if sys.platform == "win32" else "json2ts")


@pytest.mark.skipif(
    not _JSON2TS.exists(),
    reason="json2ts not found in frontend/node_modules/.bin (run pnpm install in frontend/)",
)
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
