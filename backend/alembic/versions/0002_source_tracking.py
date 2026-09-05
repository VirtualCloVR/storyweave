"""Track whether a source came from search or direct fetch."""
from alembic import op
import sqlalchemy as sa

revision = "0002_source_tracking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("source_type", sa.String(20), nullable=False, server_default="fetch"))
    op.add_column("sources", sa.Column("provider", sa.String(80), nullable=True))
    op.add_column("sources", sa.Column("query", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "query")
    op.drop_column("sources", "provider")
    op.drop_column("sources", "source_type")
