"""adiciona o id da mensagem que verifica o telefone do aluno

Revision ID: a4c1e7f2b9d0
Revises: d137ac941f62
Create Date: 2026-10-08 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'a4c1e7f2b9d0'
down_revision: Union[str, Sequence[str], None] = 'd137ac941f62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('alunos', sa.Column('whatsapp_mensagem_verificacao_id', sa.String(length=128), nullable=True))
    op.create_index(
        op.f('ix_alunos_whatsapp_mensagem_verificacao_id'),
        'alunos',
        ['whatsapp_mensagem_verificacao_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_alunos_whatsapp_mensagem_verificacao_id'), table_name='alunos')
    op.drop_column('alunos', 'whatsapp_mensagem_verificacao_id')
