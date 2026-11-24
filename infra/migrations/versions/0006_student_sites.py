"""student sites: the folder in the student's home served at /s/<login>/ and the publish switch (off by default)

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE group_students ADD COLUMN site_dir TEXT,
                  ADD COLUMN site_published BOOLEAN NOT NULL DEFAULT false""")


def downgrade() -> None:
    op.execute("ALTER TABLE group_students DROP COLUMN site_dir, DROP COLUMN site_published")
