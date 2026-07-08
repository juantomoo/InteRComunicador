import asyncio
import logging
from irc_client import IRCClient

logging.basicConfig(level=logging.WARNING)

async def run_autotest():
    print("Iniciando prueba listando canales en ChatHispano...")
    client = IRCClient()
    
    await client.connect(
        host="irc.chathispano.com",
        port=6697,
        use_ssl=True,
        verify_ssl=False,
        nick="InterTest999",
        username="test",
        realname="Autotest Bot"
    )
    
    # Wait 60 seconds to simulate human behavior
    print("Esperando 60 segundos...")
    await asyncio.sleep(60)
    
    print("Enviando /LIST...")
    await client.list_channels()
    
    channels = 0
    fake = 0
    for _ in range(100):
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=10.0)
            if event["type"] == "list_item":
                if "spambot" in event["topic"].lower():
                    fake += 1
                else:
                    channels += 1
                    if channels <= 5:
                        print("Canal real encontrado:", event["channel"], event["topic"])
            elif event["type"] == "list_end":
                print(f"Lista completada. Canales reales: {channels}, Fake: {fake}")
                return
        except asyncio.TimeoutError:
            print("Timeout")
            break

if __name__ == "__main__":
    asyncio.run(run_autotest())
