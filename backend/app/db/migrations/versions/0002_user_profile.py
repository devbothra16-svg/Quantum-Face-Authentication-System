"""Add company profile fields for two-step face enrollment."""

import sqlalchemy as sa
from alembic import op

revision = "0002_user_profile"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add optional profile columns so existing accounts remain valid."""
    op.add_column("users", sa.Column("full_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("employee_id", sa.String(80), nullable=True))


def downgrade() -> None:
    """Remove profile fields."""
    op.drop_column("users", "employee_id")
    op.drop_column("users", "department")
    op.drop_column("users", "full_name")
