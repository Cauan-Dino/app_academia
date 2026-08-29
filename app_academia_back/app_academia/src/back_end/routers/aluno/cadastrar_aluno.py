from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from back_end.services.domain.aluno.aluno_command_service import AlunoCommandService
from back_end.services.domain.aluno.aluno_query_service import AlunoQueryService
from back_end.auth.jwt_token import verificar_access_token
from back_end.schemas.cadastrar_aluno import CadastrarAluno, AlterarInformacoesAluno
from back_end.services.domain.aluno.dependencies import get_personal_client_register_service, get_personal_client_query_service


router = APIRouter(prefix="/alunos", tags=["Alunos"])


@router.post("")
async def cadastrar_aluno(
    body: CadastrarAluno,
    access_token: dict = Depends(verificar_access_token),
    service: AlunoCommandService = Depends(get_personal_client_register_service),
    ):
    return await service.cadastrar_aluno(body=body, access_token=access_token)


@router.get("")
async def buscar_alunos(
    nome_aluno: str | None = None,
    access_token: dict = Depends(verificar_access_token),
    service: AlunoQueryService = Depends(get_personal_client_query_service),
    ):
    return await service.buscar_alunos(access_token=access_token, nome_aluno=nome_aluno)


@router.get("/{aluno_id}")
async def buscar_aluno(
    aluno_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: AlunoQueryService = Depends(get_personal_client_query_service),
    ):
    return await service.buscar_aluno_por_id(access_token=access_token, aluno_id=aluno_id)


@router.patch("/{aluno_id}")
async def alterar_informacoes_aluno(
    body: AlterarInformacoesAluno,
    aluno_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: AlunoCommandService = Depends(get_personal_client_register_service),
    ):
    return await service.alterar_informacoes_aluno(
        aluno_id=aluno_id,
        body=body,
        access_token=access_token,
    )


@router.delete("/{aluno_id}")
async def deletar_aluno(
    aluno_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: AlunoCommandService = Depends(get_personal_client_register_service),
    ):
    return await service.deletar_aluno(
        aluno_id=aluno_id,
        access_token=access_token,
    )
