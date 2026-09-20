import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect


def test_migracao_adiciona_e_remove_confirmacao_whatsapp():
    caminho = Path(__file__).resolve().parents[1] / "src/back_end/alembic/versions/89b5ce041a72_registra_envio_resposta_whatsapp.py"
    spec = importlib.util.spec_from_file_location("migracao_whatsapp", caminho)
    migracao = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracao)
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    Table("solicitacoes_mudanca", metadata, Column("id", Integer, primary_key=True))
    with engine.begin() as conexao:
        metadata.create_all(conexao)
        with Operations.context(MigrationContext.configure(conexao)):
            migracao.upgrade()
            colunas = {coluna["name"]: coluna for coluna in inspect(conexao).get_columns("solicitacoes_mudanca")}
            assert colunas["whatsapp_notificada_em"]["nullable"]
            migracao.downgrade()
            assert [coluna["name"] for coluna in inspect(conexao).get_columns("solicitacoes_mudanca")] == ["id"]
    engine.dispose()
