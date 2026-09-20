from back_end.services.infra.email.email_service import EmailService
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import TaskiqDepends
from back_end.services.infra.database.database import sessao_db

def get_email_service(
    db: AsyncSession = TaskiqDepends(sessao_db),
    ) -> EmailService:
    return EmailService(db=db)