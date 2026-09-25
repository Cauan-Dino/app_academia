"""Adiciona os lembretes persistentes usados nas retentativas do Taskiq."""

from alembic import op
import sqlalchemy as sa


revision = "d137ac941f62"
down_revision = "31b222254f1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lembretes_aula",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("personal_id", sa.Integer(), sa.ForeignKey("personal.id", ondelete="CASCADE"), nullable=False),
        sa.Column("aula_fixa_id", sa.Integer(), sa.ForeignKey("agendamentos_fixos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("solicitacao_id", sa.Integer(), sa.ForeignKey("solicitacoes_mudanca.id", ondelete="CASCADE"), nullable=True),
        sa.Column("chave_ocorrencia", sa.String(50), nullable=False),
        sa.Column("inicio_da_aula", sa.DateTime(), nullable=False),
        sa.Column("programado_para", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Enum("pendente", "processando", "enviado", "falhou", "cancelado"), nullable=False, server_default="pendente"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enviado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tentativas >= 0", name="ck_lembrete_tentativas"),
        sa.CheckConstraint("programado_para < inicio_da_aula", name="ck_lembrete_programacao"),
        sa.CheckConstraint("status != 'enviado' OR enviado_em IS NOT NULL", name="ck_lembrete_enviado_em"),
        sa.UniqueConstraint("personal_id", "chave_ocorrencia", name="uq_lembrete_personal_ocorrencia"),
    )
    op.create_index("ix_lembretes_aula_personal_id", "lembretes_aula", ["personal_id"])
    op.create_index("ix_lembretes_aula_aula_fixa_id", "lembretes_aula", ["aula_fixa_id"])
    op.create_index("ix_lembrete_status_programacao", "lembretes_aula", ["status", "programado_para"])


def downgrade() -> None:
    op.drop_table("lembretes_aula")
