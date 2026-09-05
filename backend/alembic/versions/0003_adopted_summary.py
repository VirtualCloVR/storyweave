"""Enforce that adopted sessions have a non-blank summary."""
from alembic import op
import sqlalchemy as sa

revision = "0003_adopted_summary"
down_revision = "0002_source_tracking"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE sessions SET status='considering' WHERE status='adopted' AND (adoption_summary IS NULL OR length(trim(adoption_summary)) = 0)"))
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.create_check_constraint("ck_adopted_requires_summary", "status != 'adopted' OR (adoption_summary IS NOT NULL AND length(trim(adoption_summary)) > 0)")

def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_constraint("ck_adopted_requires_summary", type_="check")
