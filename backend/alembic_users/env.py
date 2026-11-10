from alembic import context
from logging.config import fileConfig

from app.db.base import UserBase
from app.db.session import engine_users
import app.db.user_models

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)
    
target_metadata = UserBase.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=engine_users.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    
    with engine_users.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
