from back_end.services.domain.agendamento.dependencies import get_student_add_class_service
from fastapi import APIRouter, Depends, Query
from back_end.schemas.agendamento_schema import CadastrarAlunoNaAula
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.domain.agendamento.aluno_add_aula_service import StudentAddClassService


router = APIRouter(tags=['Cadastrar Aluno na Aula'])

@router.get("/buscar/aluno-nas-aulas")
async def buscar_aluno_nas_aulas(
    aluno_id: int = Query(..., gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: StudentAddClassService = Depends(get_student_add_class_service)
    ):
    return await service.buscar_aulas_do_aluno(
        aluno_id=aluno_id,
        access_token=access_token
    )


@router.post("/cadastrar/aluno-na-aula")
async def cadastrar_aluno_na_aula(
    body: CadastrarAlunoNaAula,
    access_token: dict = Depends(verificar_access_token),
    service: StudentAddClassService = Depends(get_student_add_class_service)
    ):
    return await service.cadastrar_aluno_na_aula(
        body=body,
        access_token=access_token
    )


@router.get('/buscar/alunos-na-aula')
async def buscar_alunos_na_aula(
    access_token: dict = Depends(verificar_access_token),
    service: StudentAddClassService = Depends(get_student_add_class_service),
    aula_id: int = Query(..., gt=0)
    ):
    return await service.buscar_alunos_cadastrados_na_aula(
        access_token=access_token,
        aula_id=aula_id
    )


@router.delete('/deletar/aluno-na-aula')
async def deletar_aluno_na_aula(
    access_token: dict = Depends(verificar_access_token),
    service: StudentAddClassService = Depends(get_student_add_class_service),
    aluno_id: int = Query(..., gt=0),
    aula_id: int = Query(..., gt=0)
    ):
    return await service.deletar_aluno_cadastrado_na_aula(
        access_token=access_token,
        aluno_id=aluno_id,
        aula_fixa_id=aula_id
    )