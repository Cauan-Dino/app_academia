"""Registra o envio da resposta de reagendamento pelo WhatsApp.

Revision ID: 89b5ce041a72
Revises: 51ff27de4c24
"""

from alembic import op
import sqlalchemy as sa

revision = "89b5ce041a72"
down_revision = "51ff27de4c24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("solicitacoes_mudanca", sa.Column("whatsapp_notificada_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("solicitacoes_mudanca", "whatsapp_notificada_em")
