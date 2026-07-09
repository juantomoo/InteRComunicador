import asyncio
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from irc_client import IRCClient

# Optional personal assistant module (not in public repo)
try:
    from personal import assistant as _personal_assistant
    PERSONAL_MODULE_AVAILABLE = True
    logging.info("Personal assistant module loaded.")
except ImportError:
    _personal_assistant = None  # type: ignore
    PERSONAL_MODULE_AVAILABLE = False

# Setup logging
logging.basicConfig(
    filename='irc_web_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------- CONFIGURATION HELPERS -----------------
def get_config_path() -> Path:
    config_dir = Path.home() / ".config" / "intercomunicador"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

def load_config() -> dict:
    path = get_config_path()
    new_presets = [
        # ── Redes hispanas y latinas ─────────────────────────────────────────
        {"name": "ChatHispano (España/LATAM)",  "host": "irc.chathispano.com",  "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "La red hispanohablante más grande. Miles de usuarios activos."},
        {"name": "IRC-Hispano (Español)",        "host": "irc.irc-hispano.org",  "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red clásica en español, activa desde los años 90."},
        {"name": "ChatZona (⚠ SSL caducado)",    "host": "irc.chatzona.org",      "port": 6667, "ssl": False, "verify_ssl": False,
         "description": "Red en español. Cert SSL vencido (mar 2026), usa puerto 6667 sin SSL."},
        {"name": "TuiterNet (Español)",          "host": "irc.tuiter.ovh",        "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red IRC en español activa."},
        # ── Redes internacionales con canales de Colombia/LATAM ──────────────
        {"name": "Libera.Chat (#colombia)",      "host": "irc.libera.chat",       "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red global open-source. Busca #colombia, #colombia-linux, #co."},
        {"name": "OFTC (#colombia)",             "host": "irc.oftc.net",          "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red técnica global. Canal #colombia para usuarios colombianos."},
        # ── Redes internacionales populares ─────────────────────────────────
        {"name": "MindForge",                   "host": "irc.mindforge.org",     "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red pequeña activa, buena para privacidad."},
        {"name": "SwiftIRC",                    "host": "irc.swiftirc.net",      "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red inglesa con comunidades de gaming."},
        {"name": "IRCHighway",                  "host": "irc.irchighway.net",    "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red con canales de ebooks y comunidades variadas."},
        {"name": "Rizon",                       "host": "irc.rizon.net",         "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red grande con comunidades de anime y tecnología."},
        {"name": "QuakeNet",                    "host": "irc.quakenet.org",      "port": 6667, "ssl": False, "verify_ssl": False,
         "description": "Red europea clásica para gaming. Sin SSL."},
        {"name": "Undernet",                    "host": "irc.undernet.org",      "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Una de las redes IRC más antiguas del mundo."},
        {"name": "DALnet",                      "host": "irc.dal.net",           "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Red clásica con NickServ y ChanServ integrados."},
        {"name": "EFnet",                       "host": "irc.efnet.org",         "port": 6667, "ssl": False, "verify_ssl": False,
         "description": "La red IRC original (1990). Sin registro de nicks. Sin SSL."},
        # ── Servidor personalizado ──────────────────────────────────────────
        {"name": "Personalizado",               "host": "",                      "port": 6697, "ssl": True,  "verify_ssl": False,
         "description": "Introduce tu propio servidor IRC."},
    ]
    
    default_config = {
        "presets": new_presets,
        "last_connection": {
            "preset": "ChatHispano",
            "host": "irc.chathispano.com",
            "port": 6697,
            "ssl": True,
            "verify_ssl": False,
            "nick": "InterUser",
            "username": "intercom",
            "realname": "InteRComunicador User",
            "password": "",
            "auto_login": False
        }
    }
    
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                loaded["presets"] = new_presets
                if "last_connection" not in loaded:
                    loaded["last_connection"] = default_config["last_connection"]
                return loaded
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            
    return default_config

def save_config(config: dict):
    try:
        path = get_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving config: {e}")

def get_nick_color(nick: str) -> str:
    colors = [
        "#ff79c6",  # Pink
        "#50fa7b",  # Green
        "#8be9fd",  # Cyan
        "#bd93f9",  # Purple
        "#ffb86c",  # Orange
        "#ff5555",  # Red
        "#f1fa8c",  # Yellow
        "#a9b1d6",  # Light gray
        "#bb9af3",  # Magenta
        "#9ece6a",  # Light green
        "#7dcfff",  # Light cyan
        "#e0af68"   # Ochre
    ]
    h = sum(ord(c) for c in nick)
    return colors[h % len(colors)]

# ----------------- STATE MANAGER -----------------
class AppState:
    def __init__(self):
        self.client = IRCClient()
        self.connected = False
        self.current_nick = "InterUser"
        
        # channel_users: channel -> list of (nick, prefix)
        self.channel_users: Dict[str, List[Tuple[str, str]]] = {}
        # channel_users_set: channel -> set of nicks for O(1) checks
        self.channel_users_set: Dict[str, Set[str]] = {}
        # joined_chats: list of names (Status, #channel, [PM] User)
        self.joined_chats: List[str] = ["Status"]
        # messages: tab -> list of dicts (max 300)
        self.messages: Dict[str, List[dict]] = {"Status": []}
        
        self.active_websockets: Set[WebSocket] = set()
        self.poll_task: Optional[asyncio.Task] = None
        
    def extract_verification_url(self, text: str) -> Optional[str]:
        import re
        # Match links containing 'verificar'
        match = re.search(r'(https?://[^\s]+\bverificar[^\s]+code=[^\s\?\&]+[^\s]*)', text)
        if not match:
            match = re.search(r'(https?://[^\s]*verificar[^\s]*)', text)
        if match:
            url = match.group(1)
            # Strip trailing punctuation commonly added by notices
            url = url.rstrip(').,;!?*')
            return url
        return None
        
    def add_message(self, tab: str, msg_type: str, nick: str, text: str, extra: dict = None):
        if tab not in self.messages:
            self.messages[tab] = []
        
        now = datetime.now().strftime("%H:%M:%S")
        msg = {
            "timestamp": now,
            "type": msg_type,
            "nick": nick,
            "color": get_nick_color(nick) if nick else "",
            "text": text
        }
        if extra:
            msg.update(extra)
            
        self.messages[tab].append(msg)
        if len(self.messages[tab]) > 300:
            self.messages[tab].pop(0)
            
        # Broadcast to websockets
        asyncio.create_task(self.broadcast({
            "type": "message",
            "tab": tab,
            "message": msg
        }))

    async def broadcast(self, data: dict):
        if not self.active_websockets:
            return
        payload = json.dumps(data)
        disconnected = set()
        for ws in self.active_websockets:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self.active_websockets.discard(ws)

    def start_polling(self):
        if self.poll_task is None or self.poll_task.done():
            self.poll_task = asyncio.create_task(self._poll_irc_loop())

    async def _poll_irc_loop(self):
        logging.info("Backend event loop started")
        while True:
            try:
                event = await self.client.queue.get()
                await self.process_irc_event(event)
                self.client.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Error in backend event processing: {e}")

    async def process_irc_event(self, event: dict):
        etype = event["type"]
        logging.info(f"Processing event: {etype}")
        
        if etype == "connected":
            self.connected = True
            await self.broadcast({"type": "connection_status", "connected": True})
            self.add_message("Status", "status", "", "¡Conectado exitosamente!")
            
            # Check if there is automated registration data pending on connect
            if getattr(self, "reg_on_connect_data", None):
                pwd = self.reg_on_connect_data["password"]
                email = self.reg_on_connect_data["email"]
                self.add_message("Status", "status", "", f"*** Ejecutando comando de registro para nick {self.current_nick}...")
                await self.client.register_nick(pwd, email)
                self.reg_on_connect_data = None
            
        elif etype == "disconnected":
            self.connected = False
            reason = event.get("reason", "Unknown")
            await self.broadcast({"type": "connection_status", "connected": False})
            self.add_message("Status", "status", "", f"Desconectado del servidor ({reason}).")
            self.channel_users.clear()
            self.channel_users_set.clear()
            self.joined_chats = ["Status"]
            await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
            
        elif etype == "error":
            self.add_message("Status", "error", "", event["message"])
            
        elif etype == "status":
            self.add_message("Status", "status", "", event["message"])
            url = self.extract_verification_url(event["message"])
            if url:
                logging.info(f"Verification URL detected in status: {url}")
                asyncio.create_task(self.broadcast({
                    "type": "verification_required",
                    "url": url,
                    "message": event["message"]
                }))
            
        elif etype == "my_nick":
            self.current_nick = event["nick"]
            await self.broadcast({"type": "my_nick", "nick": self.current_nick})
            
        elif etype == "msg":
            channel = event["channel"]
            nick = event["nick"]
            msg = event["message"]
            is_private = event["is_private"]
            
            # Autocreate tab if we don't have it
            if channel not in self.joined_chats:
                self.joined_chats.append(channel)
                self.messages[channel] = []
                await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
                
            self.add_message(channel, "msg", nick, msg, {"is_private": is_private})

            # ── Personal assistant hook (only when module is present) ──────────
            if PERSONAL_MODULE_AVAILABLE and is_private and _personal_assistant:
                suggestion = _personal_assistant.on_pm_received(
                    nick=nick, canal=channel, mensaje=msg
                )
                if suggestion is not None:
                    # New contact: push suggestion panel to the frontend
                    asyncio.create_task(self.broadcast({
                        "type": "personal_suggestion",
                        "nick": suggestion["nick"],
                        "resumen": suggestion["resumen"],
                        "aperturas": suggestion["aperturas"],
                        "filtros": suggestion["filtros"],
                    }))
            # ─────────────────────────────────────────────────────────────────

            url = self.extract_verification_url(msg)
            if url:
                logging.info(f"Verification URL detected in msg: {url}")
                asyncio.create_task(self.broadcast({
                    "type": "verification_required",
                    "url": url,
                    "message": msg
                }))
            
        elif etype == "join":
            channel = event["channel"]
            nick = event["nick"]
            
            if nick == self.current_nick:
                if channel not in self.joined_chats:
                    self.joined_chats.append(channel)
                    self.messages[channel] = []
                    self.channel_users[channel] = []
                    self.channel_users_set[channel] = set()
                    await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
                self.add_message(channel, "status", "", f"--> Te has unido al canal {channel}")
            else:
                if channel not in self.joined_chats:
                    self.joined_chats.append(channel)
                    self.messages[channel] = []
                    self.channel_users[channel] = []
                    self.channel_users_set[channel] = set()
                    await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
                
                # Check user list size to suppress join logs
                suppress = len(self.channel_users_set.get(channel, set())) > 50
                if not suppress:
                    self.add_message(channel, "status", "", f"--> {nick} se ha unido al canal")
                
                # O(1) check
                if channel in self.channel_users_set:
                    if nick not in self.channel_users_set[channel]:
                        self.channel_users_set[channel].add(nick)
                        self.channel_users[channel].append((nick, ""))
                        self._sort_users(channel)
                        await self.broadcast({
                            "type": "users_list",
                            "channel": channel,
                            "users": self.channel_users[channel]
                        })

        elif etype == "part":
            channel = event["channel"]
            nick = event["nick"]
            reason = event.get("reason", "")
            reason_str = f" ({reason})" if reason else ""
            
            if nick == self.current_nick:
                if channel in self.joined_chats:
                    self.joined_chats.remove(channel)
                    self.messages.pop(channel, None)
                    self.channel_users.pop(channel, None)
                    self.channel_users_set.pop(channel, None)
                    await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
            else:
                suppress = len(self.channel_users_set.get(channel, set())) > 50
                if not suppress:
                    self.add_message(channel, "status", "", f"<-- {nick} ha salido del canal{reason_str}")
                
                if channel in self.channel_users_set:
                    self.channel_users_set[channel].discard(nick)
                    self.channel_users[channel] = [u for u in self.channel_users[channel] if u[0] != nick]
                    await self.broadcast({
                        "type": "users_list",
                        "channel": channel,
                        "users": self.channel_users[channel]
                    })
                    
        elif etype == "quit":
            nick = event["nick"]
            reason = event.get("reason", "")
            reason_str = f" ({reason})" if reason else ""
            
            # Remove from all channels
            for channel in list(self.joined_chats):
                if channel == "Status" or channel.startswith("[PM]"):
                    continue
                
                user_set = self.channel_users_set.get(channel)
                if user_set and nick in user_set:
                    suppress = len(user_set) > 50
                    if not suppress:
                        self.add_message(channel, "status", "", f"<-- {nick} ha salido de la red{reason_str}")
                    user_set.discard(nick)
                    self.channel_users[channel] = [u for u in self.channel_users[channel] if u[0] != nick]
                    await self.broadcast({
                        "type": "users_list",
                        "channel": channel,
                        "users": self.channel_users[channel]
                    })
                    
            # PM Tab notify
            pm_tab = f"[PM] {nick}"
            if pm_tab in self.joined_chats:
                self.add_message(pm_tab, "status", "", f"*** {nick} se ha desconectado de la red{reason_str}")

        elif etype == "nick":
            old = event["old_nick"]
            new = event["new_nick"]
            
            # Channels nick update
            for channel in list(self.joined_chats):
                if channel == "Status" or channel.startswith("[PM]"):
                    continue
                
                if channel in self.channel_users_set and old in self.channel_users_set[channel]:
                    self.channel_users_set[channel].discard(old)
                    self.channel_users_set[channel].add(new)
                    
                    for i, (n, p) in enumerate(self.channel_users[channel]):
                        if n == old:
                            self.channel_users[channel][i] = (new, p)
                            break
                    self._sort_users(channel)
                    self.add_message(channel, "status", "", f"*** {old} es ahora conocido como {new}")
                    await self.broadcast({
                        "type": "users_list",
                        "channel": channel,
                        "users": self.channel_users[channel]
                    })
            
            # PM Tab update
            old_pm = f"[PM] {old}"
            new_pm = f"[PM] {new}"
            if old_pm in self.joined_chats:
                idx = self.joined_chats.index(old_pm)
                self.joined_chats[idx] = new_pm
                self.messages[new_pm] = self.messages.pop(old_pm, [])
                self.add_message(new_pm, "status", "", f"*** {old} es ahora conocido como {new}")
                await self.broadcast({"type": "sync_tabs", "tabs": self.joined_chats})
                
        elif etype == "topic":
            channel = event["channel"]
            topic = event["topic"]
            self.add_message(channel, "status", "", f"*** El tema del canal es: {topic}")
            await self.broadcast({
                "type": "topic",
                "channel": channel,
                "topic": topic
            })
            
        elif etype == "names":
            channel = event["channel"]
            nicks = event["nicks"]
            
            self.channel_users_set[channel] = {n[0] for n in nicks}
            self.channel_users[channel] = nicks
            self._sort_users(channel)
            
            await self.broadcast({
                "type": "users_list",
                "channel": channel,
                "users": self.channel_users[channel]
            })
            
        elif etype == "list_item":
            await self.broadcast({
                "type": "search_item",
                "channel": event["channel"],
                "users": event["users"],
                "topic": event["topic"]
            })
            
        elif etype == "list_end":
            await self.broadcast({"type": "search_end"})
            
        elif etype == "verification_cleared":
            self.add_message("Status", "status", "", "✅ ¡Verificación completada! Ya puedes chatear normalmente.")
            await self.broadcast({"type": "verification_cleared"})

        elif etype == "whois_data":
            # Accumulate WHOIS fields keyed by nick
            nick = event.get("nick", "?")
            if not hasattr(self, "_whois_cache"):
                self._whois_cache = {}
            if nick not in self._whois_cache:
                self._whois_cache[nick] = {"nick": nick}
            field = event.get("field")
            cache = self._whois_cache[nick]
            if field == "user":
                cache.update({"user": event["user"], "host": event["host"], "realname": event["realname"]})
            elif field == "server":
                cache.update({"server": event["server"], "server_info": event["info"]})
            elif field == "oper":
                cache["oper"] = event["text"]
            elif field == "idle":
                cache.update({"idle_secs": event["idle_secs"], "signon_ts": event["signon_ts"]})
            elif field == "channels":
                cache["channels"] = event["channels"]
            elif field == "account":
                cache["account"] = event["account"]
            elif field == "real_ip":
                cache["real_ip"] = event["real_ip"]

        elif etype == "whois_end":
            nick = event.get("nick", "?")
            if not hasattr(self, "_whois_cache"):
                self._whois_cache = {}
            data = self._whois_cache.pop(nick, {"nick": nick})
            await self.broadcast({"type": "whois_panel", "data": data})

    def _sort_users(self, channel: str):
        users = self.channel_users.get(channel, [])
        ops = [u for u in users if u[1] in ('@', '&', '~', '%')]
        voiced = [u for u in users if u[1] == '+']
        others = [u for u in users if not u[1]]
        
        ops.sort(key=lambda x: x[0].lower())
        voiced.sort(key=lambda x: x[0].lower())
        others.sort(key=lambda x: x[0].lower())
        
        self.channel_users[channel] = ops + voiced + others

# Create sessions manager to support multiple tabs/connections in parallel
sessions: Dict[str, AppState] = {}

def get_state(session_id: str) -> AppState:
    if not session_id or session_id == "null" or session_id == "undefined":
        session_id = "default"
    if session_id not in sessions:
        sessions[session_id] = AppState()
    return sessions[session_id]

# Fallback global state
state = get_state("default")

# FastAPI instantiation
app = FastAPI(title="InteRComunicador Web")

@app.on_event("startup")
def open_browser():
    import webbrowser
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception as e:
        logging.error(f"Error opening browser: {e}")


# Serve UI static assets
@app.get("/")
def get_index():
    return FileResponse("static/index.html")

@app.get("/style.css")
def get_css():
    return FileResponse("static/style.css")

@app.get("/app.js")
def get_js():
    return FileResponse("static/app.js")

@app.get("/api/config")
def api_get_config():
    return load_config()

@app.post("/api/config")
def api_save_config(config: dict):
    save_config(config)
    return {"status": "ok"}

@app.post("/api/shutdown")
def api_shutdown(background_tasks: BackgroundTasks):
    logging.info("Shutdown requested via web API")
    
    # Disconnect all active IRC clients
    for s_id, s in list(sessions.items()):
        if s.client and s.client.connected:
            try:
                asyncio.create_task(s.client.disconnect())
            except Exception as e:
                logging.error(f"Error disconnecting client {s_id}: {e}")
                
    def kill_server():
        import time
        import os
        import signal
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)
        
    background_tasks.add_task(kill_server)
    return {"status": "ok"}


@app.get("/api/state")
def api_get_state(session_id: str = "default"):
    s = get_state(session_id)
    return {
        "connected": s.connected,
        "current_nick": s.current_nick,
        "joined_chats": s.joined_chats,
        "messages": {tab: list(msgs) for tab, msgs in s.messages.items()},
        "channel_users": {channel: list(users) for channel, users in s.channel_users.items()}
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "default"):
    await websocket.accept()
    state = get_state(session_id)
    state.active_websockets.add(websocket)
    state.start_polling()
    
    # Send current state immediately to synchronize the new client
    await websocket.send_json({
        "type": "init",
        "connected": state.connected,
        "current_nick": state.current_nick,
        "joined_chats": state.joined_chats,
        "messages": state.messages,
        "channel_users": state.channel_users
    })
    
    try:
        while True:
            # Read messages from the frontend client
            data = await websocket.receive_json()
            action = data.get("action")
            logging.info(f"WS client action: {action}")
            
            if action == "connect":
                conn_data = data["data"]
                
                # Extract and store register on connect if present
                reg_data = conn_data.pop("register_on_connect", None)
                state.reg_on_connect_data = reg_data
                
                # Save config
                cfg = load_config()
                cfg["last_connection"] = conn_data
                save_config(cfg)
                
                # Start connection task
                # Ensure we run this in background
                asyncio.create_task(state.client.connect(
                    host=conn_data["host"],
                    port=int(conn_data["port"]),
                    use_ssl=conn_data["ssl"],
                    verify_ssl=conn_data["verify_ssl"],
                    nick=conn_data["nick"],
                    username=conn_data["username"],
                    realname=conn_data["realname"],
                    password=conn_data.get("password")
                ))
                
            elif action == "disconnect":
                asyncio.create_task(state.client.disconnect(data.get("reason", "Leaving")))
                
            elif action == "join":
                asyncio.create_task(state.client.join(data["channel"]))
                
            elif action == "part":
                asyncio.create_task(state.client.part(data["channel"], data.get("reason", "Leaving")))
                
            elif action == "close_tab":
                tab_name = data.get("tab")
                if tab_name and tab_name in state.joined_chats:
                    state.joined_chats.remove(tab_name)
                    state.messages.pop(tab_name, None)
                    await state.broadcast({"type": "sync_tabs", "tabs": state.joined_chats})
                    
            elif action == "privmsg":
                target = data["target"]
                text = data["text"]
                
                # Log own message locally
                if state.client.connected:
                    asyncio.create_task(state.client.privmsg(target, text))
                    # Record it in tab
                    tab_name = f"[PM] {target}" if not target.startswith(('#', '&')) else target
                    if tab_name not in state.joined_chats:
                        state.joined_chats.append(tab_name)
                        state.messages[tab_name] = []
                        await state.broadcast({"type": "sync_tabs", "tabs": state.joined_chats})
                    state.add_message(tab_name, "msg", state.current_nick, text)
                    
            elif action == "command":
                cmd_text = data["text"].strip()
                if cmd_text.startswith("/"):
                    parts = cmd_text.split()
                    cmd = parts[0][1:].lower()
                    args = parts[1:]
                    
                    if cmd == "join":
                        if args:
                            asyncio.create_task(state.client.join(args[0]))
                    elif cmd == "part":
                        chan = args[0] if args else data.get("active_tab")
                        if chan and chan != "Status":
                            asyncio.create_task(state.client.part(chan, " ".join(args[1:]) if len(args) > 1 else "Leaving"))
                    elif cmd == "query":
                        if args:
                            target = args[0]
                            tab_name = f"[PM] {target}"
                            if tab_name not in state.joined_chats:
                                state.joined_chats.append(tab_name)
                                state.messages[tab_name] = []
                                await state.broadcast({"type": "sync_tabs", "tabs": state.joined_chats})
                    elif cmd == "msg" and len(args) >= 2:
                        target = args[0]
                        msg = " ".join(args[1:])
                        if state.client.connected:
                            asyncio.create_task(state.client.privmsg(target, msg))
                            tab_name = f"[PM] {target}"
                            if tab_name not in state.joined_chats:
                                state.joined_chats.append(tab_name)
                                state.messages[tab_name] = []
                                await state.broadcast({"type": "sync_tabs", "tabs": state.joined_chats})
                            state.add_message(tab_name, "msg", state.current_nick, msg)
                    elif cmd == "nick" and args:
                        if state.client.connected:
                            asyncio.create_task(state.client.change_nick(args[0]))
                    elif cmd == "list":
                        pattern = args[0] if args else None
                        if state.client.connected:
                            asyncio.create_task(state.client.list_channels(pattern))
                    elif cmd == "me" and args:
                        action_text = " ".join(args)
                        chan = data.get("active_tab")
                        if chan and chan != "Status":
                            if state.client.connected:
                                asyncio.create_task(state.client.send(f"PRIVMSG {chan} :\x01ACTION {action_text}\x01"))
                                state.add_message(chan, "action", state.current_nick, action_text)
                    elif cmd == "register" and len(args) >= 2:
                        if state.client.connected:
                            asyncio.create_task(state.client.register_nick(args[0], args[1]))
                            state.add_message("Status", "status", "", f"Enviando registro de nick {state.current_nick}...")
                    elif cmd == "identify" and args:
                        if state.client.connected:
                            asyncio.create_task(state.client.identify_nick(args[0]))
                            state.add_message("Status", "status", "", "Enviando identificación...")
                    elif cmd == "verify" and args:
                        if state.client.connected:
                            asyncio.create_task(state.client.privmsg("NickServ", f"VERIFY REGISTER {state.current_nick} {args[0]}"))
                            state.add_message("Status", "status", "", "Enviando verificación a NickServ...")
                    elif cmd == "validate" and args:
                        # ChatZona / ChateaGratis anti-bot JWT validation
                        if state.client.connected:
                            token = args[0]
                            asyncio.create_task(state.client.send(f"VALIDATE {token}"))
                            state.add_message("Status", "status", "", "🔐 Enviando token de verificación al servidor...")
                    elif cmd == "captcha" and args:
                        # Alias for /validate
                        if state.client.connected:
                            token = args[0]
                            asyncio.create_task(state.client.send(f"VALIDATE {token}"))
                            state.add_message("Status", "status", "", "🔐 Enviando token de verificación al servidor...")
                    elif cmd == "whois" and args:
                        if state.client.connected:
                            asyncio.create_task(state.client.send(f"WHOIS {args[0]}"))
                            state.add_message("Status", "status", "", f"🔍 Consultando WHOIS de {args[0]}...")
                    elif cmd == "away":
                        if state.client.connected:
                            away_msg = " ".join(args) if args else "Ausente"
                            asyncio.create_task(state.client.send(f"AWAY :{away_msg}"))
                            state.add_message("Status", "status", "", f"💤 Marcado como ausente: {away_msg}")
                    elif cmd == "back":
                        if state.client.connected:
                            asyncio.create_task(state.client.send("AWAY"))
                            state.add_message("Status", "status", "", "👋 Vuelto de ausente.")
                    elif cmd == "ctcp" and len(args) >= 2:
                        if state.client.connected:
                            target = args[0]
                            ctcp_cmd = args[1].upper()
                            asyncio.create_task(state.client.send(f"PRIVMSG {target} :\x01{ctcp_cmd}\x01"))
                            state.add_message("Status", "status", "", f"📡 CTCP {ctcp_cmd} enviado a {target}")
                    elif cmd == "raw" and args:
                        if state.client.connected:
                            asyncio.create_task(state.client.send(" ".join(args)))
                    elif cmd == "clear":
                        active_tab = data.get("active_tab", "Status")
                        if active_tab in state.messages:
                            state.messages[active_tab].clear()
                            await websocket.send_json({"type": "clear", "tab": active_tab})
                            
    except WebSocketDisconnect:
        state.active_websockets.discard(websocket)
        logging.info("WebSocket disconnected")

# Main startup runner
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
