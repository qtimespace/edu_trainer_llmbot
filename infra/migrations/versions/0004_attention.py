"""внимание ученика: вкладка в фокусе / окно не в фокусе / вкладка скрыта — текущее и лента переходов

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE presence ADD COLUMN attention TEXT")  # focused | blurred | hidden; пусто — не сообщали
    op.execute("""CREATE TABLE attention_log (id BIGSERIAL PRIMARY KEY,
                      account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                      state TEXT NOT NULL, at TIMESTAMPTZ NOT NULL)""")
    op.execute("CREATE INDEX attention_log_account_at ON attention_log (account_id, at)")


def downgrade() -> None:
    op.execute("DROP TABLE attention_log")
    op.execute("ALTER TABLE presence DROP COLUMN attention")
