"""remove student groups / mandatory subjects; faculty can ask for a closed class to be reopened

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_curriculum_group_code'), table_name='curriculum')
    op.drop_table('curriculum')
    op.drop_index(op.f('ix_students_group_code'), table_name='students')
    op.drop_column('students', 'group_code')
    op.add_column('class_sections', sa.Column('reopen_requested_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('class_sections', 'reopen_requested_at')
    op.add_column('students', sa.Column('group_code', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_students_group_code'), 'students', ['group_code'], unique=False)
    op.create_table('curriculum',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_code', sa.String(length=20), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('is_mandatory', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('group_code', 'subject_id', name='uq_curriculum_group_subject')
    )
    op.create_index(op.f('ix_curriculum_group_code'), 'curriculum', ['group_code'], unique=False)
