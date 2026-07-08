import asyncio
import logging
from irc_client import IRCClient

logging.basicConfig(level=logging.WARNING)

async def run_autotest():
    print("Iniciando prueba uniendo a #charlas en ChatHispano...")
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
    
    motd_done = False
    for _ in range(100):
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=3.0)
            if not motd_done and event["type"] == "status" and ("End of message of the day" in event.get("message", "") or "Fin del MOTD" in event.get("message", "")):
                print("MOTD finalizado. Entrando a #charlas...")
                await client.join("#charlas")
                motd_done = True
            elif motd_done:
                print("EVENT POST-MOTD:", event)
                if event["type"] == "join":
                    print("¡Éxito!")
                    return
        except asyncio.TimeoutError:
            if not motd_done:
                print("Timeout waiting for MOTD. Forcing join...")
                await client.join("#charlas")
                motd_done = True
            else:
                print("Timeout post MOTD")
                break

if __name__ == "__main__":
    asyncio.run(run_autotest())
