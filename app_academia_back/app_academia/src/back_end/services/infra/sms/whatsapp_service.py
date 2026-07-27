import httpx2
import os

TEMPO_EXPIRACAO_SEGUNDOS = 300
MAX_TENTATIVAS = 5
TEMPO_BLOQUEIO_HORAS = 1

class WhatsAppService:
    def __init__(self):
        self.phone_number_id =  os.getenv('PHONE_NUMBER_ID')
        self.whatsapp_token = os.getenv('WHATSAPP_TOKEN')


    async def numero_existe_no_whatsapp(self, numero_telefone: str) -> bool:
        url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/contacts"
        headers = {"Authorization": f"Bearer {self.whatsapp_token}"}
        payload = {
            'blocking': 'wait',
            'contacts': [numero_telefone],
            'force_check': True
        }
        
        # Faz uma requisição assíncrona http no endpoint da META
        async with httpx2.AsyncClient() as client:
            response = await client.post(json=payload,url=url,headers=headers)
            data = response.json()
            
            try:
                return data["contacts"][0]["status"] == "valid" # Retorna True
            except (KeyError, IndexError):
                return False


    # Envia o código de 6 digitos pro whatsapp da pessoa
    async def enviar_codigo_whatsapp(self, codigo: int, telefone: str):
        url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": telefone,  # formato: 5598999999999 (sem +, com código do país)
            "type": "template",
            "template": {
                "name": "codigo_verificacao",  # nome do template criado e aprovado
                "language": {"code": "pt_BR"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(codigo)}
                        ]
                    }
                ]
            }
        }