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
}


def generate_all() -> None:
    for module, output_rel in FEATURES.items():
        output = REPO_ROOT / output_rel
        output.parent.mkdir(parents=True, exist_ok=True)
        generate_typescript_defs(module, str(output), json2ts_cmd=JSON2TS)
        print(f"wrote {output}")


if __name__ == "__main__":
    generate_all()
