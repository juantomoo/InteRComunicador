import asyncio
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Label, Input, Button, Checkbox, Select, ListView, ListItem, RichLog, DataTable, OptionList
)
from textual.binding import Binding
from rich.text import Text

from irc_client import IRCClient

# Setup log for UI
logging.basicConfig(
    filename='irc_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Helper functions for Config
def get_config_path() -> Path:
    config_dir = Path.home() / ".config" / "intercomunicador"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

def load_config() -> dict:
    path = get_config_path()
    new_presets = [
        {"name": "ChatHispano", "host": "irc.chathispano.com", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "ChatZona", "host": "irc.chatzona.org", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "MindForge", "host": "irc.mindforge.org", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "Libera.Chat", "host": "irc.libera.chat", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "OFTC", "host": "irc.oftc.net", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "Undernet", "host": "irc.undernet.org", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "DALnet", "host": "irc.dal.net", "port": 6697, "ssl": True, "verify_ssl": False},
        {"name": "EFnet", "host": "irc.efnet.org", "port": 6667, "ssl": False, "verify_ssl": False}
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

# Helper to hash nicknames for stable colors
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

def name_to_id(name: str, prefix: str) -> str:
    # Converts a channel/query name into a safe Textual ID
    clean = "".join(c if c.isalnum() else "_" for c in name.lower())
    return f"{prefix}{clean}"


# --------------------- DIALOG SCREENS ---------------------

class JoinChannelDialog(ModalScreen[str]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Cerrar")]
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal-overlay"):
            with Container(classes="modal-dialog"):
                yield Label("Unirse a un Canal", classes="modal-title")
                yield Input(placeholder="#canal (ej. #lobby, #python)", id="channel-input")
                with Container(classes="modal-buttons"):
                    yield Button("Cancelar", id="cancel-btn", variant="error")
                    yield Button("Unirse", id="join-btn", variant="success")

    def on_mount(self) -> None:
        self.query_one("#channel-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "join-btn":
            val = self.query_one("#channel-input", Input).value.strip()
            if val:
                self.dismiss(val)
            else:
                self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.dismiss(val)
        else:
            self.dismiss(None)


class DirectMessageDialog(ModalScreen[str]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Cerrar")]
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal-overlay"):
            with Container(classes="modal-dialog"):
                yield Label("Iniciar Charla Privada", classes="modal-title")
                yield Input(placeholder="Nick del usuario", id="nick-input")
                with Container(classes="modal-buttons"):
                    yield Button("Cancelar", id="cancel-btn", variant="error")
                    yield Button("Iniciar", id="chat-btn", variant="success")

    def on_mount(self) -> None:
        self.query_one("#nick-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "chat-btn":
            val = self.query_one("#nick-input", Input).value.strip()
            if val:
                self.dismiss(val)
            else:
                self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.dismiss(val)
        else:
            self.dismiss(None)


class RegisterDialog(ModalScreen[Tuple[str, str]]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Cerrar")]
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal-overlay"):
            with Container(classes="modal-dialog"):
                yield Label("Registrar Nick con NickServ", classes="modal-title")
                yield Label("Ingresa una contraseña y correo electrónico para registrar tu nick actual en la red IRC.", classes="field-label")
                yield Input(placeholder="Contraseña segura", password=True, id="reg-password")
                yield Input(placeholder="Correo electrónico", id="reg-email")
                with Container(classes="modal-buttons"):
                    yield Button("Cancelar", id="cancel-btn", variant="error")
                    yield Button("Registrar", id="reg-btn", variant="success")

    def on_mount(self) -> None:
        self.query_one("#reg-password").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "reg-btn":
            pwd = self.query_one("#reg-password", Input).value.strip()
            email = self.query_one("#reg-email", Input).value.strip()
            if pwd and email:
                self.dismiss((pwd, email))
            else:
                self.dismiss(None)


class ChannelSearchDialog(ModalScreen[str]):
    BINDINGS = [Binding("escape", "app.pop_screen", "Cerrar")]
    
    def __init__(self, client: IRCClient):
        super().__init__()
        self.client = client
        self.all_channels: List[Tuple[str, int, str]] = []
        self._channel_set: set = set()  # Fast O(1) duplicate detection
        self._closing = False

    def compose(self) -> ComposeResult:
        with Container(classes="modal-overlay"):
            with Container(classes="channel-search-dialog"):
                yield Label("Buscar Canales Públicos", classes="modal-title")
                yield Label("Nota: Algunas redes (ej. ChatHispano) requieren esperar 60s tras conectar para buscar canales.", classes="field-label")
                yield Input(placeholder="Filtrar canales por nombre o tema...", id="search-filter")
                yield DataTable(id="channel-table")
                with Horizontal(id="dialog-footer"):
                    yield Label("Esperando listado del servidor...", id="loader-label")
                    yield Button("Cerrar", id="close-btn", variant="error")

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Canal", "Usuarios", "Tema")
        
        # Focus filter input
        self.query_one("#search-filter").focus()
        
        # Trigger list on client
        await self.client.list_channels()

    def add_channel(self, channel: str, users: int, topic: str):
        if self._closing:
            return
            
        # Ignore honeypot channels sent by networks to confuse spambots
        if "spambot" in topic.lower() or "fake channel" in topic.lower():
            return
            
        # Ignore server-wide wildcards or hidden channels marked as *
        if channel == "*":
            return
        
        # Ensure channel names are unique to prevent DuplicateKey errors
        if channel in self._channel_set:
            return
        self._channel_set.add(channel)
            
        self.all_channels.append((channel, users, topic))
        
        # Update progress label every 20 channels to prevent excessive DOM refreshes
        if len(self.all_channels) % 20 == 0:
            try:
                label = self.query_one("#loader-label", Label)
                label.update(f"Cargando: {len(self.all_channels)} canales recibidos...")
            except Exception:
                pass

    def on_list_finished(self):
        if self._closing:
            return
        
        try:
            label = self.query_one("#loader-label", Label)
            label.update(f"¡Completado! {len(self.all_channels)} canales.")
            
            # Populate the table for the first time
            self.filter_table(self.query_one("#search-filter", Input).value.strip().lower())
        except Exception as e:
            logging.exception("Error in on_list_finished")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-filter" and not self._closing:
            self.filter_table(event.value.strip().lower())

    def filter_table(self, query: str):
        if self._closing:
            return
        try:
            table = self.query_one(DataTable)
        except Exception:
            return
        
        # Use move_cursor + clear which fully resets internal key tracking
        table.clear()
        # After clear(), internal key set is reset - safe to add rows with same keys
        
        seen_keys: set = set()
        count = 0
        for channel, users, topic in self.all_channels:
            if not query or query in channel.lower() or query in topic.lower():
                # Extra guard: skip if key was somehow already added this render
                if channel in seen_keys:
                    continue
                seen_keys.add(channel)
                try:
                    table.add_row(channel, str(users), topic, key=channel)
                except Exception:
                    pass  # Never crash on duplicate key
                count += 1
                if count >= 300:  # limit to top 300 rows to prevent terminal rendering lockup
                    break

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self._closing = True
            self.dismiss(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        self._closing = True
        self.dismiss(row_key)


# --------------------- WELCOME / CONNECT SCREEN ---------------------

class WelcomeScreen(Screen[Optional[dict]]):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        presets = self.config["presets"]
        last = self.config["last_connection"]

        preset_options = [(p["name"], p["name"]) for p in presets] + [("Personalizado", "Custom")]
        
        # Find default selection index
        default_preset = last.get("preset", "Libera.Chat")
        if not any(x[1] == default_preset for x in preset_options):
            default_preset = "Custom"

        with Container(id="welcome-container"):
            with Container(id="welcome-card", classes="dialog-panel"):
                yield Label("InteRComunicador - Conexión de Chat", classes="welcome-title")
                
                with Container(classes="field-row"):
                    yield Label("Red / Servidor:", classes="field-label")
                    yield Select(preset_options, value=default_preset, id="srv-preset")
                
                with Container(classes="field-row"):
                    yield Label("Servidor (Host):", classes="field-label")
                    yield Input(value=last.get("host", ""), placeholder="irc.server.org", id="srv-host")
                
                with Container(classes="field-row"):
                    yield Label("Puerto:", classes="field-label")
                    yield Input(value=str(last.get("port", 6697)), placeholder="6697", id="srv-port")
                
                with Container(classes="field-row"):
                    yield Label("Seguridad SSL:", classes="field-label")
                    with Horizontal():
                        yield Checkbox("Usar SSL", value=last.get("ssl", True), id="srv-ssl")
                        yield Checkbox("Verificar Cert", value=last.get("verify_ssl", False), id="srv-verify-ssl")

                with Container(classes="field-row"):
                    yield Label("Nickname (Apodo):", classes="field-label")
                    yield Input(value=last.get("nick", "InterUser"), placeholder="Tu apodo", id="usr-nick")
                
                with Container(classes="field-row"):
                    yield Label("Usuario / Realname:", classes="field-label")
                    with Horizontal():
                        yield Input(value=last.get("username", "intercom"), placeholder="usuario", id="usr-name")
                        yield Input(value=last.get("realname", "InteRComunicador User"), placeholder="Nombre real", id="usr-real")

                with Container(classes="field-row"):
                    yield Label("Contraseña Nick:", classes="field-label")
                    with Horizontal():
                        yield Input(value=last.get("password", ""), placeholder="Contraseña de NickServ/SASL", password=True, id="usr-pass")
                        yield Checkbox("Guardar", value=bool(last.get("password", "")), id="usr-save-pass")

                with Container(classes="buttons-row"):
                    yield Button("Conectar", variant="primary", id="connect-btn")
                    yield Button("Registrar Nick", variant="success", id="register-btn")
                    yield Button("Salir", variant="error", id="exit-btn")

    def on_mount(self) -> None:
        self.update_preset_fields(self.query_one("#srv-preset", Select).value)
        self.query_one("#connect-btn").focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "srv-preset":
            self.update_preset_fields(event.value)

    def update_preset_fields(self, preset_name: Any):
        if preset_name == "Custom" or preset_name == Select.BLANK:
            self.query_one("#srv-host", Input).disabled = False
            self.query_one("#srv-port", Input).disabled = False
            self.query_one("#srv-ssl", Checkbox).disabled = False
            self.query_one("#srv-verify-ssl", Checkbox).disabled = False
        else:
            # Find the preset in config
            preset = next((p for p in self.config["presets"] if p["name"] == preset_name), None)
            if preset:
                host_in = self.query_one("#srv-host", Input)
                port_in = self.query_one("#srv-port", Input)
                ssl_cb = self.query_one("#srv-ssl", Checkbox)
                vssl_cb = self.query_one("#srv-verify-ssl", Checkbox)
                
                host_in.value = preset["host"]
                port_in.value = str(preset["port"])
                ssl_cb.value = preset["ssl"]
                vssl_cb.value = preset["verify_ssl"]
                
                # Make them editable even for presets so the user can tweak port or SSL
                host_in.disabled = False
                port_in.disabled = False
                ssl_cb.disabled = False
                vssl_cb.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit-btn":
            self.dismiss(None)
        elif event.button.id == "register-btn":
            # Show the register instructions / dialog
            self.app.push_screen(RegisterDialog(), self.on_register_dialog_result)
        elif event.button.id == "connect-btn":
            self.process_connect()

    def on_register_dialog_result(self, result: Optional[Tuple[str, str]]):
        if result:
            pwd, email = result
            # Prefill the registration password and save it
            self.query_one("#usr-pass", Input).value = pwd
            self.query_one("#usr-save-pass", Checkbox).value = True
            # Store in config that we want to automatically register this nick on connection
            self.config["last_connection"]["register_on_connect"] = {
                "password": pwd,
                "email": email
            }
            # Now trigger connection
            self.process_connect()

    def process_connect(self):
        nick = self.query_one("#usr-nick", Input).value.strip()
        if not nick:
            self.query_one("#usr-nick", Input).focus()
            return
            
        host = self.query_one("#srv-host", Input).value.strip()
        if not host:
            self.query_one("#srv-host", Input).focus()
            return
            
        try:
            port = int(self.query_one("#srv-port", Input).value.strip())
        except ValueError:
            self.query_one("#srv-port", Input).focus()
            return

        preset = self.query_one("#srv-preset", Select).value
        ssl_val = self.query_one("#srv-ssl", Checkbox).value
        verify_ssl = self.query_one("#srv-verify-ssl", Checkbox).value
        username = self.query_one("#usr-name", Input).value.strip()
        realname = self.query_one("#usr-real", Input).value.strip()
        
        save_pass = self.query_one("#usr-save-pass", Checkbox).value
        password = self.query_one("#usr-pass", Input).value if save_pass else ""

        # Update last connection config
        self.config["last_connection"].update({
            "preset": preset if preset != Select.BLANK else "Custom",
            "host": host,
            "port": port,
            "ssl": ssl_val,
            "verify_ssl": verify_ssl,
            "nick": nick,
            "username": username,
            "realname": realname,
            "password": password if save_pass else ""
        })
        
        # Save config file
        save_config(self.config)

        # Connect options returned to the main app
        self.dismiss({
            "host": host,
            "port": port,
            "ssl": ssl_val,
            "verify_ssl": verify_ssl,
            "nick": nick,
            "username": username,
            "realname": realname,
            "password": password if password else None,
            "register_on_connect": self.config["last_connection"].pop("register_on_connect", None)
        })


# --------------------- CHAT INPUT WITH HISTORY ---------------------

class ChatInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history: List[str] = []
        self.history_index: int = -1
        self.temp_input: str = ""

    def on_key(self, event) -> None:
        if event.key == "up":
            if self.history:
                if self.history_index == -1:
                    self.temp_input = self.value
                self.history_index = min(self.history_index + 1, len(self.history) - 1)
                self.value = self.history[len(self.history) - 1 - self.history_index]
            event.prevent_default()
        elif event.key == "down":
            if self.history_index > -1:
                self.history_index -= 1
                if self.history_index == -1:
                    self.value = self.temp_input
                else:
                    self.value = self.history[len(self.history) - 1 - self.history_index]
            event.prevent_default()

    def record_submit(self, text: str):
        if text.strip():
            # Avoid duplicate consecutive command history
            if not self.history or self.history[-1] != text:
                self.history.append(text)
            self.history_index = -1
            self.temp_input = ""
            self.value = ""


# --------------------- MAIN CHAT APP ---------------------

class InteRComunicadorApp(App):
    CSS_PATH = "intercomunicador.tcss"
    TITLE = "InteRComunicador - Cliente de Chat Global"
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir"),
        Binding("ctrl+n", "join_channel", "Unirse a Canal"),
        Binding("ctrl+p", "direct_message", "Mensaje Privado"),
        Binding("ctrl+f", "search_channels", "Buscar Canales"),
        Binding("ctrl+r", "register_nick", "Registrar Nick"),
        Binding("ctrl+w", "close_tab", "Cerrar Pestaña")
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.client = IRCClient()
        self.active_tab: str = "Status"  # Can be "Status", channel name (e.g. "#lobby"), or nick (for PMs)
        self.joined_chats: List[str] = ["Status"]
        self.chat_logs: Dict[str, RichLog] = {}
        # channel_users stores SORTED list for display; channel_users_set stores set for O(1) lookups
        self.channel_users: Dict[str, List[Tuple[str, str]]] = {} # channel -> [(nick, prefix)]
        self.channel_users_set: Dict[str, set] = {}  # channel -> {nick, ...}
        self.search_dialog: Optional[ChannelSearchDialog] = None
        self.current_nick: str = "InterUser"
        self.reg_on_connect_data: Optional[dict] = None
        self._updating_sidebar: bool = False
        self._users_update_timer = None
        self._users_dirty: bool = False  # Flag for deferred user list rebuild
        self._suppress_joinpart: bool = False  # Suppress join/part/quit log in busy channels
        self._msg_batch: List[Tuple[str, str]] = []  # (tab, markup) buffer
        self._msg_flush_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="main-layout"):
            # Left Sidebar
            with Container(id="sidebar"):
                yield Label("InteRComunicador", classes="sidebar-title")
                yield Label("[red]●[/] Desconectado", id="status-indicator", classes="status-indicator")
                yield Label("Nickname: -", id="nick-indicator", classes="status-indicator")
                
                yield Label("Salas y Chats", id="chat-list-label")
                yield ListView(id="active-chats-list")
                
                with Container(classes="sidebar-actions"):
                    yield Button("Buscar Canales (Ctrl+F)", id="btn-search", classes="sidebar-button")
                    yield Button("Unirse a Canal (Ctrl+N)", id="btn-join", classes="sidebar-button")
                    yield Button("Charla Privada (Ctrl+P)", id="btn-pm", classes="sidebar-button")
                    yield Button("Registrar Nick (Ctrl+R)", id="btn-register", classes="sidebar-button")
                    yield Button("Cerrar Pestaña (Ctrl+W)", id="btn-close-tab", classes="sidebar-button")
                    yield Button("Desconectar", id="btn-disconnect", variant="error", classes="sidebar-button")
            
            # Middle Chat Area
            with Container(id="chat-container"):
                yield Label("Status de Red", id="chat-header")
                # Container for logs that we will switch between
                yield Container(id="chat-switcher")
                
                with Container(id="input-container"):
                    yield ChatInput(placeholder="Escribe un mensaje o /help para ayuda...", id="message-input")
            
            # Right Sidebar (Users List in Channel)
            with Container(id="users-sidebar"):
                yield Label("Usuarios", id="users-list-label")
                yield OptionList(id="users-list")
                
        yield Footer()

    async def on_mount(self) -> None:
        # Hide users list initially as we are on Status tab
        self.query_one("#users-sidebar").display = False
        
        # Disable disconnect button, input, and other actions until connected
        self.query_one("#message-input", Input).disabled = True
        self.query_one("#btn-disconnect").disabled = True
        self.query_one("#btn-join").disabled = True
        self.query_one("#btn-pm").disabled = True
        self.query_one("#btn-search").disabled = True
        self.query_one("#btn-register").disabled = True

        # Initialize the Status log
        await self.create_chat_tab("Status")
        
        # Show Welcome screen to configure and connect
        self.action_show_welcome()

    def action_show_welcome(self) -> None:
        self.push_screen(WelcomeScreen(self.config), self.on_welcome_result)

    async def on_welcome_result(self, result: Optional[dict]):
        if not result:
            # User clicked Exit or cancelled, close app
            self.exit()
            return
            
        # Re-enable sidebar items that make sense
        self.query_one("#btn-disconnect").disabled = False
        self.query_one("#btn-join").disabled = False
        self.query_one("#btn-pm").disabled = False
        self.query_one("#btn-search").disabled = False
        self.query_one("#btn-register").disabled = False
        self.query_one("#message-input", Input).disabled = False

        # Status indicators
        self.query_one("#status-indicator", Label).update("[yellow]●[/] Conectando...")
        self.current_nick = result["nick"]
        self.query_one("#nick-indicator", Label).update(f"Nick: {self.current_nick}")

        # If they filled register details, save it to execute after welcome
        self.reg_on_connect_data = result.get("register_on_connect")

        # Start the async IRC connection
        self.run_worker(
            self.client.connect(
                host=result["host"],
                port=result["port"],
                use_ssl=result["ssl"],
                verify_ssl=result["verify_ssl"],
                nick=result["nick"],
                username=result["username"],
                realname=result["realname"],
                password=result["password"]
            )
        )
        
        # Start reading events from queue
        self.run_worker(self.poll_irc_events())

    async def poll_irc_events(self):
        while True:
            try:
                # Process up to 5 events before yielding to the UI
                for _ in range(5):
                    try:
                        event = await asyncio.wait_for(self.client.queue.get(), timeout=0.05)
                    except asyncio.TimeoutError:
                        break
                    try:
                        await self.handle_irc_event(event)
                    except Exception as e:
                        logging.exception(f"Error handling event: {e}")
                    self.client.queue.task_done()
                
                # Flush any buffered messages to the UI
                self._flush_msg_batch()
                
                # Always yield to let Textual render
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Error in UI queue polling: {e}")

    async def handle_irc_event(self, event: dict):
        etype = event["type"]
        
        if etype == "connected":
            self.query_one("#status-indicator", Label).update("[green]●[/] Conectado")
            
            # Check if we need to register the nick
            if self.reg_on_connect_data:
                pwd = self.reg_on_connect_data["password"]
                email = self.reg_on_connect_data["email"]
                self.log_message("Status", f"[bold #bb9af3]*** Ejecutando comando de registro para nick {self.current_nick}...[/]")
                await self.client.register_nick(pwd, email)
                self.reg_on_connect_data = None
                
        elif etype == "disconnected":
            reason = event.get("reason", "Unknown")
            self.query_one("#status-indicator", Label).update("[red]●[/] Desconectado")
            self.log_message("Status", f"[bold #f7768e]*** Desconectado del servidor ({reason}).[/]")
            self.log_message("Status", "[bold #7aa2f7]*** Escribe /connect para volver a conectarte o pulsa Ctrl+C para salir.[/]")
            
            # Reset indicators
            self.query_one("#nick-indicator", Label).update("Nick: -")
            
            # Clear user sidebar
            self.query_one("#users-list", OptionList).clear_options()
            self.query_one("#users-sidebar").display = False
            
            # Disable actions
            self.query_one("#btn-disconnect").disabled = True
            
        elif etype == "error":
            self.log_message("Status", f"[bold #f7768e]*** ERROR: {event['message']}[/]")
            
        elif etype == "status":
            self.log_message("Status", f"[#9ece6a]{event['message']}[/]")
            
        elif etype == "my_nick":
            self.current_nick = event["nick"]
            self.query_one("#nick-indicator", Label).update(f"Nick: {self.current_nick}")
            
        elif etype == "msg":
            channel = event["channel"]
            nick = event["nick"]
            msg = event["message"]
            is_private = event["is_private"]
            
            # Check if tab exists, if not create it
            if channel not in self.joined_chats:
                await self.create_chat_tab(channel, is_private=is_private)
                
            color = get_nick_color(nick)
            now = datetime.now().strftime("%H:%M:%S")
            
            if is_private:
                # Private message
                formatted = f"[#565f89][{now}][/] [bold #bb9af3]*Privado*[/] <[bold {color}]{nick}[/]> {msg}"
            else:
                # Channel message
                formatted = f"[#565f89][{now}][/] <[bold {color}]{nick}[/]> {msg}"
                
            self.log_message(channel, formatted)
            
            # Highlight sidebar item if not active
            if channel != self.active_tab:
                self.highlight_chat_tab(channel)

        elif etype == "join":
            channel = event["channel"]
            nick = event["nick"]
            now = datetime.now().strftime("%H:%M:%S")
            
            if nick == self.current_nick:
                # We joined a channel
                if channel not in self.joined_chats:
                    await self.create_chat_tab(channel)
                await self.switch_chat_tab(channel)
                self.log_message(channel, f"[#565f89][{now}][/] [#9ece6a]--> Te has unido al canal {channel}[/]")
                # Auto-suppress join/part logs for channels with 50+ users
                users_set = self.channel_users_set.get(channel, set())
                if len(users_set) > 50:
                    self._suppress_joinpart = True
            else:
                # Someone else joined
                if channel not in self.joined_chats:
                    await self.create_chat_tab(channel)
                if not self._suppress_joinpart:
                    self.log_message(channel, f"[#565f89][{now}][/] [#9ece6a]--> [bold]{nick}[/] se ha unido al canal[/]")
                
                # Add to local names using O(1) set lookup
                if channel in self.channel_users_set:
                    if nick not in self.channel_users_set[channel]:
                        self.channel_users_set[channel].add(nick)
                        self.channel_users[channel].append((nick, ""))
                        self._users_dirty = True
                    if channel == self.active_tab:
                        self.schedule_users_list_update(channel)

        elif etype == "part":
            channel = event["channel"]
            nick = event["nick"]
            reason = event.get("reason", "")
            now = datetime.now().strftime("%H:%M:%S")
            reason_str = f" ({reason})" if reason else ""
            
            if nick == self.current_nick:
                # We left the channel
                await self.remove_chat_tab(channel)
            else:
                # Someone else left
                if not self._suppress_joinpart:
                    self.log_message(channel, f"[#565f89][{now}][/] [#f7768e]<-- [bold]{nick}[/] ha salido del canal{reason_str}[/]")
                
                # Remove from local names using O(1) set
                if channel in self.channel_users_set:
                    self.channel_users_set[channel].discard(nick)
                    self.channel_users[channel] = [u for u in self.channel_users[channel] if u[0] != nick]
                    self._users_dirty = True
                    if channel == self.active_tab:
                        self.schedule_users_list_update(channel)

        elif etype == "quit":
            nick = event["nick"]
            reason = event.get("reason", "")
            now = datetime.now().strftime("%H:%M:%S")
            reason_str = f" ({reason})" if reason else ""
            
            # Remove user from all channels using O(1) set lookup
            for channel in list(self.joined_chats):
                if channel == "Status" or channel.startswith("[PM]"):
                    continue
                
                user_set = self.channel_users_set.get(channel)
                if user_set and nick in user_set:
                    if not self._suppress_joinpart:
                        self.log_message(channel, f"[#565f89][{now}][/] [#f7768e]<-- [bold]{nick}[/] ha salido de la red{reason_str}[/]")
                    user_set.discard(nick)
                    self.channel_users[channel] = [u for u in self.channel_users[channel] if u[0] != nick]
                    self._users_dirty = True
                    if channel == self.active_tab:
                        self.schedule_users_list_update(channel)
                        
            # Also notify in PM if we have a private chat open with them
            pm_tab = f"[PM] {nick}"
            if pm_tab in self.joined_chats:
                self.log_message(pm_tab, f"[#565f89][{now}][/] [#f7768e]*** [bold]{nick}[/] se ha desconectado de la red{reason_str}[/]")

        elif etype == "nick":
            old = event["old_nick"]
            new = event["new_nick"]
            now = datetime.now().strftime("%H:%M:%S")
            
            # Update local name records and log message
            for channel in list(self.joined_chats):
                if channel == "Status":
                    continue
                
                # Check if it's a channel
                if not channel.startswith("[PM]"):
                    if channel in self.channel_users:
                        for i, (nick, prefix) in enumerate(self.channel_users[channel]):
                            if nick == old:
                                self.channel_users[channel][i] = (new, prefix)
                                self.log_message(channel, f"[#565f89][{now}][/] [#bb9af3]*** [bold]{old}[/] es ahora conocido como [bold]{new}[/][/]")
                                break
                        self.channel_users[channel].sort(key=lambda x: x[0].lower())
                        if channel == self.active_tab:
                            self.schedule_users_list_update(channel)
                else:
                    # PM Tab
                    if channel == f"[PM] {old}":
                        # Rename PM tab!
                        new_pm_tab = f"[PM] {new}"
                        # Update joined chats list
                        idx = self.joined_chats.index(channel)
                        self.joined_chats[idx] = new_pm_tab
                        
                        # Swap logs
                        self.chat_logs[new_pm_tab] = self.chat_logs.pop(channel)
                        # Switch widget ID
                        log_widget = self.chat_logs[new_pm_tab]
                        old_id = name_to_id(channel, "query_")
                        new_id = name_to_id(new_pm_tab, "query_")
                        log_widget.id = new_id
                        
                        # Log message
                        self.log_message(new_pm_tab, f"[#565f89][{now}][/] [#bb9af3]*** [bold]{old}[/] es ahora conocido como [bold]{new}[/][/]")
                        
                        # Refresh sidebar
                        self.refresh_sidebar_list()
                        if self.active_tab == channel:
                            self.active_tab = new_pm_tab
                            self.query_one("#chat-header", Label).update(f"Charla Privada con {new}")

        elif etype == "topic":
            channel = event["channel"]
            topic = event["topic"]
            now = datetime.now().strftime("%H:%M:%S")
            
            self.log_message(channel, f"[#565f89][{now}][/] [#7dcfff]*** El tema del canal es: {topic}[/]")
            if channel == self.active_tab:
                self.query_one("#chat-header", Label).update(f"{channel} | Tema: {topic}")

        elif etype == "names":
            channel = event["channel"]
            nicks = event["nicks"]
            
            # Sort nicks: operators (@) and voiced (+) first, then alphabetical
            ops = [n for n in nicks if n[1] in ('@', '&', '~', '%')]
            voiced = [n for n in nicks if n[1] == '+']
            others = [n for n in nicks if not n[1]]
            
            ops.sort(key=lambda x: x[0].lower())
            voiced.sort(key=lambda x: x[0].lower())
            others.sort(key=lambda x: x[0].lower())
            
            sorted_nicks = ops + voiced + others
            self.channel_users[channel] = sorted_nicks
            self.channel_users_set[channel] = {n[0] for n in sorted_nicks}
            
            # Auto-detect busy channels and suppress join/part spam
            if len(sorted_nicks) > 50:
                self._suppress_joinpart = True
            
            if channel == self.active_tab:
                self.schedule_users_list_update(channel)

        elif etype == "list_item":
            if self.search_dialog and not self.search_dialog._closing:
                self.search_dialog.add_channel(event["channel"], event["users"], event["topic"])
                
        elif etype == "list_end":
            if self.search_dialog and not self.search_dialog._closing:
                self.search_dialog.on_list_finished()

    # --------------------- TAB MANAGEMENT ---------------------

    async def create_chat_tab(self, name: str, is_private: bool = False) -> RichLog:
        if name in self.chat_logs:
            return self.chat_logs[name]

        # Determine safe Textual ID
        prefix = "query_" if is_private or name.startswith("[PM]") else "chan_"
        if name == "Status":
            prefix = "status_"
        wid = name_to_id(name, prefix)

        # Create log widget
        log_widget = RichLog(id=wid, highlight=True, markup=True, max_lines=2000)
        self.chat_logs[name] = log_widget
        
        # Mount into content switcher container
        switcher = self.query_one("#chat-switcher")
        await switcher.mount(log_widget)
        
        # Hide all except active
        if name != self.active_tab:
            log_widget.display = False

        if name not in self.joined_chats:
            self.joined_chats.append(name)
            self.refresh_sidebar_list()
            
        return log_widget

    async def remove_chat_tab(self, name: str):
        if name == "Status":
            return # Can't remove Status log
            
        if name in self.chat_logs:
            log_widget = self.chat_logs[name]
            await log_widget.remove()
            self.chat_logs.pop(name)
            
        if name in self.joined_chats:
            self.joined_chats.remove(name)
            
        if name in self.channel_users:
            self.channel_users.pop(name)
        if name in self.channel_users_set:
            self.channel_users_set.pop(name)
            
        self.refresh_sidebar_list()
        
        # Switch back to Status
        if self.active_tab == name:
            await self.switch_chat_tab("Status")

    async def switch_chat_tab(self, name: str):
        if name not in self.joined_chats:
            return
            
        # Hide current active log
        if self.active_tab in self.chat_logs:
            self.chat_logs[self.active_tab].display = False
            
        # Set new active
        self.active_tab = name
        
        # Show new log
        if name in self.chat_logs:
            self.chat_logs[name].display = True
            # Scroll to bottom
            self.chat_logs[name].scroll_end(animate=False)

        # Update Header and User Sidebar visibility
        header = self.query_one("#chat-header", Label)
        user_sidebar = self.query_one("#users-sidebar")
        
        if name == "Status":
            header.update("Status de Red & Consola")
            user_sidebar.display = False
        elif name.startswith("[PM]"):
            user_name = name.replace("[PM] ", "")
            header.update(f"Charla Privada con {user_name}")
            user_sidebar.display = False
        else:
            # Channel
            header.update(f"{name} | Obteniendo información...")
            user_sidebar.display = True
            # Load user list
            self.update_users_list_widget(name)
            # Ask server for topic to be sure it's up to date
            if self.client.connected:
                await self.client.send(f"TOPIC {name}")

        # Update sidebar ListView selection without triggering events recursively
        self._updating_sidebar = True
        try:
            list_view = self.query_one("#active-chats-list", ListView)
            for i, item in enumerate(list_view.children):
                if getattr(item, "chat_name", None) == name:
                    list_view.index = i
                    # Remove highlight styles if it was highlighted
                    item.set_class(False, "unread-highlight")
                    break
        finally:
            self._updating_sidebar = False

    def highlight_chat_tab(self, name: str):
        list_view = self.query_one("#active-chats-list", ListView)
        for item in list_view.children:
            if getattr(item, "chat_name", None) == name:
                # Add unread message indicator/class
                item.set_class(True, "unread-highlight")
                break

    def refresh_sidebar_list(self):
        self._updating_sidebar = True
        try:
            list_view = self.query_one("#active-chats-list", ListView)
            list_view.clear()
            
            for name in self.joined_chats:
                item = ListItem(Label(name))
                setattr(item, "chat_name", name)
                list_view.append(item)
                
            # Restore selection to active_tab
            for i, item in enumerate(list_view.children):
                if getattr(item, "chat_name", None) == self.active_tab:
                    list_view.index = i
                    break
        finally:
            self._updating_sidebar = False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._updating_sidebar:
            return
        if event.list_view.id == "active-chats-list":
            if event.item:
                chat_name = getattr(event.item, "chat_name", None)
                if chat_name and chat_name != self.active_tab:
                    self.run_worker(self.switch_chat_tab(chat_name))

    def schedule_users_list_update(self, channel: str):
        if channel != self.active_tab:
            return
        if self._users_update_timer is not None:
            # Timer already running, wait for it
            return
            
        # 3-second debounce to survive high-traffic channels
        self._users_update_timer = self.set_timer(3.0, self._do_users_list_update)

    def _do_users_list_update(self):
        self._users_update_timer = None
        self.update_users_list_widget(self.active_tab)

    def update_users_list_widget(self, channel: str):
        try:
            users_list = self.query_one("#users-list", OptionList)
        except Exception:
            return
        users_list.clear_options()
        
        users = self.channel_users.get(channel, [])
        # For very large channels, only show first 200 users to prevent UI freeze
        display_users = users[:200]
        options = []
        for nick, prefix in display_users:
            prefix_color = "#3d59a1" # default
            if prefix in ('@', '&', '~'):
                prefix_color = "#e0af68" # gold/operator
            elif prefix == '+':
                prefix_color = "#9ece6a" # green/voiced
                
            label_text = f"[{prefix_color}]{prefix}[/] {nick}" if prefix else f"  {nick}"
            options.append(Text.from_markup(label_text))
            
        users_list.add_options(options)
        
        if len(users) > 200:
            users_list.add_option(Text.from_markup(f"[#565f89]... y {len(users) - 200} más[/]"))

    def log_message(self, tab: str, markup_text: str):
        """Buffer messages and flush in batches for performance."""
        self._msg_batch.append((tab, markup_text))
        # Auto-flush when buffer gets large (for non-polled callers)
        if len(self._msg_batch) > 30:
            self._flush_msg_batch()
    
    def _flush_msg_batch(self):
        """Write all buffered messages to their RichLog widgets at once."""
        if not self._msg_batch:
            return
        batch = self._msg_batch
        self._msg_batch = []
        for tab, markup_text in batch:
            if tab in self.chat_logs:
                self.chat_logs[tab].write(markup_text)
            else:
                if "Status" in self.chat_logs:
                    self.chat_logs["Status"].write(f"[{tab}] {markup_text}")

    # --------------------- USER COMMANDS & INPUT ---------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message-input":
            text = event.value.strip()
            if not text:
                return
                
            # Record in history
            event.input.record_submit(event.value)
            
            # Process command or message
            if text.startswith("/"):
                await self.process_command(text)
            else:
                await self.send_chat_message(text)

    async def send_chat_message(self, text: str):
        if not self.client.connected:
            self.log_message("Status", "[bold #f7768e]*** No estás conectado. Conéctate primero con /connect o reinicia el app.[/]")
            return
            
        if self.active_tab == "Status":
            self.log_message("Status", "[bold #e0af68]*** No puedes enviar mensajes aquí. Únete a un canal (/join #canal) o inicia una charla privada (/query usuario).[/]")
            return
            
        target = self.active_tab
        if target.startswith("[PM] "):
            target = target.replace("[PM] ", "")
            
        # Send to IRC server
        await self.client.privmsg(target, text)
        
        # Log to active window
        now = datetime.now().strftime("%H:%M:%S")
        color = get_nick_color(self.current_nick)
        self.log_message(self.active_tab, f"[#565f89][{now}][/] <[bold #7aa2f7]{self.current_nick}[/]> {text}")

    async def process_command(self, cmd_line: str):
        parts = cmd_line.split()
        cmd = parts[0][1:].lower()
        args = parts[1:]
        
        if cmd == "help":
            self.log_message(self.active_tab, "[bold #7dcfff]=== COMANDOS DISPONIBLES ===[/]")
            self.log_message(self.active_tab, "  /join #canal           - Unirse a un canal público o privado.")
            self.log_message(self.active_tab, "  /part [#canal] [rzn]   - Salir del canal actual o de uno específico.")
            self.log_message(self.active_tab, "  /query nick            - Iniciar una charla privada con un usuario.")
            self.log_message(self.active_tab, "  /msg nick mensaje      - Enviar un mensaje privado a un usuario sin abrir pestaña.")
            self.log_message(self.active_tab, "  /nick nuevo_nick       - Cambiar tu apodo en el servidor.")
            self.log_message(self.active_tab, "  /list [patrón]         - Buscar canales públicos en el servidor.")
            self.log_message(self.active_tab, "  /me acción             - Realizar una acción en el chat (ej: /me saluda).")
            self.log_message(self.active_tab, "  /register pwd email    - Registrar tu nick actual con NickServ.")
            self.log_message(self.active_tab, "  /identify pwd          - Identificarte con NickServ si ya estás registrado.")
            self.log_message(self.active_tab, "  /verify código         - Verificar tu cuenta (si lo pide el servidor al registrarte).")
            self.log_message(self.active_tab, "  /connect               - Desconectarse y volver a la pantalla de conexión.")
            self.log_message(self.active_tab, "  /quit [razón]          - Cerrar la conexión y volver a la pantalla inicial.")
            self.log_message(self.active_tab, "  /clear                 - Limpiar el log de la pestaña activa.")
            self.log_message(self.active_tab, "  /raw comando           - Enviar comando sin procesar al servidor IRC.")
            self.log_message(self.active_tab, "  /joinpart              - Activar/desactivar mensajes de entrada/salida en canales grandes.")
            self.log_message(self.active_tab, "[bold #7dcfff]============================[/]")
            
        elif cmd == "join":
            if not args:
                self.action_join_channel()
                return
            chan = args[0]
            if self.client.connected:
                await self.client.join(chan)
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "part":
            chan = args[0] if args else self.active_tab
            reason = " ".join(args[1:]) if len(args) > 1 else "Goodbye"
            
            if chan == "Status":
                self.log_message("Status", "No puedes abandonar la consola de Status.")
                return
                
            if chan.startswith("[PM] "):
                await self.remove_chat_tab(chan)
                return
                
            if self.client.connected:
                await self.client.part(chan, reason)
            else:
                await self.remove_chat_tab(chan)
                
        elif cmd == "query":
            if not args:
                self.action_direct_message()
                return
            target = args[0]
            pm_tab = f"[PM] {target}"
            await self.create_chat_tab(pm_tab, is_private=True)
            await self.switch_chat_tab(pm_tab)
            
        elif cmd == "msg":
            if len(args) < 2:
                self.log_message(self.active_tab, "Uso: /msg nick mensaje")
                return
            target = args[0]
            msg = " ".join(args[1:])
            if self.client.connected:
                await self.client.privmsg(target, msg)
                pm_tab = f"[PM] {target}"
                if pm_tab not in self.joined_chats:
                    await self.create_chat_tab(pm_tab, is_private=True)
                now = datetime.now().strftime("%H:%M:%S")
                self.log_message(pm_tab, f"[#565f89][{now}][/] <[bold #7aa2f7]{self.current_nick}[/]> {msg}")
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "nick":
            if not args:
                self.log_message(self.active_tab, "Uso: /nick nuevo_apodo")
                return
            new_nick = args[0]
            if self.client.connected:
                await self.client.change_nick(new_nick)
            else:
                self.current_nick = new_nick
                self.query_one("#nick-indicator", Label).update(f"Nick: {self.current_nick}")
                
        elif cmd == "list":
            pattern = args[0] if args else None
            if self.client.connected:
                await self.open_search_dialog(pattern)
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "me":
            if not args:
                return
            action = " ".join(args)
            if self.active_tab == "Status":
                return
                
            target = self.active_tab
            if target.startswith("[PM] "):
                target = target.replace("[PM] ", "")
                
            if self.client.connected:
                await self.client.send(f"PRIVMSG {target} :\x01ACTION {action}\x01")
                now = datetime.now().strftime("%H:%M:%S")
                self.log_message(self.active_tab, f"[#565f89][{now}][/] [italic #9ece6a]* {self.current_nick} {action}[/]")
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "register":
            if len(args) < 2:
                self.log_message(self.active_tab, "Uso: /register contraseña correo")
                return
            pwd = args[0]
            email = args[1]
            if self.client.connected:
                self.log_message(self.active_tab, f"Enviando comando de registro para nick [bold]{self.current_nick}[/]...")
                await self.client.register_nick(pwd, email)
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "identify":
            if not args:
                self.log_message(self.active_tab, "Uso: /identify contraseña")
                return
            pwd = args[0]
            if self.client.connected:
                self.log_message(self.active_tab, "Enviando identificación...")
                await self.client.identify_nick(pwd)
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
                
        elif cmd == "verify":
            if not args:
                self.log_message(self.active_tab, "Uso: /verify código_de_verificación")
                return
            code = " ".join(args)
            if self.client.connected:
                # Standard verification varies, usually NickServ VERIFY REGISTER nick code
                await self.client.privmsg("NickServ", f"VERIFY REGISTER {self.current_nick} {code}")
                self.log_message(self.active_tab, "Enviando código de verificación a NickServ...")
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")

        elif cmd == "clear":
            if self.active_tab in self.chat_logs:
                self.chat_logs[self.active_tab].clear()
                
        elif cmd in ("quit", "connect"):
            reason = " ".join(args) if args else "InteRComunicador user leaving"
            await self.client.disconnect(reason)
            self.action_show_welcome()
            
        elif cmd == "raw":
            if not args:
                return
            raw_line = " ".join(args)
            if self.client.connected:
                await self.client.send(raw_line)
            else:
                self.log_message("Status", "[bold #f7768e]*** No conectado.[/]")
        
        elif cmd == "joinpart":
            self._suppress_joinpart = not self._suppress_joinpart
            state = "[bold #f7768e]OCULTOS[/]" if self._suppress_joinpart else "[bold #9ece6a]VISIBLES[/]"
            self.log_message(self.active_tab, f"[#7dcfff]*** Mensajes de entrada/salida: {state}[/]")
                
        else:
            self.log_message(self.active_tab, f"[bold #f7768e]Comando desconocido: /{cmd}. Escribe /help para ver la lista de comandos.[/]")

    # --------------------- BUTTON / ACTION BINDINGS ---------------------

    def action_quit_app(self) -> None:
        self.run_worker(self.client.disconnect("App closed"))
        self.exit()

    def action_join_channel(self) -> None:
        if not self.client.connected:
            return
        self.push_screen(JoinChannelDialog(), self.on_join_dialog_result)

    def on_join_dialog_result(self, result: Optional[str]):
        if result:
            self.run_worker(self.client.join(result))

    def action_direct_message(self) -> None:
        if not self.client.connected:
            return
        self.push_screen(DirectMessageDialog(), self.on_pm_dialog_result)

    def on_pm_dialog_result(self, result: Optional[str]):
        if result:
            pm_tab = f"[PM] {result}"
            self.run_worker(self.create_chat_tab(pm_tab, is_private=True))
            self.run_worker(self.switch_chat_tab(pm_tab))

    def action_register_nick(self) -> None:
        if not self.client.connected:
            return
        self.push_screen(RegisterDialog(), self.on_register_dialog_main_result)

    def action_close_tab(self) -> None:
        if self.active_tab == "Status":
            return
        
        tab = self.active_tab  # Capture before any async switch changes it
        # Part channel or close private message tab
        if tab.startswith("#") or tab.startswith("&"):
            self.run_worker(self.client.part(tab))
        else:
            # Close PM tab: do both steps in a single worker to avoid race
            async def _close_pm():
                await self.remove_chat_tab(tab)
                await self.switch_chat_tab("Status")
            self.run_worker(_close_pm())

    def on_register_dialog_main_result(self, result: Optional[Tuple[str, str]]):
        if result:
            pwd, email = result
            self.run_worker(self.client.register_nick(pwd, email))

    def action_search_channels(self) -> None:
        if not self.client.connected:
            return
        self.run_worker(self.open_search_dialog())

    async def open_search_dialog(self, pattern: Optional[str] = None):
        self.search_dialog = ChannelSearchDialog(self.client)
        self.push_screen(self.search_dialog, self.on_search_dialog_result)

    def on_search_dialog_result(self, result: Optional[str]):
        self.search_dialog = None
        if result:
            self.run_worker(self.client.join(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-disconnect":
            self.run_worker(self.client.disconnect())
            self.action_show_welcome()
        elif bid == "btn-search":
            self.action_search_channels()
        elif bid == "btn-join":
            self.action_join_channel()
        elif bid == "btn-pm":
            self.action_direct_message()
        elif bid == "btn-register":
            self.action_register_nick()
        elif bid == "btn-close-tab":
            self.action_close_tab()


if __name__ == "__main__":
    app = InteRComunicadorApp()
    app.run()
