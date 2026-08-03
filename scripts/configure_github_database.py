import json
import os
from pathlib import Path

from backend.app.shared.database_url import prepare_github_database_url


def main() -> int:
    database_url = os.environ.get("TSUCHIBOT_DATABASE_URL")
    pooler_host = os.environ.get("TSUCHIBOT_DATABASE_POOLER_HOST")
    github_env = os.environ.get("GITHUB_ENV")
    if not database_url or not github_env:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "message": (
                        "TSUCHIBOT_DATABASE_URL and GITHUB_ENV are required. "
                        "TSUCHIBOT_DATABASE_POOLER_HOST is also required for legacy direct URLs."
                    ),
                }
            )
        )
        return 2

    pooler_url = prepare_github_database_url(database_url, pooler_host)
    with Path(github_env).open("a", encoding="utf-8") as env_file:
        env_file.write(f"TSUCHIBOT_DATABASE_URL={pooler_url}\n")
    print(json.dumps({"status": "configured", "connection": "supabase_session_pooler"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
