from abc import ABC, abstractmethod

class IPaymentGateway(ABC):
    @abstractmethod
    async def request_mobile_payment(self, phone_number: str, amount: float, reference: str) -> dict:
        """
        Déclenche une requête de paiement asynchrone (débit) via Mobile Money.
        Doit retourner un dictionnaire contenant au moins le 'transaction_id' et le 'status' initial.
        """
        pass
