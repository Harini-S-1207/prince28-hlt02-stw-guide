import pytest

from stw_guide.db.url import to_asyncpg_url


def test_converts_postgresql_url_to_asyncpg():
    result = to_asyncpg_url("postgresql://app_user@localhost:5432/testdb")

    assert result.startswith("postgresql+asyncpg://")
    assert "app_user@" in result


def test_preserves_existing_asyncpg_driver():
    result = to_asyncpg_url("postgresql+asyncpg://app_user@localhost/testdb")

    assert result.startswith("postgresql+asyncpg://")


@pytest.mark.parametrize(
    "driver",
    [
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    ],
)
def test_converts_supported_sync_drivers(driver):
    result = to_asyncpg_url(f"{driver}://app_user@localhost/testdb")

    assert result.startswith("postgresql+asyncpg://")


def test_converts_sslmode_require_to_ssl_require():
    result = to_asyncpg_url(
        "postgresql://app_user@localhost/testdb?sslmode=require&channel_binding=require"
    )

    assert "ssl=require" in result
    assert "sslmode" not in result
    assert "channel_binding" not in result


def test_sslmode_disable_does_not_add_ssl():
    result = to_asyncpg_url("postgresql://app_user@localhost/testdb?sslmode=disable")

    assert "ssl=" not in result
    assert "sslmode" not in result


def test_url_without_sslmode():
    result = to_asyncpg_url("postgresql://app_user@localhost/testdb")

    assert "ssl=" not in result
