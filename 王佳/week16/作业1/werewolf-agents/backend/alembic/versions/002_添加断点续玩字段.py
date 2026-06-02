"""添加断点续玩字段 — games 表增加 round, phase, engine_state 列

Revision ID: 002
Revises: 001
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('round', sa.Integer(), nullable=False, server_default='0', comment='当前回合数'))
    op.add_column('games', sa.Column('phase', sa.String(16), nullable=True, comment='当前阶段: night / day'))
    op.add_column('games', sa.Column('engine_state', sa.JSON(), nullable=True, comment='引擎完整状态快照，用于断点续玩'))


def downgrade() -> None:
    op.drop_column('games', 'engine_state')
    op.drop_column('games', 'phase')
    op.drop_column('games', 'round')
