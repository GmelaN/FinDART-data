from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres_init import init_postgres


if __name__ == "__main__":
    init_postgres()
    print("PostgreSQL schema is ready.")
