from fastapi import HTTPException
from back_end.services.infra.database.models import Alunos
import re

class PersonalClientUtils:
    # Permite chamar o metodo diretamente pela classe sem precisar de um objeto, ex: PersonalClientRegisterService.buscar_alunos
    @staticmethod
    def serializar_aluno(aluno: Alunos) -> dict:
        return {
            'nome': aluno.nome,
            'id': aluno.id,
            'telefone': aluno.telefone
        }
    

    # Pega a classe e passa como paramentro (cls)
    @classmethod
    def serializar_alunos(cls, alunos: list[Alunos]) -> list[dict]:
        return [
            cls.serializar_aluno(aluno)
            for aluno in alunos
        ]



    def obter_personal_id(
        self,
        access_token: dict
        ) -> int:
        """
        Pega o id do personal no access_token Se existir.
        Se não existir o id do personal dentro do payload do access_token exibe mensagem de erro
        """
        personal_id = access_token.get('id')
        if not personal_id:
            raise HTTPException(
                status_code=500,
                detail='Ocorreu um erro desconhecido!'
            )

        return personal_id



    def validacao_nome_aluno(
        self,
        nome_aluno: str
        ) -> str:
        """
        Valida e formata o nome_aluno
        Tirando espaços no inicio e final, e Retornando o nome do aluno formatado
        """
        nome_aluno = nome_aluno.strip() # remove espaços no início e no fim\

        if not nome_aluno or not re.match(r'^[A-Za-zÀ-ÿ\s]+$', nome_aluno):
            raise HTTPException(
                status_code=400,
                detail="Nome inválido"
            )

        return nome_aluno