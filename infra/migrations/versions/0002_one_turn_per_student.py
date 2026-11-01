"""один ход тьютора на ученика одновременно: параллельные ходы по разным заданиям не превышают лимит расходов

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX agent_jobs_one_running_student ON agent_jobs (student_id)"
               " WHERE status = 'running' AND task_id IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX agent_jobs_one_running_student")
