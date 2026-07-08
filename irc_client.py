import asyncio
import ssl
import base64
import logging
from typing import Dict, List, Tuple, Optional, Any

# Configure logging for debugging
logging.basicConfig(
    filename='irc_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class IRCClient:
    def __init__(self):
        self.host: Optional[str] = None
        self.port: int = 6667
        self.use_ssl: bool = False
        self.verify_ssl: bool = False
        self.nick: str = "InterUser"
        self.username: str = "intercom"
        self.realname: str = "InteRComunicador User"
        self.password: Optional[str] = None
        
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.read_task: Optional[asyncio.Task] = None
        self.queue: asyncio.Queue = asyncio.Queue()
        self.connected: bool = False
        
        # Temp buffers
        self._names_buffer: Dict[str, List[Tuple[str, str]]] = {}
        self._my_current_nick: str = ""

    async def connect(
        self,
        host: str,
        port: int,
        use_ssl: bool,
        verify_ssl: bool,
        nick: str,
        username: str,
        realname: str,
        password: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.nick = nick
        self._my_current_nick = nick
        self.username = username if username else "intercom"
        self.realname = realname if realname else "InteRComunicador User"
        self.password = password
        
        logging.info(f"Connecting to {host}:{port} (SSL: {use_ssl}) as {nick}")
        self.queue.put_nowait({"type": "status", "message": f"Conectando a {host}:{port}..."})
        
        try:
            if use_ssl:
                if verify_ssl:
                    ssl_context = ssl.create_default_context()
                else:
                    ssl_context = ssl._create_unverified_context()
            else:
                ssl_context = None
                
            self.reader, self.writer = await asyncio.open_connection(
                host, port, ssl=ssl_context
            )
            self.connected = True
            
            # Start read loop
            self.read_task = asyncio.create_task(self._read_loop())
            
            # Initiate registration
            if self.password:
                # Send CAP for SASL if we want SASL, but NickServ identification after 001 is simpler and more compatible.
                # We will send standard connection messages first, and identify post-welcome.
                pass
                
            await self.send(f"NICK {self.nick}")
            await self.send(f"USER {self.username} 0 * :{self.realname}")
            
        except Exception as e:
            logging.exception("Connection failed")
            self.connected = False
            self.queue.put_nowait({"type": "error", "message": f"Error de conexión: {str(e)}"})
            self.queue.put_nowait({"type": "disconnected", "reason": str(e)})

    async def disconnect(self, reason: str = "Leaving"):
        logging.info(f"Disconnecting: {reason}")
        if self.connected:
            try:
                await self.send(f"QUIT :{reason}")
            except Exception:
                pass
        self._cleanup()
        self.queue.put_nowait({"type": "disconnected", "reason": reason})

    def _cleanup(self):
        self.connected = False
        if self.read_task:
            self.read_task.cancel()
            self.read_task = None
        if self.writer:
            try:
                self.writer.close()
            except Exception:
                pass
            self.writer = None
        self.reader = None

    async def send(self, message: str):
        if not self.writer or not self.connected:
            logging.warning(f"Attempted to send message while disconnected: {message}")
            return
        
        logging.debug(f"--> {message}")
        try:
            self.writer.write(f"{message}\r\n".encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            logging.exception("Error sending message")
            self._cleanup()
            self.queue.put_nowait({"type": "disconnected", "reason": f"Connection lost: {str(e)}"})

    async def join(self, channel: str):
        if not channel.startswith(('#', '&')):
            channel = f"#{channel}"
        await self.send(f"JOIN {channel}")

    async def part(self, channel: str, reason: str = "Goodbye"):
        await self.send(f"PART {channel} :{reason}")

    async def privmsg(self, target: str, message: str):
        await self.send(f"PRIVMSG {target} :{message}")

    async def change_nick(self, new_nick: str):
        await self.send(f"NICK {new_nick}")

    async def list_channels(self, pattern: Optional[str] = None):
        if pattern:
            await self.send(f"LIST {pattern}")
        else:
            await self.send("LIST")

    async def register_nick(self, password: str, email: str):
        # Traditional NickServ register
        await self.privmsg("NickServ", f"REGISTER {password} {email}")

    async def identify_nick(self, password: str):
        # Traditional NickServ identify
        await self.privmsg("NickServ", f"IDENTIFY {password}")

    async def _read_loop(self):
        logging.info("Read loop started")
        try:
            while self.connected and self.reader:
                line_bytes = await self.reader.readline()
                if not line_bytes:
                    logging.info("Connection closed by remote host")
                    self.queue.put_nowait({"type": "disconnected", "reason": "Conexión cerrada por el servidor."})
                    break
                
                line = line_bytes.decode('utf-8', errors='replace').rstrip('\r\n')
                logging.debug(f"<-- {line}")
                
                try:
                    await self._handle_line(line)
                except Exception as ex:
                    logging.exception(f"Error handling line: {line}")
                    
        except asyncio.CancelledError:
            logging.info("Read loop task cancelled")
        except Exception as e:
            logging.exception("Exception in read loop")
            self.queue.put_nowait({"type": "disconnected", "reason": f"Error de lectura: {str(e)}"})
        finally:
            self._cleanup()

    def _parse_line(self, line: str) -> Optional[Tuple[str, str, List[str]]]:
        prefix = ""
        trailing = []
        if not line:
            return None
        if line.startswith(':'):
            prefix_end = line.find(' ')
            if prefix_end == -1:
                return None
            prefix = line[1:prefix_end]
            line = line[prefix_end + 1:]
        
        if ' :' in line:
            line, trailing_part = line.split(' :', 1)
            trailing = [trailing_part]
        else:
            trailing = []
            
        parts = line.split()
        if not parts:
            return None
        command = parts[0]
        params = parts[1:] + trailing
        return prefix, command, params

    async def _handle_line(self, line: str):
        parsed = self._parse_line(line)
        if not parsed:
            return
            
        prefix, command, params = parsed
        
        # PING / PONG
        if command == "PING":
            payload = params[0] if params else ""
            await self.send(f"PONG :{payload}")
            return
            
        # Extract nick from prefix (nick!user@host)
        sender_nick = ""
        if prefix and '!' in prefix:
            sender_nick = prefix.split('!')[0]
        else:
            sender_nick = prefix

        # Handle command
        if command == "001": # RPL_WELCOME
            self._my_current_nick = params[0]
            self.queue.put_nowait({"type": "my_nick", "nick": self._my_current_nick})
            self.queue.put_nowait({"type": "connected"})
            self.queue.put_nowait({"type": "status", "message": f"¡Conectado exitosamente como {self._my_current_nick}!"})
            
            # If a password is saved, automatically identify with NickServ
            if self.password:
                self.queue.put_nowait({"type": "status", "message": "Identificando con NickServ..."})
                await self.identify_nick(self.password)
                
        elif command == "NICK":
            if not params:
                return
            new_nick = params[0]
            if sender_nick == self._my_current_nick:
                self._my_current_nick = new_nick
                self.queue.put_nowait({"type": "my_nick", "nick": new_nick})
            self.queue.put_nowait({"type": "nick", "old_nick": sender_nick, "new_nick": new_nick})
            
        elif command == "JOIN":
            if not params:
                return
            channel = params[0]
            self.queue.put_nowait({"type": "join", "channel": channel, "nick": sender_nick})
            
        elif command == "PART":
            if not params:
                return
            channel = params[0]
            reason = params[1] if len(params) > 1 else ""
            self.queue.put_nowait({"type": "part", "channel": channel, "nick": sender_nick, "reason": reason})
            
        elif command == "QUIT":
            reason = params[0] if params else ""
            self.queue.put_nowait({"type": "quit", "nick": sender_nick, "reason": reason})
            
        elif command == "PRIVMSG":
            if len(params) < 2:
                return  # Malformed PRIVMSG, ignore
            target = params[0]
            msg = params[1]
            
            # IRC services and anti-bot systems use special nicks or service hosts
            IRC_SERVICES = {
                'nickserv', 'chanserv', 'memoserv', 'operserv', 'hostserv',
                'botserv', 'global', 'ircop', 'helpserv', 'infoserv',
                # ChatZona / ChateaGratis anti-bot
                'nick', 'services',
            }
            sender_lower = sender_nick.lower() if sender_nick else ''
            # Also detect service hosts like nick!services@services.chat
            is_service_host = (
                prefix and
                ('services@' in prefix or prefix.endswith('.services') or prefix.endswith('.chat'))
            )
            is_service = sender_lower in IRC_SERVICES or is_service_host
            
            # Check if this is a private message or a channel message
            is_private = not target.startswith(('#', '&', '$', '+'))
            
            if is_service and is_private:
                # Route service messages to Status tab, not a PM tab
                self.queue.put_nowait({
                    "type": "status",
                    "message": f"[{sender_nick}] {msg}"
                })
            else:
                # If private, the sender is the chat group tab name
                chat_tab = f"[PM] {sender_nick}" if is_private else target
                self.queue.put_nowait({
                    "type": "msg",
                    "channel": chat_tab,
                    "nick": sender_nick,
                    "message": msg,
                    "is_private": is_private
                })
            
        elif command == "NOTICE":
            if not params:
                return  # Malformed NOTICE, ignore
            target = params[0]
            msg = params[1] if len(params) > 1 else ""
            # Server notice or NickServ notice
            sender = sender_nick if sender_nick else "Server"
            self.queue.put_nowait({
                "type": "status", 
                "message": f"[{sender}] {msg}"
            })
            
        elif command == "332": # RPL_TOPIC
            if len(params) < 3:
                return
            channel = params[1]
            topic = params[2]
            self.queue.put_nowait({"type": "topic", "channel": channel, "topic": topic})
            
        elif command == "353": # RPL_NAMREPLY
            # params: [my_nick, symbol, channel, names_list]
            if len(params) < 3:
                return  # Malformed 353, ignore
            channel = params[2]
            names_str = params[3] if len(params) > 3 else ""
            
            if channel not in self._names_buffer:
                self._names_buffer[channel] = []
                
            for name in names_str.split():
                if not name:
                    continue
                if name[0] in ('~', '&', '@', '%', '+'):
                    prefix_char = name[0]
                    name_nick = name[1:]
                else:
                    prefix_char = ''
                    name_nick = name
                if name_nick:  # Don't add empty nicks
                    self._names_buffer[channel].append((name_nick, prefix_char))
                
        elif command == "366": # RPL_ENDOFNAMES
            if len(params) < 2:
                return
            channel = params[1]
            nicks = self._names_buffer.pop(channel, [])
            self.queue.put_nowait({"type": "names", "channel": channel, "nicks": nicks})
            
        elif command == "322": # RPL_LIST
            # params: [my_nick, channel, num_users, topic]
            if len(params) < 2:
                return
            channel = params[1]
            try:
                users = int(params[2]) if len(params) > 2 else 0
            except ValueError:
                users = 0
            topic = params[3] if len(params) > 3 else ""
            self.queue.put_nowait({
                "type": "list_item",
                "channel": channel,
                "users": users,
                "topic": topic
            })
            
        elif command == "323": # RPL_LISTEND
            self.queue.put_nowait({"type": "list_end"})
            
        elif command == "433": # ERR_NICKNAMEINUSE
            proposed_nick = params[1]
            alternative_nick = proposed_nick + "_"
            self.queue.put_nowait({
                "type": "status",
                "message": f"El nickname '{proposed_nick}' ya está en uso. Intentando con '{alternative_nick}'..."
            })
            await self.change_nick(alternative_nick)
            
        elif command == "311": # RPL_WHOISUSER  — nick user host * :realname
            target_nick = params[1] if len(params) > 1 else "?"
            user       = params[2] if len(params) > 2 else ""
            host       = params[3] if len(params) > 3 else ""
            realname   = params[5] if len(params) > 5 else ""
            self.queue.put_nowait({"type": "whois_data", "field": "user",
                "nick": target_nick, "user": user, "host": host, "realname": realname})

        elif command == "312": # RPL_WHOISSERVER  — nick server :serverinfo
            target_nick  = params[1] if len(params) > 1 else "?"
            server_name  = params[2] if len(params) > 2 else ""
            server_info  = params[3] if len(params) > 3 else ""
            self.queue.put_nowait({"type": "whois_data", "field": "server",
                "nick": target_nick, "server": server_name, "info": server_info})

        elif command == "313": # RPL_WHOISOPERATOR
            target_nick = params[1] if len(params) > 1 else "?"
            self.queue.put_nowait({"type": "whois_data", "field": "oper",
                "nick": target_nick, "text": params[-1]})

        elif command == "317": # RPL_WHOISIDLE  — nick secs signontime :info
            target_nick = params[1] if len(params) > 1 else "?"
            idle_secs   = int(params[2]) if len(params) > 2 and params[2].isdigit() else 0
            signon_ts   = int(params[3]) if len(params) > 3 and params[3].isdigit() else 0
            self.queue.put_nowait({"type": "whois_data", "field": "idle",
                "nick": target_nick, "idle_secs": idle_secs, "signon_ts": signon_ts})

        elif command == "318": # RPL_ENDOFWHOIS
            target_nick = params[1] if len(params) > 1 else "?"
            self.queue.put_nowait({"type": "whois_end", "nick": target_nick})

        elif command == "319": # RPL_WHOISCHANNELS  — nick :[@#chan ...]
            target_nick = params[1] if len(params) > 1 else "?"
            channels    = params[2] if len(params) > 2 else ""
            self.queue.put_nowait({"type": "whois_data", "field": "channels",
                "nick": target_nick, "channels": channels})

        elif command == "330": # RPL_WHOISACCOUNT (ircu/InspIRCd)
            target_nick = params[1] if len(params) > 1 else "?"
            account     = params[2] if len(params) > 2 else ""
            self.queue.put_nowait({"type": "whois_data", "field": "account",
                "nick": target_nick, "account": account})

        elif command == "338": # RPL_WHOISACTUALLY (real IP)
            target_nick = params[1] if len(params) > 1 else "?"
            real_ip     = params[2] if len(params) > 2 else ""
            self.queue.put_nowait({"type": "whois_data", "field": "real_ip",
                "nick": target_nick, "real_ip": real_ip})

        elif command in ("372", "375", "376"): # MOTD lines
            # Show MOTD lines in the main status view
            msg = params[1] if len(params) > 1 else ""
            self.queue.put_nowait({"type": "status", "message": msg})
            
        elif command == "998":
            # ChatZona / ChateaGratis: Validation response (success or failure)
            msg = params[-1] if params else "Respuesta de validación recibida."
            self.queue.put_nowait({"type": "status", "message": f"[VALIDATE] {msg}"})
            # Emit special event so frontend can hide the verification banner
            if any(word in msg.lower() for word in ["ok", "correct", "valid", "accept", "success", "bienvenid", "correcto", "verificad"]):
                self.queue.put_nowait({"type": "verification_cleared"})
                
        elif command == "999":
            # Some servers use 999 for validation errors
            msg = params[-1] if params else "Error de validación."
            self.queue.put_nowait({"type": "status", "message": f"[VALIDATE ERROR] {msg}"})
            
        else:
            # Fallback for other numerics - if it has a message parameter, show in status log
            if len(params) > 1 and command.isdigit():
                # params[0] is our nick, params[1:] are command args
                # usually the last param is the readable message
                msg = params[-1]
                self.queue.put_nowait({"type": "status", "message": f"[{command}] {msg}"})
            elif len(params) > 0 and not command.isdigit():
                # General fallback for raw messages
                pass
