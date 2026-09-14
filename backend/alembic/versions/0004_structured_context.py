"""Add global characters and thread-local structured context."""
from alembic import op
import sqlalchemy as sa

revision = "0004_structured_context"
down_revision = "0003_adopted_summary"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_characters_name", "characters", ["name"])
    op.create_table(
        "character_facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.String(2000), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_character_facts_character_id", "character_facts", ["character_id"])
    op.create_table(
        "thread_characters",
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("character_id", sa.String(36), sa.ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("always_include", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "thread_scene_facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.String(2000), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_thread_scene_facts_thread_id", "thread_scene_facts", ["thread_id"])
    op.create_table(
        "thread_context_digests",
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_session_count", sa.Integer(), nullable=False),
        sa.Column("source_chars", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_thread_context_digests_source_hash", "thread_context_digests", ["source_hash"])

def downgrade() -> None:
    op.drop_index("ix_thread_context_digests_source_hash", table_name="thread_context_digests")
    op.drop_table("thread_context_digests")
    op.drop_index("ix_thread_scene_facts_thread_id", table_name="thread_scene_facts")
    op.drop_table("thread_scene_facts")
    op.drop_table("thread_characters")
    op.drop_index("ix_character_facts_character_id", table_name="character_facts")
    op.drop_table("character_facts")
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_table("characters")
