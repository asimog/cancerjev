"""Job attempt fencing, reaper, and payload limits."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_attempts",
        sa.Column("attempt_token", sa.String(100), nullable=True),
    )
    op.create_index("ix_job_attempts_token", "job_attempts", ["attempt_token"], unique=True, postgresql_where=sa.text("attempt_token IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_job_attempts_token", table_name="job_attempts")
    op.drop_column("job_attempts", "attempt_token")