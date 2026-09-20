from back_end.services.domain.agendamento.dependencies import get_class_register_service
from fastapi import APIRouter, Depends, Path
from back_end.schemas.agendamento_schema import AgendarAula, AlterarAula
from back_end.auth.jwt_token import verificar_access_token
from back_end.services.domain.agendamento.class_register_service import ClassRegisterService
from back_end.services.infra.database.models import DiaDaSemana
from datetime import time

router = APIRouter(
    prefix='',
    tags=['Cadastrar Aula']
)

@router.post("/cadastrar-aula")
async def cadastrar_aula(
    body: AgendarAula,
    access_token: dict = Depends(verificar_access_token),
    service: ClassRegisterService = Depends(get_class_register_service)
    ):
    return await service.cadastrar_aula(
        body=body,
        access_token=access_token
    )


@router.patch("/alterar-aula/{aula_id}")
async def alterar_informacoes_da_aula(
    body: AlterarAula,
    aula_id: int = Path(gt=0),
    access_token: dict = Depends(verificar_access_token),
    service: ClassRegisterService = Depends(get_class_register_service)
    ):
    return await service.alterar_informacoes_aula(
        aula_id=aula_id,
        body=body,
        access_token=access_token
    )


@router.get("/buscar-aulas")
async def buscar_aulas(
    access_token: dict = Depends(verificar_access_token),
    dia_da_semana: DiaDaSemana | None = None,
    horario_inicio: time | None = None,
    horario_fim: time | None = None,
    service: ClassRegisterService = Depends(get_class_register_service)
    ):
    return await service.buscar_aulas(
        access_token=access_token,
        dia_da_semana=dia_da_semana,
        horario_inicio=horario_inicio,
        horario_fim=horario_fim
    )


@router.delete('/deletar-aula/{aula_id}')
async def deletar_aula(
    aula_id: int = Path(gt=0),
    service: ClassRegisterService = Depends(get_class_register_service),
    access_token: dict = Depends(verificar_access_token)
    ):
    return await service.deletar_aula(
        aula_id=aula_id,
        access_token=access_token
        )
