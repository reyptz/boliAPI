import asyncio
import json
import aio_pika
import httpx
from uuid import uuid4

async def start_rabbitmq_worker(amqp_url: str = "amqp://boli_user:boli_password@127.0.0.1:5672/"):
    """
    Worker d'écoute RabbitMQ qui consomme les demandes de paiement et déclenche l'API Mobile Money.
    """
    try:
        connection = await aio_pika.connect_robust(amqp_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        queue = await channel.declare_queue("payment_requests", durable=True)
        
        async def callback(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    ride_id = payload["ride_id"]
                    amount = payload["amount"]
                    client_id = payload["client_id"]
                    
                    print(f"[RabbitMQ Worker] Consumed payment request for Ride {ride_id}, Amount: {amount} XOF")
                    
                    # Simuler la latence réseau Mobile Money (Orange Money / Wave)
                    await asyncio.sleep(2)
                    
                    # Envoyer le webhook de confirmation au backend
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://127.0.0.1:8001/api/v1/rides/webhooks/payment",
                            json={
                                "ride_id": ride_id,
                                "success": True,
                                "transaction_id": f"TX_AMQP_{uuid4().hex[:8].upper()}"
                            }
                        )
                        print(f"[RabbitMQ Worker] Webhook callback executed. Status: {response.status_code}")
                except Exception as e:
                    print(f"[RabbitMQ Worker] Error processing message: {e}")

        await queue.consume(callback)
        print("[RabbitMQ Worker] Worker is online and consuming 'payment_requests'")
        
        # Garder la connexion ouverte
        while not connection.is_closed:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"[RabbitMQ Worker] Failed to initialize worker: {e}")
