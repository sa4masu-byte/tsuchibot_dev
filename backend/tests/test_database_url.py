from urllib.parse import urlsplit

import pytest
from backend.app.shared.database_url import build_supabase_session_pooler_url


def test_builds_supabase_session_pooler_url_without_decoding_password() -> None:
    result = build_supabase_session_pooler_url(
        "postgresql://postgres:p%40ss%3Aword@db.abcdefghijkl.supabase.co:5432/postgres"
        "?sslmode=require",
        "aws-1-ap-northeast-2.pooler.supabase.com",
    )

    parsed = urlsplit(result)
    assert parsed.hostname == "aws-1-ap-northeast-2.pooler.supabase.com"
    assert parsed.port == 5432
    assert parsed.username == "postgres.abcdefghijkl"
    assert parsed.password == "p%40ss%3Aword"
    assert parsed.path == "/postgres"
    assert parsed.query == "sslmode=require"


@pytest.mark.parametrize(
    ("database_url", "pooler_host"),
    [
        (
            "https://db.abcdefghijkl.supabase.co/postgres",
            "aws-0-us-east-1.pooler.supabase.com",
        ),
        (
            "postgresql://postgres:secret@example.com/postgres",
            "aws-0-us-east-1.pooler.supabase.com",
        ),
        (
            "postgresql://postgres@db.abcdefghijkl.supabase.co/postgres",
            "aws-0-us-east-1.pooler.supabase.com",
        ),
        (
            "postgresql://postgres:secret@db.abcdefghijkl.supabase.co/postgres",
            "example.com",
        ),
    ],
)
def test_rejects_invalid_database_or_pooler_urls(
    database_url: str,
    pooler_host: str,
) -> None:
    with pytest.raises(ValueError):
        build_supabase_session_pooler_url(database_url, pooler_host)
