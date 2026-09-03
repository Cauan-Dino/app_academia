from .webhook_service import WebHook
from .whatzap_service import WhatzapService

def get_webhook_service() -> WebHook:
    return WebHook(
        whatsapp_service=WhatzapService()
    )