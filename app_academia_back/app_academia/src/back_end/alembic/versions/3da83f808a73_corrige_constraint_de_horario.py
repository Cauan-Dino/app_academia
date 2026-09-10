"""corrige constraint de horario

Revision ID: 3da83f808a73
Revises: 63bdbc5db11f
Create Date: 2026-09-10 16:26:42.963881

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3da83f808a73'
down_revision: Union[str, Sequence[str], None] = '63bdbc5db11f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_solicitacao_fim_apos_inicio",
        "solicitacoes_mudanca",
        type_="check",
    )

    op.create_check_constraint(
        "ck_solicitacao_fim_apos_inicio",
        "solicitacoes_mudanca",
        "nova_data_hora_fim > nova_data_hora_inicio",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_solicitacao_fim_apos_inicio",
        "solicitacoes_mudanca",
        type_="check",
    )
    # ### end Alembic commands ###
