"""флоу заданий (этапы и переходы, один документ) и этап задания на доске

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE flow (id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1), document JSONB NOT NULL,
                                     updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    op.execute("ALTER TABLE tasks ADD COLUMN stage TEXT")  # пусто — этап выводится из статуса (curriculum/flow.py)


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN stage")
    op.execute("DROP TABLE flow")
