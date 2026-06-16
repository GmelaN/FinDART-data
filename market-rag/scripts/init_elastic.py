from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.elastic_init import init_elastic


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the Elasticsearch index. Re-ingest documents afterwards.",
    )
    args = parser.parse_args()
    init_elastic(recreate=args.recreate)
