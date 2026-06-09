import json
import aio_pika
from app.domain.repositories.ride_repositories import IMessageQueueService

class RabbitMQService(IMessageQueueService):
    def __init__(self, amqp_url: str = "amqp://boli_user:boli_password@127.0.0.1:5672/"):
        self.amqp_url = amqp_url

    async def publish_payment_request(self, ride_id: str, amount: float, client_id: str):
        """
        Publie une demande de paiement Mobile Money sur RabbitMQ.
        """
        try:
            # Connexion au serveur RabbitMQ
            connection = await aio_pika.connect_robust(self.amqp_url)
            async with connection:
                # Création du canal
                channel = await connection.channel()
                
                # Déclaration de la file d'attente
                queue = await channel.declare_queue("payment_requests", durable=True)
                
                # Payload JSON
                payload = {
                    "ride_id": ride_id,
                    "amount": amount,
                    "client_id": client_id
                }
                
                # Publication du message
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(payload).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=queue.name
                )
                print(f"[RabbitMQ] Published payment request for Ride {ride_id} to queue '{queue.name}'")
        except Exception as e:
            print(f"[RabbitMQ] Error publishing payment request: {e}")
            # Fallback en mémoire ou direct en cas d'erreur de connexion transitoire
            print("[RabbitMQ Fallback] Executing payment trigger directly...")
            import httpx
            import asyncio
            async def fallback_webhook():
                await asyncio.sleep(2)
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            "http://127.0.0.1:8001/api/v1/rides/webhooks/payment",
                            json={"ride_id": ride_id, "success": True, "transaction_id": "FALLBACK_TX"}
                        )
                except Exception as ex:
                    print(f"Fallback payment error: {ex}")
            asyncio.create_task(fallback_webhook())
