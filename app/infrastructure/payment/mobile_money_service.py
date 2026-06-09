import httpx
import uuid
import logging
from app.domain.repositories.payment_gateway import IPaymentGateway

logger = logging.getLogger(__name__)

class MobileMoneyService(IPaymentGateway):
    def __init__(self, api_base_url: str, api_key: str):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key

    async def request_mobile_payment(self, phone_number: str, amount: float, reference: str) -> dict:
        """
        Implémentation de l'appel à une API Mobile Money (ex: Orange Money, Wave).
        Cette fonction déclenche l'invite de paiement (USSD Push) sur le téléphone du client.
        """
        url = f"{self.api_base_url}/v1/payments/request"
        
        payload = {
            "amount": amount,
            "currency": "XOF",
            "phone": phone_number,
            "reference": reference,
            "webhook_url": "https://api.boli.app/api/v1/rides/webhooks/payment" # URL publique du Webhook
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Simulation du délai réseau et de la réponse si l'API n'est pas configurée
        if self.api_base_url == "mock://mobilemoney":
            logger.info(f"[Mobile Money Mock] Demande de {amount} XOF envoyée au {phone_number} (Réf: {reference})")
            return {
                "transaction_id": f"TXN-{uuid.uuid4().hex[:8].upper()}",
                "status": "PENDING_USER_APPROVAL"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                return {
                    "transaction_id": data.get("transaction_id", f"TXN-{uuid.uuid4().hex[:8].upper()}"),
                    "status": data.get("status", "PENDING_USER_APPROVAL")
                }
        except httpx.HTTPError as e:
            logger.error(f"Erreur lors de l'appel à l'API Mobile Money: {e}")
            raise Exception("Le service de paiement est temporairement indisponible.")
