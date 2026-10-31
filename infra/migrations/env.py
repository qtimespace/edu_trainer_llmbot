from alembic import context
from sqlalchemy import create_engine

from trainer.settings import get_settings


def _url() -> str:
    return context.config.get_main_option("sqlalchemy.url") or get_settings().database_url


if context.is_offline_mode():
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
