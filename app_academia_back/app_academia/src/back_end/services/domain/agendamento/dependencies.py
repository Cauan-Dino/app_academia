from .aluno_add_aula_service import StudentAddClassService
from .class_register_service import ClassRegisterService
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from back_end.services.infra.database.database import sessao_db
from back_end.services.domain.aluno.aluno_utils import PersonalClientUtils

def get_student_add_class_service(
    db: AsyncSession = Depends(sessao_db)
    ):
    personal_client_utils = PersonalClientUtils()
    return StudentAddClassService(
        db=db, 
        personal_client_utils=personal_client_utils
    )   


def get_class_register_service(
    db: AsyncSession = Depends(sessao_db)
    ):
    return ClassRegisterService(
        db=db
    )
