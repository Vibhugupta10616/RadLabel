"""Alembic environment: online migrations against DATABASE_URL."""

from alembic import context

from radlabel.db.models import Base
from radlabel.db.store import engine

with engine().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
