"""Generate TypeScript interfaces from Pydantic schemas.

Run: uv run python -m scripts.generate_ts

Reads pydantic models from each feature's schemas module and writes a
TypeScript file beside the matching frontend feature folder.
"""

import sys
from pathlib import Path

from pydantic2ts import generate_typescript_defs

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BIN = REPO_ROOT / "frontend" / "node_modules" / ".bin"
JSON2TS = str(FRONTEND_BIN / ("json2ts.cmd" if sys.platform == "win32" else "json2ts"))

FEATURES: dict[str, str] = {
    "app.features.import_.schemas": "frontend/src/features/import/types.ts",
    "app.features.transcription.schemas": "frontend/src/lib/transcription-types.ts",
}

_REPLACEMENT_HEADER = (
    "/* eslint-disable @typescript-eslint/no-empty-interface,"
    " @typescript-eslint/no-explicit-any */\n"
    "/**\n"
    " * Auto-generated from Pydantic schemas via backend/scripts/generate_ts.py.\n"
    " * Re-run the script after updating Pydantic models; do not edit by hand.\n"
    " */\n"
)


def _rewrite_header(output_rel: str) -> None:
    # json2ts emits a fixed disable-all banner; replace with rule-specific disables
    # so SonarQube doesn't flag the bare `/* eslint-disable */`.
    safe = (REPO_ROOT / output_rel).resolve()
    safe.relative_to(REPO_ROOT.resolve())
    lines = safe.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "*/":
            safe.write_text(_REPLACEMENT_HEADER + "".join(lines[i + 1 :]), encoding="utf-8")
            return


def generate_all() -> None:
    for module, output_rel in FEATURES.items():
        output = REPO_ROOT / output_rel
        output.parent.mkdir(parents=True, exist_ok=True)
        generate_typescript_defs(module, str(output), json2ts_cmd=JSON2TS)
        _rewrite_header(output_rel)
        print(f"wrote {output}")


if __name__ == "__main__":
    generate_all()
