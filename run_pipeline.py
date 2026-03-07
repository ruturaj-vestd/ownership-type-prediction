from __future__ import annotations

import argparse
import json

from app.pipeline import OwnershipPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ownership type pipeline")
    parser.add_argument("company_name", help="Company name to analyse")
    args = parser.parse_args()

    output = OwnershipPipeline().run(args.company_name)
    print(json.dumps(output.model_dump(), indent=2))


if __name__ == "__main__":
    main()
