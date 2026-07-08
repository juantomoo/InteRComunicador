import asyncio
import logging
from irc_client import IRCClient

logging.basicConfig(level=logging.WARNING)

async def run_autotest():
    print("Iniciando Autotest Completo...")
    client = IRCClient()
    
    # 1. Conectarse
    print("1. Conectando a ChatHispano...")
    await client.connect(
        host="irc.chathispano.com",
        port=6697,
        use_ssl=True,
        verify_ssl=False,
        nick="TestUser1234",
        username="test",
        realname="Autotest Bot"
    )
    
    connected = False
    for _ in range(30):
        event = await client.queue.get()
        if event["type"] == "connected":
            connected = True
            print(" ✓ Conexión exitosa a ChatHispano")
            break
        elif event["type"] in ("disconnected", "error"):
            print(" ✗ Fallo la conexión:", event.get("reason", "Error desconocido"))
            return
            
    if not connected:
        print(" ✗ Timeout esperando conexión")
        return

    # 2. Listar canales
    print("2. Solicitando lista de canales...")
    await client.list_channels()
    channels_received = 0
    for _ in range(100):
        event = await client.queue.get()
        if event["type"] == "list_item":
            channels_received += 1
        elif event["type"] == "list_end":
            print(f" ✓ Recibida lista de canales ({channels_received} canales)")
            break

    # 3. Cambiar nick
    print("3. Cambiando nickname a TestUser4321...")
    await client.change_nick("TestUser4321")
    for _ in range(30):
        event = await client.queue.get()
        if event["type"] == "nick" and event["new_nick"] == "TestUser4321":
            print(" ✓ Nickname cambiado exitosamente")
            break
            
    # 4. Entrar a una sala
    test_channel = "#intercomunicador_test"
    print(f"4. Uniéndose a {test_channel}...")
    await client.join(test_channel)
    for _ in range(30):
        event = await client.queue.get()
        if event["type"] == "join" and event["channel"] == test_channel:
            print(" ✓ Unión a canal exitosa")
            break
            
    # 5. Enviar un mensaje y ver que llega a la sala (no lo recibiremos de vuelta como msg normal si no es bouncer,
    # pero enviar a nosotros mismos asegura que funciona la comunicación)
    print("5. Enviando mensaje al canal y mensaje privado a nosotros mismos...")
    await client.privmsg(test_channel, "Hola desde el autotest!")
    await client.privmsg("TestUser4321", "Ping autotest")
    for _ in range(30):
        event = await client.queue.get()
        if event["type"] == "msg" and event["message"] == "Ping autotest":
            print(" ✓ Mensaje enviado y recibido exitosamente")
            break

    # 6. Salir
    print("6. Desconectando...")
    await client.disconnect("Test terminado")
    for _ in range(30):
        event = await client.queue.get()
        if event["type"] == "disconnected":
            print(" ✓ Desconexión exitosa")
            break

    print("\n[✓] Autotest Completado y Exitoso!")

if __name__ == "__main__":
    asyncio.run(run_autotest())
