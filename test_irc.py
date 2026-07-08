import asyncio
from irc_client import IRCClient
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_connect():
    client = IRCClient()
    print("Conectando a ChatZona...")
    await client.connect(
        host="irc.chatzona.org",
        port=6697,
        use_ssl=True,
        verify_ssl=False,
        nick="InterTest123",
        username="intertest",
        realname="Test Bot"
    )
    
    # Wait up to 10 seconds for events
    for _ in range(20):
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=0.5)
            print("EVENTO:", event)
            if event["type"] == "connected":
                print("¡CONEXIÓN EXITOSA!")
                await client.disconnect()
                return
            elif event["type"] in ("disconnected", "error"):
                print("¡ERROR DE CONEXIÓN!")
                return
        except asyncio.TimeoutError:
            pass

    print("TIMEOUT")

if __name__ == "__main__":
    asyncio.run(test_connect())
