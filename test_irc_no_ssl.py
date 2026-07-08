import asyncio
from irc_client import IRCClient

async def test_connect():
    client = IRCClient()
    print("Conectando a ChatZona (Port 6667, sin SSL)...")
    await client.connect(
        host="irc.chatzona.org",
        port=6667,
        use_ssl=False,
        verify_ssl=False,
        nick="InterTest123",
        username="intertest",
        realname="Test Bot"
    )
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

asyncio.run(test_connect())
