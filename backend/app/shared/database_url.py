import re
from urllib.parse import quote, urlsplit, urlunsplit

_SUPABASE_DIRECT_HOST = re.compile(r"^db\.([a-z0-9]+)\.supabase\.co$")
_SUPABASE_POOLER_HOST = re.compile(r"^(?:aws|gcp)-\d+-[a-z0-9-]+\.pooler\.supabase\.com$")


def build_supabase_session_pooler_url(
    database_url: str,
    pooler_host: str,
    port: int = 5432,
) -> str:
    """Convert a Supabase direct URL into its IPv4-capable session-pooler form."""
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("database URL must use the postgres or postgresql scheme")
    if not parsed.hostname:
        raise ValueError("database URL must include a hostname")

    direct_match = _SUPABASE_DIRECT_HOST.fullmatch(parsed.hostname)
    if direct_match is None:
        raise ValueError("database URL must be a Supabase direct connection URL")
    if _SUPABASE_POOLER_HOST.fullmatch(pooler_host) is None:
        raise ValueError("pooler host is not a valid Supabase pooler hostname")
    if parsed.password is None:
        raise ValueError("database URL must include a password")
    if not 1 <= port <= 65535:
        raise ValueError("pooler port must be between 1 and 65535")

    project_ref = direct_match.group(1)
    username = quote(f"postgres.{project_ref}", safe=".")
    netloc = f"{username}:{parsed.password}@{pooler_host}:{port}"
    return urlunsplit(
        (
            parsed.scheme,
            netloc,
            parsed.path or "/postgres",
            parsed.query,
            parsed.fragment,
        )
    )


def prepare_github_database_url(
    database_url: str,
    pooler_host: str | None = None,
) -> str:
    """Accept a current session-pooler URI or convert the legacy direct URI."""
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("database URL must use the postgres or postgresql scheme")
    if parsed.hostname is None or parsed.password is None:
        raise ValueError("database URL must include a hostname and password")
    if _SUPABASE_POOLER_HOST.fullmatch(parsed.hostname):
        if parsed.port != 5432:
            raise ValueError("Supabase session pooler must use port 5432")
        if parsed.username is None or re.fullmatch(r"postgres\.[a-z0-9]+", parsed.username) is None:
            raise ValueError("Supabase pooler username must include the project reference")
        return database_url
    if pooler_host is None:
        raise ValueError("pooler host is required for a Supabase direct connection URL")
    return build_supabase_session_pooler_url(database_url, pooler_host)
