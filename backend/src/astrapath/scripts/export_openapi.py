import argparse
import json
from pathlib import Path

from astrapath.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the frozen OpenAPI contract")
    parser.add_argument("--output", default="docs/openapi.json")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
