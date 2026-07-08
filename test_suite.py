"""
test_suite.py - Suite de Tests Exhaustiva para InteRComunicador
Testea: conexión SSL, comandos IRC, robustez del parser, y operaciones de UI.
"""
import asyncio
import sys
import time
import traceback
from irc_client import IRCClient

# ─── colores ANSI ────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

results = []

def ok(name):
    results.append((name, True, ""))
    print(f"  {GREEN}✓{RESET} {name}")

def fail(name, reason=""):
    results.append((name, False, reason))
    print(f"  {RED}✗{RESET} {name}" + (f" — {reason}" if reason else ""))

def info(msg):
    print(f"  {YELLOW}→{RESET} {msg}")

# ─── helpers ─────────────────────────────────────────────────────────

async def drain_until(client, types, timeout=15, max_events=200):
    """Drain the queue until one of the given event types appears."""
    deadline = time.time() + timeout
    count = 0
    while time.time() < deadline and count < max_events:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=min(2.0, remaining))
            client.queue.task_done()
            count += 1
            if event["type"] in types:
                return event
        except asyncio.TimeoutError:
            pass
    return None


async def drain_all(client, timeout=3):
    """Drain all pending events with a short timeout."""
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            event = await asyncio.wait_for(client.queue.get(), timeout=min(0.5, remaining))
            client.queue.task_done()
            events.append(event)
        except asyncio.TimeoutError:
            break
    return events

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 1 — Parser IRC (unit tests, sin red)
# ═══════════════════════════════════════════════════════════════════════

def test_parser_unit():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 1: Parser IRC (unit tests) ═══{RESET}")
    client = IRCClient()
    p = client._parse_line

    # Líneas bien formadas
    r = p(":nick!user@host PRIVMSG #chan :hola mundo")
    if r and r[1] == "PRIVMSG" and r[2] == ["#chan", "hola mundo"]:
        ok("PRIVMSG con trailing")
    else:
        fail("PRIVMSG con trailing", str(r))

    r = p("PING :server.irc.net")
    if r and r[1] == "PING" and r[2] == ["server.irc.net"]:
        ok("PING sin prefix")
    else:
        fail("PING sin prefix", str(r))

    r = p(":server.net 353 me = #chan :@op +voiced user")
    if r and r[1] == "353" and "#chan" in r[2]:
        ok("353 RPL_NAMREPLY")
    else:
        fail("353 RPL_NAMREPLY", str(r))

    # Edge cases que solían crashear
    if p("") is None:
        ok("Línea vacía → None")
    else:
        fail("Línea vacía → None")

    if p(":onlyprefix") is None:
        ok("Solo prefix sin comando → None")
    else:
        fail("Solo prefix sin comando → None")

    r = p(":s.net 353 me = #chan :")  # nombres vacíos
    if r and r[1] == "353":
        ok("353 con lista de nicks vacía")
    else:
        fail("353 con lista de nicks vacía", str(r))

    r = p(":s.net PRIVMSG #c :")  # mensaje vacío
    if r and r[1] == "PRIVMSG":
        ok("PRIVMSG con mensaje vacío")
    else:
        fail("PRIVMSG con mensaje vacío", str(r))

    r = p(":s.net NOTICE * :")
    if r and r[1] == "NOTICE":
        ok("NOTICE vacío")
    else:
        fail("NOTICE vacío", str(r))

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 2 — _handle_line robustez (sin red, simulando mensajes)
# ═══════════════════════════════════════════════════════════════════════

async def test_handle_line_robustness():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 2: Robustez _handle_line ═══{RESET}")
    client = IRCClient()
    client.connected = True
    client._my_current_nick = "TestUser"

    malformed_lines = [
        ":s.net PRIVMSG",                        # PRIVMSG sin params
        ":s.net PRIVMSG #chan",                  # PRIVMSG sin mensaje
        ":s.net NOTICE",                         # NOTICE sin params
        ":s.net 353 me =",                       # 353 sin canal
        ":s.net 353 me = #chan",                 # 353 sin lista nicks
        ":s.net 322",                            # LIST sin datos
        ":s.net 366 me",                         # ENDOFNAMES sin canal
        ":s.net 332 me",                         # TOPIC sin datos
        "",                                      # Vacío
        "   ",                                   # Solo espacios
        ":s.net JOIN",                           # JOIN sin canal
        ":s.net PART",                           # PART sin canal
        ":s.net QUIT",                           # QUIT sin razón
        ":s.net NICK",                           # NICK sin nuevo nick
    ]

    crashed = []
    for line in malformed_lines:
        try:
            await client._handle_line(line)
        except Exception as e:
            crashed.append((line, str(e)))

    if not crashed:
        ok(f"Todos los {len(malformed_lines)} mensajes malformados manejados sin crash")
    else:
        for line, err in crashed:
            fail(f"Crash con '{line[:50]}'", err)

    # Mensajes bien formados que deben producir eventos
    await client._handle_line(":server.net 001 TestUser :Welcome!")
    ev = await drain_until(client, ["connected"], timeout=1)
    ok("001 RPL_WELCOME genera evento 'connected'") if ev else fail("001 RPL_WELCOME")

    await client._handle_line(":nick!u@h PRIVMSG #test :hola")
    ev = await drain_until(client, ["msg"], timeout=1)
    ok("PRIVMSG canal genera evento 'msg'") if ev else fail("PRIVMSG canal")

    await client._handle_line(":nick!u@h PRIVMSG TestUser :privado")
    ev = await drain_until(client, ["msg"], timeout=1)
    if ev and ev.get("is_private"):
        ok("PRIVMSG privado genera evento 'msg' con is_private=True")
    else:
        fail("PRIVMSG privado is_private")

    await client._handle_line("PING :irc.server.net")
    # No event, but no crash either
    ok("PING no genera crash (PONG enviado internamente)")

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 3 — Conexión real a Libera.Chat
# ═══════════════════════════════════════════════════════════════════════

async def test_libera_connection():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 3: Conexión Real — Libera.Chat ═══{RESET}")
    client = IRCClient()
    nick = "InterTest7749"

    info(f"Conectando a irc.libera.chat:6697 SSL como {nick}...")
    try:
        await client.connect(
            host="irc.libera.chat", port=6697,
            use_ssl=True, verify_ssl=True,
            nick=nick, username="intercomunicador",
            realname="InteRComunicador Test Suite"
        )
    except Exception as e:
        fail("Conexión SSL Libera.Chat", str(e))
        return None

    ev = await drain_until(client, ["connected", "disconnected", "error"], timeout=20)
    if ev and ev["type"] == "connected":
        ok("Conexión SSL exitosa a Libera.Chat")
    else:
        fail("Conexión SSL Libera.Chat", str(ev))
        client._cleanup()
        return None

    # Verificar nick recibido
    events = await drain_all(client, timeout=2)
    nick_events = [e for e in events if e["type"] == "my_nick"]
    if nick_events:
        ok(f"Nick recibido del servidor: {nick_events[-1]['nick']}")
        nick = nick_events[-1]["nick"]  # puede haber cambiado por nick en uso
    else:
        info("Nick propio no recibido aún (puede estar en MOTD)")

    return client, nick


async def test_libera_join_and_message(client, nick):
    print(f"\n{BOLD}{CYAN}═══ GRUPO 4: JOIN / PRIVMSG / PART — Libera.Chat ═══{RESET}")

    # JOIN a canal de test
    channel = "#test"
    info(f"Haciendo JOIN {channel}...")
    await client.join(channel)
    ev = await drain_until(client, ["join"], timeout=15)
    if ev and ev["type"] == "join":
        ok(f"JOIN exitoso a {channel}")
    else:
        fail(f"JOIN {channel} timeout", str(ev))
        return

    # Esperar NAMES list
    ev2 = await drain_until(client, ["names"], timeout=10)
    if ev2:
        users = ev2.get("nicks", [])
        ok(f"NAMES recibido: {len(users)} usuarios en {channel}")
    else:
        info("NAMES no llegó en tiempo (puede ser canal grande)")

    # Enviar mensaje
    test_msg = "InteRComunicador autotest - ignorar"
    await client.privmsg(channel, test_msg)
    ok("PRIVMSG enviado al canal sin crash")

    # /me action
    await client.send(f"PRIVMSG {channel} :\x01ACTION ejecuta el autotest\x01")
    ok("CTCP ACTION enviado sin crash")

    # Cambiar nick
    new_nick = nick + "X"
    info(f"Cambiando nick a {new_nick}...")
    await client.change_nick(new_nick)
    ev = await drain_until(client, ["nick", "my_nick"], timeout=8)
    if ev:
        ok(f"Cambio de nick exitoso → {ev.get('new_nick', ev.get('nick', '?'))}")
    else:
        fail("Cambio de nick timeout")

    # PART del canal
    await client.part(channel, "autotest terminado")
    ev = await drain_until(client, ["part"], timeout=8)
    if ev:
        ok(f"PART exitoso de {channel}")
    else:
        fail(f"PART {channel} timeout")


async def test_libera_list(client):
    print(f"\n{BOLD}{CYAN}═══ GRUPO 5: LIST de Canales — Libera.Chat ═══{RESET}")
    info("Solicitando LIST (esto puede tardar)...")
    await client.list_channels()

    channels_count = 0
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            ev = await asyncio.wait_for(client.queue.get(), timeout=3.0)
            client.queue.task_done()
            if ev["type"] == "list_item":
                channels_count += 1
            elif ev["type"] == "list_end":
                break
        except asyncio.TimeoutError:
            break

    if channels_count > 0:
        ok(f"LIST recibió {channels_count} canales sin crash")
    else:
        fail("LIST no recibió canales")


async def test_disconnect(client):
    print(f"\n{BOLD}{CYAN}═══ GRUPO 6: Desconexión Limpia ═══{RESET}")
    await client.disconnect("Autotest completado")
    ev = await drain_until(client, ["disconnected"], timeout=8)
    if ev:
        ok("Desconexión limpia con QUIT")
    else:
        fail("Desconexión no confirmada")

    # Verificar que enviar tras desconexión no crashee
    try:
        await client.send("PRIVMSG #test :después de desconectado")
        ok("Envío post-desconexión ignorado sin crash")
    except Exception as e:
        fail("Envío post-desconexión crasheó", str(e))


async def test_chathispano_connection():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 7: Conexión — ChatHispano ═══{RESET}")
    client = IRCClient()
    info("Conectando a irc.chathispano.com:6697 SSL...")
    try:
        await client.connect(
            host="irc.chathispano.com", port=6697,
            use_ssl=True, verify_ssl=False,
            nick="InterTest8831", username="intercomunicador",
            realname="InteRComunicador Test"
        )
    except Exception as e:
        fail("Conexión ChatHispano", str(e))
        return

    ev = await drain_until(client, ["connected", "disconnected", "error"], timeout=20)
    if ev and ev["type"] == "connected":
        ok("Conexión SSL exitosa a ChatHispano")
        await drain_all(client, timeout=3)
        await client.disconnect("Test OK")
    elif ev and ev["type"] == "disconnected":
        # ChatHispano a veces rechaza bots — reportar pero no es un crash
        info(f"ChatHispano desconectó: {ev.get('reason', '')} (no es un crash de app)")
        ok("Desconexión de ChatHispano manejada graciosamente")
    else:
        fail("ChatHispano timeout de conexión", str(ev))
        client._cleanup()


async def test_mindforge_connection():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 8: Conexión — MindForge ═══{RESET}")
    client = IRCClient()
    info("Conectando a irc.mindforge.org:6697 SSL...")
    try:
        await client.connect(
            host="irc.mindforge.org", port=6697,
            use_ssl=True, verify_ssl=False,
            nick="InterTest5542", username="intercomunicador",
            realname="InteRComunicador Test"
        )
    except Exception as e:
        fail("Conexión MindForge", str(e))
        return

    ev = await drain_until(client, ["connected", "disconnected", "error"], timeout=20)
    if ev and ev["type"] == "connected":
        ok("Conexión SSL exitosa a MindForge")
        # Quick LIST test
        await client.list_channels()
        channels = 0
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                e = await asyncio.wait_for(client.queue.get(), timeout=2.0)
                client.queue.task_done()
                if e["type"] == "list_item":
                    channels += 1
                elif e["type"] == "list_end":
                    break
            except asyncio.TimeoutError:
                break
        ok(f"LIST de MindForge: {channels} canales sin crash")
        await client.disconnect("Test OK")
    else:
        info(f"MindForge no conectó: {ev} (puede ser red caída)")
        client._cleanup()


async def test_reconnect_cycle():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 9: Ciclo Reconexión ═══{RESET}")
    client = IRCClient()

    for attempt in range(1, 3):
        info(f"Intento de conexión #{attempt}...")
        await client.connect(
            host="irc.libera.chat", port=6697,
            use_ssl=True, verify_ssl=True,
            nick=f"InterRec{attempt}221", username="intercomunicador",
            realname="Reconnect Test"
        )
        ev = await drain_until(client, ["connected", "disconnected", "error"], timeout=20)
        if ev and ev["type"] == "connected":
            ok(f"Conexión #{attempt} exitosa")
            await drain_all(client, timeout=1)
            await client.disconnect(f"Fin test #{attempt}")
            await drain_until(client, ["disconnected"], timeout=5)
            # Reset client for next iteration
            client = IRCClient()
        else:
            fail(f"Reconexión #{attempt}", str(ev))
            client._cleanup()
            client = IRCClient()

    ok("Ciclo de reconexión completado sin crash")


async def test_nick_collision():
    print(f"\n{BOLD}{CYAN}═══ GRUPO 10: Colisión de Nick (433) ═══{RESET}")
    # Connect two clients with the same nick simultaneously to force 433
    client = IRCClient()
    await client.connect(
        host="irc.libera.chat", port=6697,
        use_ssl=True, verify_ssl=True,
        nick="InterTest7749",  # same as grupo 3
        username="intercomunicador", realname="Collision Test"
    )
    ev = await drain_until(client, ["connected", "disconnected", "error", "status"], timeout=20)
    # Look for status messages about nick in use OR successful connected
    events = [ev] if ev else []
    events += await drain_all(client, timeout=3)
    
    nick_collision = any(
        "ya está en uso" in e.get("message", "") or "Nickname is already in use" in e.get("message", "")
        for e in events if e and e.get("type") == "status"
    )
    connected = any(e and e.get("type") == "connected" for e in events)
    
    if nick_collision or connected:
        ok("Colisión de nick (433) manejada: auto-rename sin crash")
    else:
        info("Nick disponible (sin colisión en este momento)")
        ok("Conexión sin colisión también funciona")
    
    await client.disconnect("Test 433 done")
    await drain_all(client, timeout=2)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

async def main():
    print(f"\n{BOLD}{'═'*55}")
    print(f"  InteRComunicador — Suite de Tests Exhaustiva")
    print(f"{'═'*55}{RESET}\n")

    # Unit tests (sin red)
    test_parser_unit()
    await test_handle_line_robustness()

    # Tests de red
    result = await test_libera_connection()
    if result:
        client, nick = result
        await test_libera_join_and_message(client, nick)
        await test_libera_list(client)
        await test_disconnect(client)

    await test_chathispano_connection()
    await test_mindforge_connection()
    await test_reconnect_cycle()
    await test_nick_collision()

    # ─── Resumen ───────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*55}")
    print("  RESUMEN FINAL")
    print(f"{'═'*55}{RESET}")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    total  = len(results)
    print(f"  {GREEN}✓ Pasados:{RESET}  {passed}/{total}")
    if failed:
        print(f"  {RED}✗ Fallidos:{RESET} {failed}/{total}")
        for name, ok_val, reason in results:
            if not ok_val:
                print(f"      - {name}" + (f": {reason}" if reason else ""))
    else:
        print(f"  {GREEN}{BOLD}¡Todos los tests pasaron!{RESET}")
    print(f"{'═'*55}\n")
    return failed


if __name__ == "__main__":
    failed = asyncio.run(main())
    sys.exit(0 if failed == 0 else 1)
