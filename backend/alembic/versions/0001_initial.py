"""initial Storyweave schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("projects", sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text()), sa.Column("system_prompt", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("threads", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("adoption_summary", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('considering','adopted','rejected','superseded')", name="ck_session_status"))
    op.create_table("messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("role", sa.String(20), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("model", sa.String(240)), sa.Column("metadata_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("role IN ('user','assistant','system','tool')", name="ck_message_role"))
    op.create_table("sources", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True), sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id", ondelete="SET NULL")), sa.Column("url", sa.Text(), nullable=False), sa.Column("title", sa.String(500)), sa.Column("excerpt", sa.Text()), sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("sources")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("threads")
    op.drop_table("projects")

