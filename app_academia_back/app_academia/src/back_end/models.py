from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, Enum, TIMESTAMP, TIME, BOOLEAN, DATE, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 1. Definindo a Base moderna
class Base(DeclarativeBase):
    pass

# 2. Definindo os modelos com Mapped e mapped_column
class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(Enum('personal', 'aluno', name="tipo_usuario"), nullable=False)
    telefone: Mapped[str] = mapped_column(String(15), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True,nullable=True, index=True)
    senha: Mapped[str] = mapped_column(String(255),nullable=False)
    personal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True) # Se for um personal, isso fica nulo. Se for um aluno, isso guarda o ID de quem o cadastrou.
    usuario_ativo: Mapped[bool] = mapped_column(default=True)
    data_cadastro: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=text('CURRENT_TIMESTAMP')
    )
    email_verificado: Mapped[bool] = mapped_column(default=False) # False = não verificou email conta não está ativa



class AgendamentoFixo(Base):
    __tablename__ = "agendamentos_fixos"

    id: Mapped[int] = mapped_column(primary_key=True)
    personal_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    aluno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    dia_da_semana: Mapped[int] = mapped_column(nullable=False)
    horario_inicio: Mapped[str] = mapped_column(TIME, nullable=False)
    horario_fim: Mapped[str] = mapped_column(TIME, nullable=False)
    status_ativo: Mapped[bool] = mapped_column(BOOLEAN, default=True)



class SolicitacaoMudanca(Base):
    __tablename__ = "solicitacoes_mudanca"

    id: Mapped[int] = mapped_column(primary_key=True)
    agendamento_fixo_id: Mapped[int] = mapped_column(ForeignKey("agendamentos_fixos.id"))
    data_original: Mapped[str] = mapped_column(DATE, nullable=False)
    data_nova: Mapped[str] = mapped_column(DATE, nullable=False)
    horario_inicio_novo: Mapped[str] = mapped_column(TIME, nullable=False)
    horario_fim_novo: Mapped[str] = mapped_column(TIME, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum('pendente', 'aprovado', 'recusado', name="status_mudanca"), 
        default='pendente'
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=text('CURRENT_TIMESTAMP')
    )

    

class EnvioSMS(Base):
    __tablename__ = 'envio_de_sms'

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id")) # Vínculo pelo ID
    telefone: Mapped[str] = mapped_column(String(15), index=True)
    codigo_sms: Mapped[int] = mapped_column()
    tentativas_erradas: Mapped[int] = mapped_column(default=0)
    data_criacao: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    bloqueado_ate: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True) # Bloqueia o usuario de pedir novos sms ate passar 1 hora
    codigo_sms_validado: Mapped[bool] = mapped_column(default=False)



class ConfirmacaoEmail(Base):
    __tablename__ = 'confirmacao_email'

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    email: Mapped[str] = mapped_column(String(100), index=True)
    token: Mapped[str] = mapped_column(String(255))  # token gerado pelo itsdangerous
    data_criacao: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    email_confirmado: Mapped[bool] = mapped_column(default=False)