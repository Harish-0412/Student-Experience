from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from astrapath.config import get_settings


def test_migrations_reach_phase3_without_model_drift(monkeypatch) -> None:
    database_url = (
        "sqlite:///file:astrapath_phase3_migration?"
        "mode=memory&cache=shared&uri=true"
    )
    monkeypatch.setenv("ASTRAPATH_DATABASE_URL", database_url)
    get_settings.cache_clear()
    keeper = create_engine(database_url).connect()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        keeper.close()
        get_settings.cache_clear()
