from datetime import datetime
from sqlalchemy import ForeignKey, String, Enum as SQLEnum, Time, text, UniqueConstraint, CheckConstraint, DateTime, Index, TIMESTAMP, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from back_end.services.infra.database.database import Base
from enum import Enum
from datetime import time

class DiaDaSemana(str, Enum):
    SEGUNDA = "segunda"
    TERCA = "terca"
    QUARTA = "quarta"
    QUINTA = "quinta"
    SEXTA = "sexta"
    SABADO = "sabado"
    DOMINGO = "domingo"


class Personal(Base):
    __tablename__ = "personal"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    telefone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), unique=True,nullable=True)
    senha: Mapped[str] = mapped_column(String(255),nullable=False)
    usuario_ativo: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("TRUE"))
    data_cadastro: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=text('CURRENT_TIMESTAMP'), 
        nullable=False
    )
    email_verificado: Mapped[bool] = mapped_column(default=False, nullable=False, server_default=text("FALSE")) # False = não verificou email conta não está ativa
    token_version: Mapped[int] = mapped_column(default=0, nullable=False, server_default=text("0")) # Invalida access e refresh tokens
    

class Alunos(Base):
    __tablename__ = 'alunos'
    __table_args__ = (
        UniqueConstraint( # Impede que o personal_id possa ter 2 alunos com nome iguais
            'personal_id', 
            'nome', 
            name='uq_alunos_personal_nome'
            ),

        UniqueConstraint( # Impede que o personal_id possa ter 2 alunos com telefone iguais
            'personal_id',
            'telefone',
            name='uq_alunos_personal_telefone'
        ),
        Index(
            'idx_telefone',
            'telefone'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(
        String(
            100,
            collation="utf8mb4_0900_ai_ci" # ai = accent insensitive → ignora acento || ci = case insensitive → ignora maiúsculas/minúsculas
        ),  
        nullable=False)
    telefone: Mapped[str] = mapped_column(String(15) ,nullable=False)

    personal_id: Mapped[int] = mapped_column(ForeignKey('personal.id', name="fk_personal_id"), nullable=False)

    participantes_aula_relationship: Mapped[list["ParticipanteAula"]] = relationship(
        back_populates="alunos_relationship",
        cascade="all, delete-orphan",
        passive_deletes=True # Permite o mysql executar as exclusões e não apenas o ORM
        )


class AulaFixa(Base):
    __tablename__ = "agendamentos_fixos"

    __table_args__ = (
        UniqueConstraint(
            'personal_id',
            'dia_da_semana',
            'horario_inicio',
            name="uq_aula_fixa_personal_dia_horario",
        ),

        CheckConstraint(
            'capacidade_max > 0',
            name='ck_capacidade_max',
        ),

        CheckConstraint(
            'horario_fim > horario_inicio',
            name="ck_agendamento_fixo_horarios",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    dia_da_semana: Mapped[DiaDaSemana] = mapped_column(
        SQLEnum(
            DiaDaSemana,
            name="dia_da_semana_enum",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )

    horario_inicio: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    horario_fim: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    personal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "personal.id",
            name="fk_agendamentos_fixos_personal"
            ),
        nullable=False
    )

    capacidade_max: Mapped[int] = mapped_column(
        nullable=False
    )

    participantes_aulas_relationship: Mapped[list["ParticipanteAula"]] = relationship(
        back_populates="aulas_relationship",
        cascade="all, delete-orphan",
        passive_deletes=True # Permite o mysql executar as exclusões e não apenas o ORM
        )


class ParticipanteAula(Base):
    __tablename__ = 'alunos_participantes_da_aula'

    __table_args__ = (
        UniqueConstraint(
            'aula_fixa_id',
            'aluno_id',
            name='uq_aula_fixa_aluno'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    aula_fixa_id: Mapped[int] = mapped_column(
        ForeignKey(
            'agendamentos_fixos.id', 
            ondelete='CASCADE',
            name='fk_aula_fixa_id'
            ), 
        nullable=False, 
    )

    aluno_id: Mapped[int] = mapped_column(
        ForeignKey(
            'alunos.id', 
            ondelete='CASCADE',
            name='fk_aluno_id'
            ), 
        nullable=False, 
    )

    alunos_relationship: Mapped["Alunos"] = relationship(back_populates="participantes_aula_relationship")
    aulas_relationship: Mapped["AulaFixa"] = relationship(back_populates="participantes_aulas_relationship")





class StatusSolicitacao(str, Enum):
    PENDENTE = "pendente"
    ACEITA = "aceita"
    RECUSADA = "recusada"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"


class SolicitacaoMudanca(Base):
    __tablename__ = "solicitacoes_mudanca"

    __table_args__ = (
        UniqueConstraint(
            "mensagem_externa_id",
            name="uq_solicitacao_mensagem_externa",
        ),
        CheckConstraint(
            'nova_data_hora_fim' > 'nova_data_hora_inicio',
            name='ck_solicitacao_fim_apos_inicio'
        ),
        Index(
            "ix_solicitacao_personal_status",
            "personal_id",
            "status",
        ),
        Index(
            "ix_solicitacao_expira_em",
            "expira_em",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    personal_id: Mapped[int] = mapped_column(
        ForeignKey(
            "personal.id",
            ondelete="CASCADE",
            name="fk_solicitacao_personal",
        ),
        nullable=False,
    )

    aluno_id: Mapped[int] = mapped_column(
        ForeignKey(
            "alunos.id",
            ondelete="CASCADE",
            name="fk_solicitacao_aluno",
        ),
        nullable=False,
    )

    aula_fixa_id: Mapped[int] = mapped_column(
        ForeignKey(
            "agendamentos_fixos.id",
            ondelete="CASCADE",
            name="fk_solicitacao_aula_fixa",
        ),
        nullable=False,
    )

    # Ocorrência exata da aula que o aluno deseja mudar
    data_hora_aula_original: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # Novo horário solicitado
    nova_data_hora_inicio: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    nova_data_hora_fim: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[StatusSolicitacao] = mapped_column(
        SQLEnum(
            StatusSolicitacao,
            values_callable=lambda enum: [
                item.value for item in enum
            ],
        ),
        nullable=False,
        default=StatusSolicitacao.PENDENTE,
        server_default=text("'pendente'"),
    )

    mensagem_externa_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    motivo: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    respondida_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    expira_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    personal_relationship: Mapped["Personal"] = relationship()
    aluno_relationship: Mapped["Alunos"] = relationship()
    aula_relationship: Mapped["AulaFixa"] = relationship()


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)

    personal_id: Mapped[int] = mapped_column(
        ForeignKey("personal.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    solicitacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("solicitacoes_mudanca.id", ondelete="CASCADE"),
        nullable=True,
    )

    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    mensagem: Mapped[str] = mapped_column(String(500), nullable=False)

    lida: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=text("FALSE"),
    )

    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

# class EnvioSMS(Base):
#     __tablename__ = 'envio_de_sms'

#     id: Mapped[int] = mapped_column(primary_key=True)
#     usuario_id: Mapped[int] = mapped_column(ForeignKey("personal.id")) # Vínculo pelo ID
#     telefone: Mapped[str] = mapped_column(String(15), index=True)
#     codigo_sms: Mapped[int] = mapped_column()
#     tentativas_erradas: Mapped[int] = mapped_column(default=0)
#     data_criacao: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
#     bloqueado_ate: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True) # Bloqueia o usuario de pedir novos sms ate passar 1 hora
#     codigo_sms_validado: Mapped[bool] = mapped_column(default=False)