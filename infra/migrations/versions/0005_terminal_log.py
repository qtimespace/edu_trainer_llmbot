"""terminal screen of a student for the teacher: output chunks (with echoed input) and window sizes

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE terminal_log (id BIGSERIAL PRIMARY KEY,
                      account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                      kind TEXT NOT NULL CHECK (kind IN ('out', 'size')),
                      data BYTEA NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    op.execute("CREATE INDEX terminal_log_account_id ON terminal_log (account_id, id)")


def downgrade() -> None:
    op.execute("DROP TABLE terminal_log")
