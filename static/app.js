/* ==========================================================================
   InteRComunicador JS - Premium Web Client
   ========================================================================== */

// Retrieve or generate a unique session ID for this browser tab
let sessionId = sessionStorage.getItem("irc_session_id");
if (!sessionId) {
    sessionId = "session_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
    sessionStorage.setItem("irc_session_id", sessionId);
}

const state = {
    connected: false,
    currentNick: "InterUser",
    activeTab: "Status",
    joinedChats: ["Status"],
    messages: {"Status": []},
    channelUsers: {}, // channel -> list of [nick, prefix]
    unreadCounts: {}, // tab -> count
    presets: []
};

let socket = null;
let autocompleteIndex = -1;
let pendingRegistration = null; // Holds welcome screen registration data

const COMMANDS = [
    { name: "/join", desc: "#canal - Unirse a un canal" },
    { name: "/part", desc: "[#canal] [razón] - Salir de un canal" },
    { name: "/query", desc: "usuario - Abrir chat privado" },
    { name: "/msg", desc: "usuario mensaje - Mensaje privado rápido" },
    { name: "/nick", desc: "nuevo_nick - Cambiar apodo" },
    { name: "/list", desc: "[patrón] - Listar canales" },
    { name: "/me", desc: "acción - Realizar una acción" },
    { name: "/clear", desc: "- Limpiar la pantalla" },
    { name: "/register", desc: "pwd email - Registrar nick con NickServ" },
    { name: "/identify", desc: "pwd - Identificarse en NickServ" },
    { name: "/verify", desc: "código - Verificar registro NickServ" },
    { name: "/validate", desc: "token - Enviar token de verificación anti-bot (ChatZona)" },
    { name: "/captcha", desc: "token - Alias de /validate para anti-bot" },
    { name: "/whois", desc: "nick - Ver información de un usuario" },
    { name: "/away", desc: "[mensaje] - Marcar como ausente" },
    { name: "/back", desc: "- Volver de ausente" },
    { name: "/ctcp", desc: "nick comando - Enviar consulta CTCP" },
    { name: "/raw", desc: "comando IRC crudo" },
    { name: "/help", desc: "- Mostrar ayuda" }
];

// Elements
const connectionScreen = document.getElementById("connection-screen");
const chatScreen = document.getElementById("chat-screen");
const connectForm = document.getElementById("connect-form");
const presetSelect = document.getElementById("preset-select");
const serverHost = document.getElementById("server-host");
const serverPort = document.getElementById("server-port");
const serverSSL = document.getElementById("server-ssl");
const serverVerifySSL = document.getElementById("server-verify-ssl");
const nickInput = document.getElementById("nick-input");
const passwordInput = document.getElementById("password-input");
const usernameInput = document.getElementById("username-input");
const realnameInput = document.getElementById("realname-input");
const btnConnect = document.getElementById("btn-connect");
const btnRegisterWelcome = document.getElementById("btn-register-welcome");
const btnDisconnect = document.getElementById("btn-disconnect");

const activeChatsList = document.getElementById("active-chats-list");
const activeChatTitle = document.getElementById("active-chat-title");
const activeChatTopic = document.getElementById("active-chat-topic");
const chatMessagesContainer = document.getElementById("chat-messages-container");
const messageInput = document.getElementById("message-input");
const btnSendMessage = document.getElementById("btn-send-message");

// Sidebar action buttons
const btnSidebarSearch = document.getElementById("btn-sidebar-search");
const btnSidebarJoin = document.getElementById("btn-sidebar-join");
const btnSidebarPM = document.getElementById("btn-sidebar-pm");
const btnSidebarRegister = document.getElementById("btn-sidebar-register");
const btnSidebarCloseTab = document.getElementById("btn-sidebar-close-tab");

// Status indicators in sidebar
const statusIndicatorDot = document.getElementById("status-indicator-dot");
const statusIndicatorText = document.getElementById("status-indicator-text");
const nickIndicatorText = document.getElementById("nick-indicator-text");

// User sidebar elements
const usersSidebar = document.getElementById("users-sidebar");
const btnToggleUsers = document.getElementById("btn-toggle-users");
const usersList = document.getElementById("users-list");
const userCount = document.getElementById("user-count");
const userSearchInput = document.getElementById("user-search-input");

// Modals
const searchModal = document.getElementById("search-modal");
const channelSearchFilter = document.getElementById("channel-search-filter");
const btnTriggerSearch = document.getElementById("btn-trigger-search");
const searchStatusText = document.getElementById("search-status-text");
const channelsTableBody = document.querySelector("#channels-table tbody");

const joinModal = document.getElementById("join-modal");
const joinForm = document.getElementById("join-form");
const joinChannelName = document.getElementById("join-channel-name");

const pmModal = document.getElementById("pm-modal");
const pmForm = document.getElementById("pm-form");
const pmNick = document.getElementById("pm-nick");

const registerModal = document.getElementById("register-modal");
const registerForm = document.getElementById("register-form");
const regModalPassword = document.getElementById("reg-modal-password");
const regModalEmail = document.getElementById("reg-modal-email");

const autocompletePopup = document.getElementById("autocomplete-popup");

// ----------------- WEBSOCKET & MULTI-SESSION SYNC -----------------

const appSessions = {};
let activeSessionId = null;

function createSession(sessId = null, selectImmediate = true) {
    if (!sessId) {
        sessId = "session_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
    }
    
    appSessions[sessId] = {
        id: sessId,
        state: {
            connected: false,
            currentNick: "InterUser",
            activeTab: "Status",
            joinedChats: ["Status"],
            messages: {"Status": []},
            channelUsers: {},
            unreadCounts: {},
            verificationUrl: null
        },
        socket: null,
        config: null
    };
    
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/ws?session_id=${sessId}`;
    
    const socketInstance = new WebSocket(wsUrl);
    appSessions[sessId].socket = socketInstance;
    
    socketInstance.onopen = () => {
        console.log(`WebSocket connected for session ${sessId}`);
    };
    
    socketInstance.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleSessionSocketEvent(sessId, data);
    };
    
    socketInstance.onclose = () => {
        console.log(`WebSocket disconnected for session ${sessId}, retrying in 2 seconds...`);
        appSessions[sessId].state.connected = false;
        if (sessId === activeSessionId) {
            updateUILayout();
        }
        renderServersSidebar();
        setTimeout(() => {
            if (appSessions[sessId]) {
                const retrySocket = new WebSocket(wsUrl);
                appSessions[sessId].socket = retrySocket;
                retrySocket.onopen = socketInstance.onopen;
                retrySocket.onmessage = socketInstance.onmessage;
                retrySocket.onclose = socketInstance.onclose;
            }
        }, 2000);
    };
    
    if (selectImmediate) {
        selectSession(sessId);
    }
    renderServersSidebar();
    return sessId;
}

function selectSession(sessId) {
    activeSessionId = sessId;
    const session = appSessions[sessId];
    if (!session) return;
    
    // Bind global state proxy properties to match the selected session
    state.connected = session.state.connected;
    state.currentNick = session.state.currentNick;
    state.activeTab = session.state.activeTab;
    state.joinedChats = session.state.joinedChats;
    state.messages = session.state.messages;
    state.channelUsers = session.state.channelUsers;
    state.unreadCounts = session.state.unreadCounts;
    
    socket = session.socket;
    
    // Clear/reset the unread indicator for this session
    session.unread = false;
    
    if (state.connected) {
        connectionScreen.classList.remove("active");
        chatScreen.classList.add("active");
        
        // Update header indicators
        const nickIndicatorText = document.getElementById("nick-indicator-text");
        if (nickIndicatorText) nickIndicatorText.textContent = state.currentNick;
        const statusIndicatorDot = document.getElementById("status-indicator-dot");
        const statusIndicatorText = document.getElementById("status-indicator-text");
        if (statusIndicatorDot && statusIndicatorText) {
            statusIndicatorDot.className = "status-dot green";
            statusIndicatorText.textContent = "Conectado";
        }
    } else {
        connectionScreen.classList.add("active");
        chatScreen.classList.remove("active");
        
        // Pre-fill inputs with this session's configuration
        if (session.config) {
            serverHost.value = session.config.host || "";
            serverPort.value = session.config.port || "";
            serverSSL.checked = session.config.ssl !== undefined ? session.config.ssl : true;
            serverVerifySSL.checked = session.config.verify_ssl !== undefined ? session.config.verify_ssl : false;
            nickInput.value = session.config.nick || "";
            passwordInput.value = session.config.password || "";
            usernameInput.value = session.config.username || "";
            realnameInput.value = session.config.realname || "";
        }
    }
    
    // Verification banner sync
    const verificationBanner = document.getElementById("verification-banner");
    if (verificationBanner) {
        if (session.state.verificationUrl) {
            showVerificationBanner(session.state.verificationUrl);
        } else {
            verificationBanner.classList.add("hidden");
        }
    }
    
    updateUILayout();
    renderActiveChatsList();
    renderMessages(state.activeTab);
    renderUsersList(state.activeTab);
    renderServersSidebar();
}

function closeSession(sessId) {
    const keys = Object.keys(appSessions);
    if (keys.length <= 1) {
        alert("Debes mantener al menos una conexión configurada.");
        return;
    }
    
    if (confirm("¿Seguro que deseas desconectar y cerrar esta conexión IRC?")) {
        const session = appSessions[sessId];
        if (session) {
            if (session.socket) {
                try {
                    session.socket.send(JSON.stringify({ action: "disconnect", reason: "Leaving" }));
                    session.socket.close();
                } catch(e){}
            }
            delete appSessions[sessId];
            
            if (activeSessionId === sessId) {
                const remainingKeys = Object.keys(appSessions);
                selectSession(remainingKeys[0]);
            } else {
                renderServersSidebar();
            }
        }
    }
}

function renderServersSidebar() {
    const listContainer = document.getElementById("servers-list");
    if (!listContainer) return;
    
    listContainer.innerHTML = "";
    
    Object.keys(appSessions).forEach((sessId, index) => {
        const session = appSessions[sessId];
        const btn = document.createElement("button");
        btn.className = "server-btn";
        if (sessId === activeSessionId) {
            btn.classList.add("active");
        }
        
        let hasUnread = false;
        Object.keys(session.state.unreadCounts).forEach(tab => {
            if (session.state.unreadCounts[tab] > 0) {
                hasUnread = true;
            }
        });
        if (hasUnread) {
            btn.classList.add("unread");
        }
        
        let displayName = "S" + (index + 1);
        if (session.config && session.config.host) {
            const parts = session.config.host.split('.');
            if (parts.length > 1) {
                displayName = parts[parts.length - 2].substring(0, 3).toUpperCase();
            } else {
                displayName = parts[0].substring(0, 3).toUpperCase();
            }
        }
        
        btn.textContent = displayName;
        btn.title = session.config && session.config.host 
            ? `${session.config.host} (${session.state.connected ? 'Conectado' : 'Desconectado'}) (Doble clic para eliminar)`
            : `Nueva sesión IRC (S${index + 1}) (Doble clic para eliminar)`;
            
        btn.onclick = () => {
            selectSession(sessId);
        };
        
        btn.ondblclick = (e) => {
            e.preventDefault();
            closeSession(sessId);
        };
        
        listContainer.appendChild(btn);
    });
}

function handleSessionSocketEvent(sessId, data) {
    const session = appSessions[sessId];
    if (!session) return;
    
    const type = data.type;
    
    if (type === "init") {
        session.state.connected = data.connected;
        session.state.currentNick = data.current_nick;
        session.state.joinedChats = data.joined_chats;
        session.state.messages = data.messages;
        session.state.channelUsers = data.channel_users;
        
        if (sessId === activeSessionId) {
            selectSession(sessId);
        } else {
            renderServersSidebar();
        }
        
    } else if (type === "connection_status") {
        session.state.connected = data.connected;
        if (sessId === activeSessionId) {
            state.connected = data.connected;
            updateUILayout();
            if (!state.connected) {
                btnConnect.disabled = false;
                btnConnect.innerHTML = `<i class="fa-solid fa-plug"></i> Conectarse`;
                const verificationBanner = document.getElementById("verification-banner");
                if (verificationBanner) verificationBanner.classList.add("hidden");
            } else {
                connectionScreen.classList.remove("active");
                chatScreen.classList.add("active");
            }
        }
        renderServersSidebar();
        
    } else if (type === "my_nick") {
        session.state.currentNick = data.nick;
        if (sessId === activeSessionId) {
            state.currentNick = data.nick;
            const nickIndicatorText = document.getElementById("nick-indicator-text");
            if (nickIndicatorText) nickIndicatorText.textContent = state.currentNick;
        }
        
    } else if (type === "sync_tabs") {
        const oldActive = session.state.activeTab;
        const oldTabs = [...(session.state.joinedChats || [])];
        session.state.joinedChats = data.tabs;
        
        if (!session.state.joinedChats.includes(oldActive)) {
            session.state.activeTab = "Status";
        }
        
        // Play join sound if a new channel was added
        if (typeof soundSettings !== "undefined" && soundSettings.join && sessId === activeSessionId) {
            const newlyJoined = data.tabs.filter(t => t !== "Status" && !t.startsWith("[PM]") && !oldTabs.includes(t));
            if (newlyJoined.length > 0) {
                playNotificationSound("join");
            }
        }
        
        if (sessId === activeSessionId) {
            state.joinedChats = session.state.joinedChats;
            state.activeTab = session.state.activeTab;
            renderActiveChatsList();
            renderMessages(state.activeTab);
            renderUsersList(state.activeTab);
        }
        
    } else if (type === "message") {
        const tab = data.tab;
        const msg = data.message;
        
        if (msg.nick && isUserIgnored(msg.nick)) {
            return;
        }
        
        if (!session.state.messages[tab]) {
            session.state.messages[tab] = [];
        }
        session.state.messages[tab].push(msg);
        if (session.state.messages[tab].length > 300) {
            session.state.messages[tab].shift();
        }
        
        // Persist to local history
        saveMessageToHistory(tab, msg);
        
        // Desktop notification for mentions and PMs
        const myNick = session.state.currentNick || "";
        const isMention = myNick && msg.nick !== myNick && msg.text &&
            msg.text.toLowerCase().includes(myNick.toLowerCase());
        const isPM = tab.startsWith("[PM] ") && msg.nick !== myNick;
        if ((isMention || isPM) && sessId === activeSessionId) {
            fireDesktopNotification(
                isPM ? `💬 PM de ${msg.nick}` : `🔔 Mención en ${tab}`,
                msg.text,
                msg.nick
            );
            
            if (isMention) {
                addMentionToList(tab, msg);
                if (typeof soundSettings !== "undefined" && soundSettings.mention) {
                    playNotificationSound("mention");
                }
            } else if (isPM) {
                if (typeof soundSettings !== "undefined" && soundSettings.pm) {
                    playNotificationSound("pm");
                }
            }
        }
        
        if (sessId !== activeSessionId || tab !== state.activeTab) {
            session.state.unreadCounts[tab] = (session.state.unreadCounts[tab] || 0) + 1;
            renderServersSidebar();
            if (sessId === activeSessionId) {
                renderActiveChatsList();
            }
        } else {
            queueMessageRender(tab, msg);
        }
        
    } else if (type === "users_list") {
        session.state.channelUsers[data.channel] = data.users;
        if (sessId === activeSessionId && state.activeTab === data.channel) {
            state.channelUsers[data.channel] = data.users;
            renderUsersList(data.channel);
        }
        
    } else if (type === "topic") {
        if (sessId === activeSessionId && state.activeTab === data.channel) {
            activeChatTopic.textContent = data.topic;
        }
        
    } else if (type === "search_item") {
        appendSearchItem(data.channel, data.users, data.topic);
        
    } else if (type === "search_end") {
        renderSearchResults();
        const total = allSearchChannels.length;
        searchStatusText.textContent = total > 0
            ? `✅ ${total} canales cargados. Filtra por nombre o tema, ordena por columna.`
            : "⚠️ No se recibieron canales. Espera 60s tras conectar e intenta de nuevo.";
        btnTriggerSearch.disabled = false;
        
    } else if (type === "clear") {
        session.state.messages[data.tab] = [];
        if (sessId === activeSessionId && state.activeTab === data.tab) {
            chatMessagesContainer.innerHTML = "";
            state.messages[data.tab] = [];
        }
    } else if (type === "verification_required") {
        session.state.verificationUrl = data.url;
        if (sessId === activeSessionId) {
            showVerificationBanner(data.url);
        }
    } else if (type === "verification_cleared") {
        session.state.verificationUrl = null;
        if (sessId === activeSessionId) {
            hideVerificationBanner();
        }
    } else if (type === "whois_panel") {
        // Only render if this is the active session
        if (sessId === activeSessionId) {
            renderWhoisPanel(data.data);
        }
    } else if (type === "personal_suggestion") {
        // Optional: only present if personal/ module is installed on the server
        if (sessId === activeSessionId) {
            showPersonalSuggestionPanel(data);
        }
    }
}


function showVerificationBanner(url) {
    const verificationBanner = document.getElementById("verification-banner");
    const verificationBannerLink = document.getElementById("verification-banner-link");
    if (verificationBanner && verificationBannerLink) {
        verificationBannerLink.href = url;
        verificationBanner.classList.remove("hidden");
    }
}

function hideVerificationBanner() {
    const verificationBanner = document.getElementById("verification-banner");
    if (verificationBanner) {
        verificationBanner.classList.add("hidden");
    }
}

// ----------------- PERFORMANCE LOG BATCHING -----------------

let messageBuffer = [];
let renderTimeout = null;

function queueMessageRender(tab, message) {
    messageBuffer.push({ tab, message });
    if (!renderTimeout) {
        renderTimeout = requestAnimationFrame(flushMessageBuffer);
    }
}

function flushMessageBuffer() {
    renderTimeout = null;
    const currentTab = state.activeTab;
    
    const groups = {};
    for (const item of messageBuffer) {
        if (!groups[item.tab]) {
            groups[item.tab] = [];
        }
        groups[item.tab].push(item.message);
    }
    messageBuffer = [];

    if (groups[currentTab]) {
        const fragment = document.createDocumentFragment();
        const wasAtBottom = chatMessagesContainer.scrollHeight - chatMessagesContainer.scrollTop <= chatMessagesContainer.clientHeight + 100;

        for (const msg of groups[currentTab]) {
            const line = createMessageElement(msg);
            fragment.appendChild(line);
        }

        chatMessagesContainer.appendChild(fragment);
        
        if (wasAtBottom) {
            chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
        }
    }
    
    for (const [tab, msgs] of Object.entries(groups)) {
        if (tab !== currentTab) {
            state.unreadCounts[tab] = (state.unreadCounts[tab] || 0) + msgs.length;
            const tabEl = document.querySelector(`li[data-chat-name="${tab}"]`);
            if (tabEl) {
                let badge = tabEl.querySelector(".badge");
                if (!badge) {
                    badge = document.createElement("span");
                    badge.className = "badge";
                    tabEl.querySelector(".tab-actions").appendChild(badge);
                }
                badge.textContent = state.unreadCounts[tab];
            }
        }
    }
}

// Context menu state
let ctxMenuNick = null;

function createMessageElement(msg) {
    const div = document.createElement("div");
    div.className = `message-line ${msg.type}`;
    
    // Highlight mentions
    if (msg.nick !== state.currentNick && msg.text &&
        state.currentNick && msg.text.toLowerCase().includes(state.currentNick.toLowerCase())) {
        div.classList.add("mention");
    }
    
    const timeSpan = document.createElement("span");
    timeSpan.className = "timestamp";
    timeSpan.textContent = `[${msg.timestamp}]`;
    div.appendChild(timeSpan);
    
    if (msg.nick) {
        const senderSpan = document.createElement("span");
        senderSpan.className = "sender";
        senderSpan.style.color = msg.color;
        senderSpan.textContent = msg.type === "action" ? `* ${msg.nick}` : `<${msg.nick}>`;
        // Left-click: quick open PM
        senderSpan.onclick = () => {
            if (msg.nick !== state.currentNick) {
                openPmWithNick(msg.nick);
            }
        };
        // Right-click: context menu
        senderSpan.oncontextmenu = (e) => {
            e.preventDefault();
            showNickContextMenu(e, msg.nick);
        };
        div.appendChild(senderSpan);
    }
    
    const textSpan = document.createElement("span");
    textSpan.className = "text";
    textSpan.innerHTML = formatRichText(msg.text);
    div.appendChild(textSpan);
    
    return div;
}

function formatRichText(text) {
    // Strip IRC color codes (\x03NN,NN and formatting chars)
    text = text.replace(/\x03\d{1,2}(,\d{1,2})?/g, "");
    text = text.replace(/[\x02\x0F\x16\x1D\x1F]/g, "");
    // Escape HTML
    text = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    // Make URLs clickable
    text = text.replace(/(https?:\/\/[^\s<>"]+)/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    return text;
}

// ----------------- RENDER ENGINE -----------------

/**
 * Renders stored messages for a given tab into the chat container.
 * Called whenever the user switches tabs.
 */
function renderMessages(tabName) {
    chatMessagesContainer.innerHTML = "";
    const msgs = state.messages[tabName] || [];
    if (msgs.length === 0) return;

    const fragment = document.createDocumentFragment();
    msgs.forEach(msg => {
        if (msg.nick && isUserIgnored(msg.nick)) {
            return;
        }
        fragment.appendChild(createMessageElement(msg));
    });
    chatMessagesContainer.appendChild(fragment);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

function updateUILayout() {
    if (state.connected) {
        connectionScreen.classList.remove("active");
        chatScreen.classList.add("active");
        
        statusIndicatorDot.className = "status-dot green";
        statusIndicatorText.textContent = "Conectado";
        nickIndicatorText.textContent = state.currentNick;
    } else {
        chatScreen.classList.remove("active");
        connectionScreen.classList.add("active");
        
        statusIndicatorDot.className = "status-dot red";
        statusIndicatorText.textContent = "Desconectado";
        nickIndicatorText.textContent = "-";
    }
}

function renderActiveChatsList() {
    activeChatsList.innerHTML = "";
    state.joinedChats.forEach(chat => {
        const li = document.createElement("li");
        li.setAttribute("data-chat-name", chat);
        if (chat === state.activeTab) {
            li.className = "active";
        }
        
        const txtSpan = document.createElement("span");
        txtSpan.className = "tab-text";
        txtSpan.textContent = chat;
        li.appendChild(txtSpan);

        const actionsDiv = document.createElement("div");
        actionsDiv.className = "tab-actions";

        // Unread Badge
        if (state.unreadCounts[chat] > 0) {
            const badge = document.createElement("span");
            badge.className = "badge";
            badge.textContent = state.unreadCounts[chat];
            actionsDiv.appendChild(badge);
        }

        // Close button (except for Status)
        if (chat !== "Status") {
            const closeBtn = document.createElement("button");
            closeBtn.className = "close-tab-btn";
            closeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            closeBtn.title = "Cerrar Pestaña";
            closeBtn.onclick = (e) => {
                e.stopPropagation();
                closeChatTab(chat);
            };
            actionsDiv.appendChild(closeBtn);
        }

        li.appendChild(actionsDiv);
        li.onclick = () => switchTab(chat);
        activeChatsList.appendChild(li);
    });
}

function switchTab(tabName) {
    state.activeTab = tabName;
    state.unreadCounts[tabName] = 0;
    
    // Sync back to the session state
    const session = appSessions[activeSessionId];
    if (session) {
        session.state.activeTab = tabName;
        session.state.unreadCounts[tabName] = 0;
    }
    
    renderActiveChatsList();
    renderMessages(tabName);
    renderUsersList(tabName);
    
    activeChatTitle.textContent = tabName;
    if (tabName === "Status") {
        activeChatTopic.textContent = "Mensajes del sistema y del servidor";
        usersSidebar.classList.remove("active");
        btnToggleUsers.style.display = "none";
    } else if (tabName.startsWith("[PM]")) {
        activeChatTopic.textContent = `Charla privada con ${tabName.replace("[PM] ", "")}`;
        usersSidebar.classList.remove("active");
        btnToggleUsers.style.display = "none";
    } else {
        activeChatTopic.textContent = "Cargando tema del canal...";
        usersSidebar.classList.add("active");
        btnToggleUsers.style.display = "block";
    }
    
    messageInput.focus();
}

function renderUsersList(channel) {
    usersList.innerHTML = "";
    if (channel === "Status" || channel.startsWith("[PM]")) {
        userCount.textContent = "0";
        return;
    }
    
    const users = state.channelUsers[channel] || [];
    const filterText = userSearchInput.value.toLowerCase().trim();
    
    const filteredUsers = users.filter(([nick, prefix]) => {
        return nick.toLowerCase().includes(filterText);
    });
    
    userCount.textContent = filteredUsers.length;
    
    const fragment = document.createDocumentFragment();
    filteredUsers.forEach(([nick, prefix]) => {
        const li = document.createElement("li");
        
        if (prefix) {
            const prefSpan = document.createElement("span");
            prefSpan.className = `user-prefix ${prefix === "+" ? "voiced" : "op"}`;
            prefSpan.textContent = prefix;
            li.appendChild(prefSpan);
        }
        
        const nickSpan = document.createElement("span");
        nickSpan.textContent = nick;
        li.appendChild(nickSpan);
        
        // Star badge for favorite users
        if (isUserFavorite(nick)) {
            const star = document.createElement("span");
            star.className = "fav-star";
            star.textContent = "★";
            star.title = "Favorito";
            li.appendChild(star);
        }
        
        li.onclick = () => {
            if (nick !== state.currentNick) {
                openWhoisPanel(nick);
            }
        };
        
        li.ondblclick = () => {
            if (nick !== state.currentNick) {
                openPmWithNick(nick);
            }
        };
        
        li.oncontextmenu = (e) => {
            e.preventDefault();
            showNickContextMenu(e, nick);
        };
        
        fragment.appendChild(li);
    });
    
    usersList.appendChild(fragment);
}

function closeChatTab(tabName) {
    if (tabName === "Status") return;
    
    if (tabName.startsWith("[PM] ")) {
        // Remove from local state AND the session state
        const session = appSessions[activeSessionId];
        const idx = state.joinedChats.indexOf(tabName);
        if (idx > -1) {
            state.joinedChats.splice(idx, 1);
            delete state.messages[tabName];
            delete state.unreadCounts[tabName];
            // Keep session state in sync
            if (session) {
                session.state.joinedChats = state.joinedChats;
                session.state.messages = state.messages;
                session.state.unreadCounts = state.unreadCounts;
            }
        }
        
        // Notify the backend to remove it from its list of tabs/joined_chats
        sendAction("close_tab", { tab: tabName });
        
        if (state.activeTab === tabName) {
            switchTab("Status");
        } else {
            renderActiveChatsList();
        }
    } else {
        // Channel: send PART command to server
        sendAction("command", { text: `/part ${tabName}` });
    }
}

function openPmWithNick(nick) {
    if (!nick || nick === state.currentNick) return;
    const pmTab = `[PM] ${nick}`;
    if (!state.joinedChats.includes(pmTab)) {
        state.joinedChats.push(pmTab);
        state.messages[pmTab] = [];
    }
    switchTab(pmTab);
    sendAction("command", { text: `/query ${nick}` });
}

// ---- INPUT HISTORY (↑/↓ to navigate sent messages) ----
let inputHistory    = [];
let inputHistoryIdx = -1;
let inputHistoryDraft = "";

// ---- DESKTOP NOTIFICATIONS ----
let notificationsEnabled = localStorage.getItem("notif_enabled") === "true";

function updateNotifButton() {
    const btn = document.getElementById("btn-notif-toggle");
    if (!btn) return;
    if (notificationsEnabled) {
        btn.classList.add("notif-active");
        btn.title = "Notificaciones activas (clic para desactivar)";
        btn.innerHTML = '<i class="fa-solid fa-bell"></i>';
    } else {
        btn.classList.remove("notif-active");
        btn.title = "Activar notificaciones de escritorio";
        btn.innerHTML = '<i class="fa-solid fa-bell-slash"></i>';
    }
}

document.getElementById("btn-notif-toggle").onclick = () => {
    if (!notificationsEnabled) {
        Notification.requestPermission().then(perm => {
            if (perm === "granted") {
                notificationsEnabled = true;
                localStorage.setItem("notif_enabled", "true");
                updateNotifButton();
                addSystemStatusMessage("🔔 Notificaciones de escritorio activadas.");
            } else {
                addSystemStatusMessage("⚠️ Permiso de notificaciones denegado por el navegador.");
            }
        });
    } else {
        notificationsEnabled = false;
        localStorage.setItem("notif_enabled", "false");
        updateNotifButton();
        addSystemStatusMessage("🔕 Notificaciones desactivadas.");
    }
};

function fireDesktopNotification(title, body, nick) {
    if (!notificationsEnabled) return;
    if (Notification.permission !== "granted") return;
    // Only fire if window is not focused
    if (document.hasFocus()) return;
    const n = new Notification(title, {
        body: body.length > 120 ? body.slice(0, 120) + "…" : body,
        icon: `https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${encodeURIComponent(nick || "irc")}`,
        tag: nick || "irc"
    });
    n.onclick = () => { window.focus(); n.close(); };
    setTimeout(() => n.close(), 6000);
}

updateNotifButton();

// ---- AWAY STATUS TOGGLE ----
let isAway = false;

document.getElementById("btn-away-toggle").onclick = () => {
    if (!state.connected) return;
    isAway = !isAway;
    const btn = document.getElementById("btn-away-toggle");
    if (isAway) {
        sendAction("command", { text: "/away AFK - Ausente por el momento" });
        btn.classList.add("away-active");
        btn.title = "Estás ausente — clic para volver";
        addSystemStatusMessage("🟡 Marcado como Ausente (AWAY).");
    } else {
        sendAction("command", { text: "/away" });
        btn.classList.remove("away-active");
        btn.title = "Marcar como Ausente";
        addSystemStatusMessage("🟢 De vuelta — marcado como Disponible.");
    }
};

// ---- IN-CHAT SEARCH ----
let chatSearchMatches = [];
let chatSearchCurrent = -1;

function toggleChatSearch() {
    const bar = document.getElementById("chat-search-bar");
    if (!bar) return;
    if (bar.classList.contains("hidden")) {
        bar.classList.remove("hidden");
        document.getElementById("chat-search-input").focus();
        document.getElementById("chat-search-input").select();
    } else {
        closeChatSearch();
    }
}

function closeChatSearch() {
    const bar = document.getElementById("chat-search-bar");
    if (!bar || bar.classList.contains("hidden")) return;
    bar.classList.add("hidden");
    clearSearchHighlights();
    chatSearchMatches = [];
    chatSearchCurrent = -1;
    document.getElementById("chat-search-count").textContent = "";
}

function clearSearchHighlights() {
    chatMessagesContainer.querySelectorAll(".search-highlight").forEach(el => {
        const parent = el.parentNode;
        parent.replaceChild(document.createTextNode(el.textContent), el);
        parent.normalize();
    });
}

function runChatSearch(query) {
    clearSearchHighlights();
    chatSearchMatches = [];
    chatSearchCurrent = -1;
    document.getElementById("chat-search-count").textContent = "";
    if (!query || query.length < 2) return;

    const lq = query.toLowerCase();
    const textNodes = [];
    const walker = document.createTreeWalker(
        chatMessagesContainer, NodeFilter.SHOW_TEXT,
        { acceptNode: n => n.textContent.toLowerCase().includes(lq) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP }
    );
    let node;
    while ((node = walker.nextNode())) textNodes.push(node);

    textNodes.forEach(tn => {
        const parts = tn.textContent.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
        if (parts.length <= 1) return;
        const frag = document.createDocumentFragment();
        parts.forEach(part => {
            if (part.toLowerCase() === lq) {
                const mark = document.createElement("mark");
                mark.className = "search-highlight";
                mark.textContent = part;
                chatSearchMatches.push(mark);
                frag.appendChild(mark);
            } else {
                frag.appendChild(document.createTextNode(part));
            }
        });
        tn.parentNode.replaceChild(frag, tn);
    });

    document.getElementById("chat-search-count").textContent =
        chatSearchMatches.length > 0 ? `1 / ${chatSearchMatches.length}` : "Sin resultados";

    if (chatSearchMatches.length > 0) {
        chatSearchCurrent = 0;
        jumpToSearchMatch(0);
    }
}

function jumpToSearchMatch(idx) {
    chatSearchMatches.forEach(m => m.classList.remove("current"));
    if (chatSearchMatches[idx]) {
        chatSearchMatches[idx].classList.add("current");
        chatSearchMatches[idx].scrollIntoView({ block: "center", behavior: "smooth" });
        document.getElementById("chat-search-count").textContent =
            `${idx + 1} / ${chatSearchMatches.length}`;
    }
}

document.getElementById("chat-search-input").addEventListener("input", e => {
    runChatSearch(e.target.value.trim());
});

document.getElementById("chat-search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") {
        e.preventDefault();
        if (chatSearchMatches.length === 0) return;
        chatSearchCurrent = (chatSearchCurrent + 1) % chatSearchMatches.length;
        jumpToSearchMatch(chatSearchCurrent);
    } else if (e.key === "Escape") {
        closeChatSearch();
    }
});

document.getElementById("btn-chat-search").onclick = () => toggleChatSearch();
document.getElementById("btn-chat-search-close").onclick = () => closeChatSearch();

document.getElementById("btn-chat-search-next").onclick = () => {
    if (chatSearchMatches.length === 0) return;
    chatSearchCurrent = (chatSearchCurrent + 1) % chatSearchMatches.length;
    jumpToSearchMatch(chatSearchCurrent);
};

document.getElementById("btn-chat-search-prev").onclick = () => {
    if (chatSearchMatches.length === 0) return;
    chatSearchCurrent = (chatSearchCurrent - 1 + chatSearchMatches.length) % chatSearchMatches.length;
    jumpToSearchMatch(chatSearchCurrent);
};

// ---- BLACKLIST MANAGEMENT ----
let ignoredUsers = new Set(JSON.parse(localStorage.getItem("ignored_users") || "[]"));

function isUserIgnored(nick) {
    if (!nick) return false;
    return ignoredUsers.has(nick.toLowerCase());
}

function ignoreUser(nick) {
    if (!nick) return;
    const nickLower = nick.trim();
    if (!nickLower || nickLower.toLowerCase() === state.currentNick.toLowerCase()) return;
    ignoredUsers.add(nickLower.toLowerCase());
    localStorage.setItem("ignored_users", JSON.stringify([...ignoredUsers]));
    
    addSystemStatusMessage(`🚫 Has ignorado a ${nickLower}. Sus mensajes ya no se mostrarán.`);
    renderBlacklist();
    
    // Re-render current tab messages to apply filter immediately
    renderMessages(state.activeTab);
}

function unignoreUser(nick) {
    if (!nick) return;
    const nickLower = nick.trim().toLowerCase();
    if (ignoredUsers.has(nickLower)) {
        ignoredUsers.delete(nickLower);
        localStorage.setItem("ignored_users", JSON.stringify([...ignoredUsers]));
        addSystemStatusMessage(`✅ Has dejado de ignorar a ${nick}.`);
    }
    renderBlacklist();
    
    // Re-render current tab messages to show their messages again
    renderMessages(state.activeTab);
}

function renderBlacklist() {
    const ul = document.getElementById("blacklist-ul");
    if (!ul) return;
    ul.innerHTML = "";
    
    if (ignoredUsers.size === 0) {
        const li = document.createElement("li");
        li.style.justifyContent = "center";
        li.style.color = "var(--text-muted)";
        li.textContent = "Ningún usuario ignorado.";
        ul.appendChild(li);
        return;
    }
    
    [...ignoredUsers].sort().forEach(nick => {
        const li = document.createElement("li");
        
        const span = document.createElement("span");
        span.className = "ignored-nick";
        span.textContent = nick;
        li.appendChild(span);
        
        const btn = document.createElement("button");
        btn.className = "btn-unignore";
        btn.innerHTML = '<i class="fa-solid fa-user-check"></i> Dejar de ignorar';
        btn.onclick = () => unignoreUser(nick);
        li.appendChild(btn);
        
        ul.appendChild(li);
    });
}

function addSystemStatusMessage(text) {
    const err = {
        timestamp: new Date().toLocaleTimeString(),
        type: "status",
        text: text
    };
    if (!state.messages["Status"]) {
        state.messages["Status"] = [];
    }
    state.messages["Status"].push(err);
    queueMessageRender("Status", err);
}

// ---- THEMES SYSTEM ----
const THEMES = ["tokyo-night", "dracula", "nord", "solarized", "light"];

function setTheme(themeName) {
    if (!THEMES.includes(themeName)) themeName = "tokyo-night";
    document.documentElement.setAttribute("data-theme", themeName);
    localStorage.setItem("selected_theme", themeName);
    
    // Update theme card active styles in modal
    document.querySelectorAll(".theme-card").forEach(card => {
        if (card.getAttribute("data-theme") === themeName) {
            card.classList.add("active");
        } else {
            card.classList.remove("active");
        }
    });
}

// Load theme on startup immediately
setTheme(localStorage.getItem("selected_theme") || "tokyo-night");

// ---- SOUND SYSTEM (Web Audio API Synthesizer) ----
let soundSettings = {
    mention: localStorage.getItem("sound_mention") !== "false", // default true
    pm: localStorage.getItem("sound_pm") !== "false",           // default true
    join: localStorage.getItem("sound_join") === "true"          // default false
};

const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playNotificationSound(type) {
    try {
        if (audioCtx.state === "suspended") {
            audioCtx.resume();
        }
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        const now = audioCtx.currentTime;
        if (type === "mention") {
            // High double chime
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(1320, now + 0.1);
            gainNode.gain.setValueAtTime(0.12, now);
            gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc.start(now);
            osc.stop(now + 0.35);
        } else if (type === "pm") {
            // Sweet chord
            osc.type = "triangle";
            osc.frequency.setValueAtTime(523.25, now); // C5
            osc.frequency.setValueAtTime(659.25, now + 0.07); // E5
            gainNode.gain.setValueAtTime(0.1, now);
            gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
            osc.start(now);
            osc.stop(now + 0.45);
        } else if (type === "join") {
            // Low ascending swoosh
            osc.type = "sine";
            osc.frequency.setValueAtTime(220, now);
            osc.frequency.exponentialRampToValueAtTime(440, now + 0.18);
            gainNode.gain.setValueAtTime(0.08, now);
            gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
            osc.start(now);
            osc.stop(now + 0.18);
        }
    } catch(e) {
        console.error("Web Audio failed:", e);
    }
}

// ---- MENTIONS SYSTEM ----
let mentionsList = JSON.parse(localStorage.getItem("irc_mentions") || "[]");
let unreadMentionsCount = 0;

function addMentionToList(tab, msg) {
    mentionsList.unshift({
        ts: Date.now(),
        timestamp: msg.timestamp || new Date().toLocaleTimeString(),
        nick: msg.nick || "",
        text: msg.text || "",
        channel: tab
    });
    if (mentionsList.length > 200) mentionsList.pop();
    localStorage.setItem("irc_mentions", JSON.stringify(mentionsList));
    unreadMentionsCount++;
    updateMentionsBadge();
}

function updateMentionsBadge() {
    const badge = document.getElementById("mentions-badge");
    if (!badge) return;
    if (unreadMentionsCount > 0) {
        badge.textContent = unreadMentionsCount;
        badge.classList.remove("hidden");
    } else {
        badge.classList.add("hidden");
    }
}

function renderMentionsModal() {
    const list = document.getElementById("mentions-list");
    if (!list) return;
    list.innerHTML = "";
    if (mentionsList.length === 0) {
        list.innerHTML = '<p class="history-empty">Sin menciones todavía.</p>';
        return;
    }
    
    mentionsList.forEach(m => {
        const row = document.createElement("div");
        row.className = "history-msg-row";
        row.style.cursor = "pointer";
        row.title = `Ir al canal ${m.channel}`;
        row.onclick = () => {
            if (state.joinedChats.includes(m.channel)) {
                switchTab(m.channel);
            }
            closeModal("mentions-modal");
        };
        
        const dateStr = new Date(m.ts).toLocaleDateString();
        row.innerHTML = `<span class="h-time" style="font-size:10px; color:var(--text-muted); min-width: 120px;">[${dateStr} ${m.timestamp}] in ${m.channel}</span><span class="h-nick" style="color:var(--accent); font-weight:bold;">&lt;${m.nick}&gt;</span><span class="h-text">${m.text}</span>`;
        list.appendChild(row);
    });
}

// ---- FAVORITES MANAGEMENT ----
let favoriteUsers = new Set(JSON.parse(localStorage.getItem("favorite_users") || "[]"));

function isUserFavorite(nick) {
    if (!nick) return false;
    return favoriteUsers.has(nick.toLowerCase());
}

function addFavorite(nick) {
    if (!nick) return;
    const nl = nick.trim();
    if (!nl) return;
    favoriteUsers.add(nl.toLowerCase());
    localStorage.setItem("favorite_users", JSON.stringify([...favoriteUsers]));
    addSystemStatusMessage(`★ ${nl} agregado a favoritos.`);
    renderFavorites();
    renderUsersList(state.activeTab);
}

function removeFavorite(nick) {
    if (!nick) return;
    const nl = nick.trim().toLowerCase();
    favoriteUsers.delete(nl);
    localStorage.setItem("favorite_users", JSON.stringify([...favoriteUsers]));
    addSystemStatusMessage(`☆ ${nick} eliminado de favoritos.`);
    renderFavorites();
    renderUsersList(state.activeTab);
}

function renderFavorites() {
    const ul = document.getElementById("favorites-ul");
    if (!ul) return;
    ul.innerHTML = "";
    if (favoriteUsers.size === 0) {
        const li = document.createElement("li");
        li.style.justifyContent = "center";
        li.style.color = "var(--text-muted)";
        li.textContent = "Ningún usuario favorito aún.";
        ul.appendChild(li);
        return;
    }
    [...favoriteUsers].sort().forEach(nick => {
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.className = "fav-nick";
        span.textContent = nick;
        li.appendChild(span);
        const btn = document.createElement("button");
        btn.className = "btn-unfavorite";
        btn.innerHTML = '<i class="fa-solid fa-star-half-stroke"></i> Quitar';
        btn.onclick = () => removeFavorite(nick);
        li.appendChild(btn);
        // PM on click
        span.style.cursor = "pointer";
        span.onclick = () => { openPmWithNick(nick); closeModal("favorites-modal"); };
        ul.appendChild(li);
    });
}

// ---- HISTORY MANAGEMENT ----
const HISTORY_KEY_PREFIX = "irc_history_";
const HISTORY_MAX_DAYS = 15;

function _historyKey(tab) {
    return HISTORY_KEY_PREFIX + encodeURIComponent(tab);
}

function pruneOldHistory() {
    const cutoff = Date.now() - HISTORY_MAX_DAYS * 86400000;
    Object.keys(localStorage).forEach(key => {
        if (!key.startsWith(HISTORY_KEY_PREFIX)) return;
        try {
            const entries = JSON.parse(localStorage.getItem(key) || "[]");
            const fresh = entries.filter(e => e.ts >= cutoff);
            if (fresh.length === 0) {
                localStorage.removeItem(key);
            } else {
                localStorage.setItem(key, JSON.stringify(fresh));
            }
        } catch(_) { localStorage.removeItem(key); }
    });
}

function saveMessageToHistory(tab, msg) {
    if (!msg || !tab || tab === "Status") return;
    const key = _historyKey(tab);
    try {
        const entries = JSON.parse(localStorage.getItem(key) || "[]");
        entries.push({
            ts: Date.now(),
            time: msg.timestamp || new Date().toLocaleTimeString(),
            nick: msg.nick || "",
            text: msg.text || ""
        });
        // Keep at most 2000 entries per tab
        if (entries.length > 2000) entries.splice(0, entries.length - 2000);
        localStorage.setItem(key, JSON.stringify(entries));
    } catch(e) { /* localStorage full, skip */ }
}

function getHistoryTabs() {
    return Object.keys(localStorage)
        .filter(k => k.startsWith(HISTORY_KEY_PREFIX))
        .map(k => {
            try { return decodeURIComponent(k.slice(HISTORY_KEY_PREFIX.length)); }
            catch(_) { return k.slice(HISTORY_KEY_PREFIX.length); }
        });
}

function renderHistoryModal() {
    // Populate tab dropdown
    const sel = document.getElementById("history-select-tab");
    const current = sel.value;
    sel.innerHTML = '<option value="">-- Selecciona canal/chat --</option>';
    getHistoryTabs().sort().forEach(tab => {
        const opt = document.createElement("option");
        opt.value = tab;
        opt.textContent = tab;
        if (tab === current) opt.selected = true;
        sel.appendChild(opt);
    });
    
    // Also pre-select current active tab if available
    if (!current && state.activeTab && state.activeTab !== "Status") {
        sel.value = state.activeTab;
    }
}

function searchAndShowHistory() {
    const sel = document.getElementById("history-select-tab");
    const tab = sel.value;
    const results = document.getElementById("history-results");
    if (!tab) {
        results.innerHTML = '<p class="history-empty">Selecciona un canal o chat primero.</p>';
        return;
    }
    const key = _historyKey(tab);
    const from = document.getElementById("history-date-from").value;
    const to   = document.getElementById("history-date-to").value;
    let entries = JSON.parse(localStorage.getItem(key) || "[]");
    
    if (from) {
        const fromTs = new Date(from).getTime();
        entries = entries.filter(e => e.ts >= fromTs);
    }
    if (to) {
        const toTs = new Date(to).getTime() + 86400000;
        entries = entries.filter(e => e.ts < toTs);
    }
    
    if (entries.length === 0) {
        results.innerHTML = '<p class="history-empty">Sin mensajes en ese rango.</p>';
        return;
    }
    
    results.innerHTML = "";
    let lastDate = "";
    entries.forEach(e => {
        const d = new Date(e.ts).toLocaleDateString();
        if (d !== lastDate) {
            lastDate = d;
            const div = document.createElement("div");
            div.className = "history-date-divider";
            div.textContent = d;
            results.appendChild(div);
        }
        const row = document.createElement("div");
        row.className = "history-msg-row";
        const isMe = e.nick && e.nick === state.currentNick;
        row.innerHTML = `<span class="h-time">${e.time}</span><span class="h-nick${isMe ? " is-me" : ""}">${e.nick || "*"}</span><span class="h-text">${e.text}</span>`;
        results.appendChild(row);
    });
    results.scrollTop = results.scrollHeight;
}

// ---- NICK CONTEXT MENU ----
const nickContextMenu = document.getElementById("nick-context-menu");

function showNickContextMenu(e, nick) {
    ctxMenuNick = nick;
    
    // Update ignore menu option text
    const ctxIgnore = document.getElementById("ctx-ignore");
    if (ctxIgnore) {
        if (nick === state.currentNick) {
            ctxIgnore.style.display = "none";
        } else {
            ctxIgnore.style.display = "block";
            if (isUserIgnored(nick)) {
                ctxIgnore.innerHTML = '<i class="fa-solid fa-user-check"></i> Dejar de ignorar';
            } else {
                ctxIgnore.innerHTML = '<i class="fa-solid fa-user-slash"></i> Ignorar Usuario';
            }
        }
    }
    
    // Update favorite menu option text
    const ctxFav = document.getElementById("ctx-favorite");
    if (ctxFav) {
        if (nick === state.currentNick) {
            ctxFav.style.display = "none";
        } else {
            ctxFav.style.display = "block";
            if (isUserFavorite(nick)) {
                ctxFav.innerHTML = '<i class="fa-solid fa-star-half-stroke"></i> Quitar de favoritos';
            } else {
                ctxFav.innerHTML = '<i class="fa-solid fa-star"></i> Marcar como favorito';
            }
        }
    }
    
    nickContextMenu.classList.remove("hidden");
    const menuW = 220;
    const menuH = 240;
    let x = e.clientX;
    let y = e.clientY;
    if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 8;
    if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 8;
    nickContextMenu.style.left = x + "px";
    nickContextMenu.style.top  = y + "px";
}

function hideNickContextMenu() {
    nickContextMenu.classList.add("hidden");
    ctxMenuNick = null;
}

document.getElementById("ctx-whois").onclick = () => {
    if (ctxMenuNick) openWhoisPanel(ctxMenuNick);
    hideNickContextMenu();
};

document.getElementById("ctx-pm").onclick = () => {
    if (ctxMenuNick) openPmWithNick(ctxMenuNick);
    hideNickContextMenu();
};

document.getElementById("ctx-mention").onclick = () => {
    if (ctxMenuNick) {
        messageInput.value = (messageInput.value + ` ${ctxMenuNick}: `).trimStart();
        messageInput.focus();
    }
    hideNickContextMenu();
};

document.getElementById("ctx-ctcp-version").onclick = () => {
    if (ctxMenuNick) sendAction("command", { text: `/ctcp ${ctxMenuNick} VERSION` });
    hideNickContextMenu();
};

document.getElementById("ctx-ctcp-ping").onclick = () => {
    if (ctxMenuNick) sendAction("command", { text: `/ctcp ${ctxMenuNick} PING` });
    hideNickContextMenu();
};

document.getElementById("ctx-ignore").onclick = () => {
    if (ctxMenuNick) {
        if (isUserIgnored(ctxMenuNick)) {
            unignoreUser(ctxMenuNick);
        } else {
            ignoreUser(ctxMenuNick);
        }
    }
    hideNickContextMenu();
};

document.getElementById("ctx-favorite").onclick = () => {
    if (ctxMenuNick) {
        if (isUserFavorite(ctxMenuNick)) {
            removeFavorite(ctxMenuNick);
        } else {
            addFavorite(ctxMenuNick);
        }
    }
    hideNickContextMenu();
};

document.addEventListener("click", (e) => {
    if (!nickContextMenu.classList.contains("hidden") && !nickContextMenu.contains(e.target)) {
        hideNickContextMenu();
    }
});

// ---- WHOIS PANEL ----
let lastWhoisNick = null;

function openWhoisPanel(nick) {
    lastWhoisNick = nick;
    // Reset modal
    document.getElementById("whois-nick").textContent = nick;
    document.getElementById("whois-realname").textContent = "Consultando...";
    document.getElementById("whois-account").textContent = "";
    document.getElementById("whois-fields").innerHTML = "";
    // Default avatar (Gravatar-style fallback using nick hash)
    const avatarEl = document.getElementById("whois-avatar");
    avatarEl.src = `https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${encodeURIComponent(nick)}`;
    openModal("whois-modal");
    sendAction("command", { text: `/whois ${nick}` });
}

function renderWhoisPanel(data) {
    document.getElementById("whois-nick").textContent = data.nick || "?";
    document.getElementById("whois-realname").textContent = data.realname || "";
    const accountEl = document.getElementById("whois-account");
    accountEl.textContent = data.account ? `Cuenta: ${data.account}` : "";
    
    const fields = document.getElementById("whois-fields");
    fields.innerHTML = "";
    
    function addField(icon, label, value) {
        const d = document.createElement("div");
        d.className = "whois-field";
        d.innerHTML = `<i class="fa-solid ${icon}"></i><span><b>${label}:</b> <span class="field-value">${value}</span></span>`;
        fields.appendChild(d);
    }
    
    if (data.user && data.host) addField("fa-at", "Ident@Host", `${data.user}@${data.host}`);
    if (data.real_ip) addField("fa-network-wired", "IP real", data.real_ip);
    if (data.server) addField("fa-server", "Servidor", `${data.server} — ${data.server_info || ""}`);
    if (data.oper) addField("fa-shield", "IRC Op", data.oper);
    
    if (data.idle_secs !== undefined) {
        const mins = Math.floor(data.idle_secs / 60);
        const secs = data.idle_secs % 60;
        const idleStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
        addField("fa-clock", "Inactivo", idleStr);
    }
    if (data.signon_ts) {
        const dt = new Date(data.signon_ts * 1000).toLocaleString();
        addField("fa-right-to-bracket", "Conectado desde", dt);
    }
    
    if (data.channels) {
        const d = document.createElement("div");
        d.className = "whois-field";
        const chanList = document.createElement("span");
        chanList.className = "channels-list";
        data.channels.trim().split(/\s+/).forEach(ch => {
            const badge = document.createElement("span");
            badge.className = "chan-badge";
            const cleanCh = ch.replace(/^[@+%~&]/, "");
            badge.textContent = ch;
            badge.title = "Unirse a " + cleanCh;
            badge.onclick = () => { sendAction("command", { text: `/join ${cleanCh}` }); closeModal("whois-modal"); };
            chanList.appendChild(badge);
        });
        d.innerHTML = `<i class="fa-solid fa-hashtag"></i><b>Canales:</b> `;
        d.appendChild(chanList);
        fields.appendChild(d);
    }
    
    // Try Gravatar if we have account info (use nick as seed fallback)
    const avatarEl = document.getElementById("whois-avatar");
    avatarEl.src = `https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${encodeURIComponent(data.nick)}`;
}

document.getElementById("btn-whois-pm").onclick = () => {
    if (lastWhoisNick) { openPmWithNick(lastWhoisNick); closeModal("whois-modal"); }
};
document.getElementById("btn-whois-refresh").onclick = () => {
    if (lastWhoisNick) openWhoisPanel(lastWhoisNick);
};

// ----------------- CONFIG & PRESETS LOAD -----------------

async function loadConfigAndPresets() {
    try {
        const response = await fetch("/api/config");
        const config = await response.json();
        state.presets = config.presets;
        
        presetSelect.innerHTML = "";
        state.presets.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.name;
            opt.textContent = p.name;
            if (p.description) opt.title = p.description;
            presetSelect.appendChild(opt);
        });
        
        function applyPreset(presetName) {
            const selected = state.presets.find(p => p.name === presetName);
            if (!selected) return;
            
            const isCustom = presetName === "Personalizado";
            
            // Fill fields
            if (!isCustom) {
                serverHost.value = selected.host;
                serverPort.value = selected.port;
                serverSSL.checked = selected.ssl;
                serverVerifySSL.checked = selected.verify_ssl;
            }
            
            // Enable/disable host+port fields based on preset
            serverHost.readOnly = !isCustom;
            serverPort.readOnly = !isCustom;
            serverHost.style.opacity = isCustom ? "1" : "0.7";
            serverPort.style.opacity = isCustom ? "1" : "0.7";
            
            // Show description hint
            const existingHint = document.getElementById("preset-description");
            if (existingHint) existingHint.remove();
            if (selected.description) {
                const hint = document.createElement("p");
                hint.id = "preset-description";
                hint.style.cssText = "font-size:12px;color:var(--text-muted);margin-top:4px;";
                hint.textContent = `ℹ️ ${selected.description}`;
                presetSelect.parentElement.appendChild(hint);
            }
        }
        
        presetSelect.onchange = () => applyPreset(presetSelect.value);
        
        const last = config.last_connection;
        if (last) {
            // Try to match saved preset name
            const matchedPreset = state.presets.find(p => p.name === last.preset);
            if (matchedPreset) {
                presetSelect.value = matchedPreset.name;
            } else {
                presetSelect.value = state.presets[0]?.name || "";
            }
            
            serverHost.value = last.host || "irc.chathispano.com";
            serverPort.value = last.port || 6697;
            serverSSL.checked = last.ssl !== undefined ? last.ssl : true;
            serverVerifySSL.checked = last.verify_ssl !== undefined ? last.verify_ssl : false;
            nickInput.value = last.nick || "InterUser";
            passwordInput.value = last.password || "";
            usernameInput.value = last.username || "intercom";
            realnameInput.value = last.realname || "InteRComunicador User";
        } else {
            presetSelect.value = state.presets[0]?.name || "";
        }
        
        // Apply preset description on load
        applyPreset(presetSelect.value);
        
    } catch (e) {
        console.error("Error loading config", e);
    }
}

function sendAction(action, data = {}) {
    const session = appSessions[activeSessionId];
    if (session && session.socket && session.socket.readyState === WebSocket.OPEN) {
        session.socket.send(JSON.stringify({
            action,
            active_tab: state.activeTab,
            ...data
        }));
    }
}

// ----------------- MODALS MANAGEMENT -----------------

function openModal(modalId) {
    document.getElementById(modalId).classList.add("active");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
}

window.closeModal = closeModal; // Expose globally for close buttons

// ----------------- EVENT LISTENERS -----------------

// Connection & Welcome Form
connectForm.onsubmit = (e) => {
    e.preventDefault();
    
    const payload = {
        preset: presetSelect.value,
        host: serverHost.value,
        port: parseInt(serverPort.value),
        ssl: serverSSL.checked,
        verify_ssl: serverVerifySSL.checked,
        nick: nickInput.value,
        password: passwordInput.value,
        username: usernameInput.value,
        realname: realnameInput.value
    };
    
    if (pendingRegistration) {
        payload.register_on_connect = pendingRegistration;
        pendingRegistration = null;
    }
    
    btnConnect.disabled = true;
    btnConnect.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Conectando...`;
    
    const statusIndicatorDot = document.getElementById("status-indicator-dot");
    const statusIndicatorText = document.getElementById("status-indicator-text");
    if (statusIndicatorDot && statusIndicatorText) {
        statusIndicatorDot.className = "status-dot yellow";
        statusIndicatorText.textContent = "Conectando...";
    }
    
    const session = appSessions[activeSessionId];
    if (session) {
        session.config = payload;
    }
    
    sendAction("connect", { data: payload });
};

btnRegisterWelcome.onclick = () => {
    openModal("register-modal");
};

btnDisconnect.onclick = () => {
    sendAction("disconnect");
};

const btnShutdown = document.getElementById("btn-shutdown");
if (btnShutdown) {
    btnShutdown.onclick = async () => {
        if (confirm("¿Estás seguro de que deseas apagar InteRComunicador?\n\nEsto cerrará el servidor de fondo y desconectará todas las salas de chat activas.")) {
            document.body.innerHTML = `
                <div style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    background-color: #1a1b26;
                    color: #a9b1d6;
                    font-family: 'Outfit', 'Inter', sans-serif;
                    text-align: center;
                ">
                    <i class="fa-solid fa-power-off" style="font-size: 64px; color: #f7768e; margin-bottom: 20px; animation: pulse 2s infinite;"></i>
                    <h2 style="color: #ffffff; margin-bottom: 10px; font-weight: 700;">InteRComunicador Apagado</h2>
                    <p style="color: #565f89; margin-bottom: 20px; font-size: 16px;">El servidor web se ha detenido con éxito y se han cerrado todas las conexiones IRC.</p>
                    <p style="font-size: 14px; color: #565f89; opacity: 0.8;">Ya puedes cerrar esta pestaña del navegador de forma segura.</p>
                </div>
                <style>
                    @keyframes pulse {
                        0% { transform: scale(1); opacity: 1; }
                        50% { transform: scale(1.1); opacity: 0.7; }
                        100% { transform: scale(1); opacity: 1; }
                    }
                </style>
            `;
            try {
                await fetch("/api/shutdown", { method: "POST" });
            } catch(e) {
                console.error("Error calling shutdown:", e);
            }
        }
    };
}


// Modals forms submissions
joinForm.onsubmit = (e) => {
    e.preventDefault();
    const chan = joinChannelName.value.trim();
    if (chan) {
        sendAction("command", { text: `/join ${chan}` });
        closeModal("join-modal");
        joinChannelName.value = "";
    }
};

pmForm.onsubmit = (e) => {
    e.preventDefault();
    const nick = pmNick.value.trim();
    if (nick) {
        const pmTab = `[PM] ${nick}`;
        if (!state.joinedChats.includes(pmTab)) {
            state.joinedChats.push(pmTab);
            state.messages[pmTab] = [];
        }
        switchTab(pmTab);
        sendAction("command", { text: `/query ${nick}` });
        closeModal("pm-modal");
        pmNick.value = "";
    }
};

registerForm.onsubmit = (e) => {
    e.preventDefault();
    const pwd = regModalPassword.value.trim();
    const email = regModalEmail.value.trim();
    
    if (pwd && email) {
        if (state.connected) {
            // Register immediately
            sendAction("command", { text: `/register ${pwd} ${email}` });
        } else {
            // Save for connecting stage
            pendingRegistration = { password: pwd, email: email };
            passwordInput.value = pwd;
            alert("Los detalles de registro se han guardado. Por favor, haz clic en 'Conectarse' para iniciar la conexión y el registro automático.");
        }
        closeModal("register-modal");
        regModalPassword.value = "";
        regModalEmail.value = "";
    }
};

// Sidebar Action Buttons clicks — search handled by openSearchModal() defined below
btnSidebarSearch.onclick = () => openSearchModal();

btnSidebarJoin.onclick = () => {
    openModal("join-modal");
    joinChannelName.focus();
};

btnSidebarPM.onclick = () => {
    openModal("pm-modal");
    pmNick.focus();
};

btnSidebarRegister.onclick = () => {
    openModal("register-modal");
    regModalPassword.focus();
};

btnSidebarCloseTab.onclick = () => {
    closeChatTab(state.activeTab);
};

// Blacklist Sidebar Buttons & Modal events
const btnSidebarBlacklist = document.getElementById("btn-sidebar-blacklist");

btnSidebarBlacklist.onclick = () => {
    openModal("blacklist-modal");
    renderBlacklist();
    document.getElementById("blacklist-add-nick").focus();
};

document.getElementById("btn-blacklist-add").onclick = () => {
    const input = document.getElementById("blacklist-add-nick");
    const nick = input.value.trim();
    if (nick) {
        ignoreUser(nick);
        input.value = "";
    }
};

document.getElementById("blacklist-add-nick").onkeydown = (e) => {
    if (e.key === "Enter") {
        const input = document.getElementById("blacklist-add-nick");
        const nick = input.value.trim();
        if (nick) {
            ignoreUser(nick);
            input.value = "";
        }
    }
};

// Favorites sidebar button & modal
const btnSidebarFavorites = document.getElementById("btn-sidebar-favorites");
btnSidebarFavorites.onclick = () => {
    openModal("favorites-modal");
    renderFavorites();
    document.getElementById("favorites-add-nick").focus();
};

document.getElementById("btn-favorites-add").onclick = () => {
    const input = document.getElementById("favorites-add-nick");
    const nick = input.value.trim();
    if (nick) { addFavorite(nick); input.value = ""; }
};

document.getElementById("favorites-add-nick").onkeydown = (e) => {
    if (e.key === "Enter") {
        const input = document.getElementById("favorites-add-nick");
        const nick = input.value.trim();
        if (nick) { addFavorite(nick); input.value = ""; }
    }
};

// History sidebar button & modal
const btnSidebarHistory = document.getElementById("btn-sidebar-history");
btnSidebarHistory.onclick = () => {
    openModal("history-modal");
    renderHistoryModal();
};

document.getElementById("btn-history-search").onclick = searchAndShowHistory;

document.getElementById("history-select-tab").onchange = searchAndShowHistory;

document.getElementById("btn-history-clear-all").onclick = () => {
    if (!confirm("¿Eliminar todo el historial guardado localmente? Esta acción no se puede deshacer.")) return;
    Object.keys(localStorage).forEach(k => {
        if (k.startsWith(HISTORY_KEY_PREFIX)) localStorage.removeItem(k);
    });
    renderHistoryModal();
    document.getElementById("history-results").innerHTML = '<p class="history-empty">Historial eliminado.</p>';
};

// Prune old history on startup
pruneOldHistory();

// ---- COLLAPSIBLE ACTIONS PANEL ----
(function initActionsToggle() {
    const btn   = document.getElementById("btn-toggle-actions");
    const panel = document.getElementById("actions-buttons-panel");
    if (!btn || !panel) return;

    const PREF_KEY = "actions_panel_collapsed";
    const collapsed = localStorage.getItem(PREF_KEY) === "true";

    if (collapsed) {
        panel.classList.add("collapsed");
        btn.setAttribute("aria-expanded", "false");
    }

    btn.addEventListener("click", () => {
        const isExpanded = btn.getAttribute("aria-expanded") === "true";
        if (isExpanded) {
            panel.classList.add("collapsed");
            btn.setAttribute("aria-expanded", "false");
            localStorage.setItem(PREF_KEY, "true");
        } else {
            panel.classList.remove("collapsed");
            btn.setAttribute("aria-expanded", "true");
            localStorage.setItem(PREF_KEY, "false");
        }
    });
})();

// Autocomplete and Inputs
function handleMessageSubmit() {
    const text = messageInput.value.trim();
    if (!text) return;
    
    messageInput.value = "";
    
    if (text.startsWith("/")) {
        sendAction("command", { text });
    } else {
        if (state.activeTab === "Status") {
            const err = {
                timestamp: new Date().toLocaleTimeString(),
                type: "error",
                text: "No puedes enviar mensajes en la pestaña de Status. Únete a un canal o abre un privado."
            };
            if (!state.messages["Status"]) {
                state.messages["Status"] = [];
            }
            state.messages["Status"].push(err);
            queueMessageRender("Status", err);
            return;
        }
        
        let target = state.activeTab;
        if (target.startsWith("[PM] ")) {
            target = target.replace("[PM] ", "");
        }
        sendAction("privmsg", { target, text });
    }
    
    hideAutocomplete();
    // Push to input history
    if (text && !text.startsWith("/help")) {
        inputHistory.unshift(text);
        if (inputHistory.length > 100) inputHistory.pop();
        inputHistoryIdx = -1;
    }
}

btnSendMessage.onclick = handleMessageSubmit;

messageInput.onkeydown = (e) => {
    if (e.key === "Enter") {
        if (autocompletePopup.classList.contains("active") && autocompleteIndex >= 0) {
            const items = autocompletePopup.querySelectorAll(".autocomplete-item");
            if (items[autocompleteIndex]) {
                items[autocompleteIndex].click();
                e.preventDefault();
                return;
            }
        }
        handleMessageSubmit();
        e.preventDefault();
    } else if (e.key === "ArrowDown") {
        if (autocompletePopup.classList.contains("active")) {
            const items = autocompletePopup.querySelectorAll(".autocomplete-item");
            if (items.length > 0) {
                autocompleteIndex = (autocompleteIndex + 1) % items.length;
                updateAutocompleteSelection(items);
                e.preventDefault();
            }
        } else if (inputHistoryIdx > 0) {
            // Navigate forward in history
            inputHistoryIdx--;
            messageInput.value = inputHistory[inputHistoryIdx];
            e.preventDefault();
        } else if (inputHistoryIdx === 0) {
            inputHistoryIdx = -1;
            messageInput.value = inputHistoryDraft;
            e.preventDefault();
        }
    } else if (e.key === "ArrowUp") {
        if (autocompletePopup.classList.contains("active")) {
            const items = autocompletePopup.querySelectorAll(".autocomplete-item");
            if (items.length > 0) {
                autocompleteIndex = (autocompleteIndex - 1 + items.length) % items.length;
                updateAutocompleteSelection(items);
                e.preventDefault();
            }
        } else if (inputHistory.length > 0) {
            // Navigate back in history
            if (inputHistoryIdx === -1) {
                inputHistoryDraft = messageInput.value;
            }
            inputHistoryIdx = Math.min(inputHistoryIdx + 1, inputHistory.length - 1);
            messageInput.value = inputHistory[inputHistoryIdx];
            e.preventDefault();
        }
    } else if (e.key === "Escape") {
        hideAutocomplete();
    }
};

messageInput.oninput = () => {
    const val = messageInput.value;
    if (val.startsWith("/")) {
        const cmdPart = val.split(" ")[0];
        const matches = COMMANDS.filter(c => c.name.startsWith(cmdPart));
        
        if (matches.length > 0) {
            showAutocomplete(matches);
        } else {
            hideAutocomplete();
        }
    } else {
        hideAutocomplete();
    }
};

function showAutocomplete(matches) {
    autocompletePopup.innerHTML = "";
    autocompleteIndex = -1;
    
    matches.forEach((m, idx) => {
        const item = document.createElement("div");
        item.className = "autocomplete-item";
        
        const nameSpan = document.createElement("span");
        nameSpan.className = "name";
        nameSpan.textContent = m.name;
        item.appendChild(nameSpan);
        
        const descSpan = document.createElement("span");
        descSpan.className = "desc";
        descSpan.textContent = m.desc;
        item.appendChild(descSpan);
        
        item.onclick = () => {
            messageInput.value = m.name + " ";
            messageInput.focus();
            hideAutocomplete();
        };
        
        autocompletePopup.appendChild(item);
    });
    
    autocompletePopup.classList.add("active");
}

function hideAutocomplete() {
    autocompletePopup.classList.remove("active");
    autocompletePopup.innerHTML = "";
    autocompleteIndex = -1;
}

function updateAutocompleteSelection(items) {
    items.forEach((item, idx) => {
        if (idx === autocompleteIndex) {
            item.classList.add("selected");
            item.scrollIntoView({ block: "nearest" });
        } else {
            item.classList.remove("selected");
        }
    });
}

// Global Shortcuts (Keyboard Listeners matching the CLI App bindings)
document.onkeydown = (e) => {
    if (e.ctrlKey && e.shiftKey) {
        if (e.key === "F" || e.key === "f") {
            e.preventDefault();
            toggleChatSearch();
        }
    } else if (e.ctrlKey) {
        if (e.key === "f" || e.key === "F") {
            e.preventDefault();
            btnSidebarSearch.click();
        } else if (e.key === "n" || e.key === "N") {
            e.preventDefault();
            btnSidebarJoin.click();
        } else if (e.key === "p" || e.key === "P") {
            e.preventDefault();
            btnSidebarPM.click();
        } else if (e.key === "g" || e.key === "G") {
            e.preventDefault();
            btnSidebarRegister.click();
        } else if (e.key === "w" || e.key === "W") {
            e.preventDefault();
            btnSidebarCloseTab.click();
        }
    } else if (e.key === "Escape") {
        closeChatSearch();
    }
};

// User List Toggle & Filtering
btnToggleUsers.onclick = () => {
    usersSidebar.classList.toggle("active");
};

userSearchInput.oninput = () => {
    renderUsersList(state.activeTab);
};

// ---- CHANNEL SEARCH: client-side store + filter + sort ----

// All channels received from server stored here
let allSearchChannels = [];  // [{name, users, topic}]
let searchSortKey = "users";  // default sort: most users first
let searchSortAsc = false;

function openSearchModal() {
    openModal("search-modal");
    channelSearchFilter.value = "";
    searchStatusText.textContent = "Pulsa \"Buscar\" para cargar canales del servidor.";
    channelsTableBody.innerHTML = "";
    allSearchChannels = [];
    btnTriggerSearch.disabled = false;
    setTimeout(() => channelSearchFilter.focus(), 80);
}

btnSidebarSearch.onclick = openSearchModal;

// Trigger full list from IRC server
btnTriggerSearch.onclick = () => {
    allSearchChannels = [];
    channelsTableBody.innerHTML = "";
    btnTriggerSearch.disabled = true;
    searchStatusText.textContent = "⏳ Solicitando lista al servidor IRC...";
    sendAction("command", { text: "/list" });
};

// Real-time client-side filter as user types
channelSearchFilter.oninput = () => {
    renderSearchResults();
};

channelSearchFilter.onkeydown = (e) => {
    if (e.key === "Enter") btnTriggerSearch.click();
};

// Store incoming channel and re-render
function appendSearchItem(channel, users, topic) {
    allSearchChannels.push({ name: channel, users: parseInt(users) || 0, topic: topic || "" });
    // Throttle: only re-render every 30 channels to avoid DOM overload
    if (allSearchChannels.length % 30 === 0 || allSearchChannels.length < 30) {
        renderSearchResults();
        searchStatusText.textContent = `📡 Recibiendo... ${allSearchChannels.length} canales`;
    }
}

function renderSearchResults() {
    const filterText = channelSearchFilter.value.toLowerCase().trim();
    
    let results = allSearchChannels.filter(ch => {
        if (!filterText) return true;
        return ch.name.toLowerCase().includes(filterText) ||
               ch.topic.toLowerCase().includes(filterText);
    });
    
    // Sort
    results.sort((a, b) => {
        let va = a[searchSortKey];
        let vb = b[searchSortKey];
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va < vb) return searchSortAsc ? -1 : 1;
        if (va > vb) return searchSortAsc ? 1 : -1;
        return 0;
    });
    
    const fragment = document.createDocumentFragment();
    results.forEach(ch => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        
        const chanTd = document.createElement("td");
        chanTd.textContent = ch.name;
        chanTd.style.fontWeight = "600";
        chanTd.style.color = "var(--accent)";
        tr.appendChild(chanTd);
        
        const usersTd = document.createElement("td");
        usersTd.textContent = ch.users;
        tr.appendChild(usersTd);
        
        const topicTd = document.createElement("td");
        topicTd.textContent = ch.topic;
        topicTd.style.maxWidth = "300px";
        topicTd.style.overflow = "hidden";
        topicTd.style.textOverflow = "ellipsis";
        topicTd.style.whiteSpace = "nowrap";
        tr.appendChild(topicTd);
        
        const actionTd = document.createElement("td");
        const joinBtn = document.createElement("button");
        joinBtn.className = "join-btn";
        joinBtn.textContent = "Unirse";
        joinBtn.onclick = (e) => {
            e.stopPropagation();
            joinChannelFromSearch(ch.name);
        };
        actionTd.appendChild(joinBtn);
        tr.appendChild(actionTd);
        
        // Clicking the row also joins
        tr.ondblclick = () => joinChannelFromSearch(ch.name);
        
        fragment.appendChild(tr);
    });
    
    channelsTableBody.innerHTML = "";
    channelsTableBody.appendChild(fragment);
    
    if (allSearchChannels.length > 0) {
        searchStatusText.textContent = `✅ ${results.length} de ${allSearchChannels.length} canales mostrados. Doble-clic o botón para unirse.`;
    }
}

function joinChannelFromSearch(channel) {
    // Send join to server
    sendAction("command", { text: `/join ${channel}` });
    // Pre-create tab locally for instant UX feedback
    if (!state.joinedChats.includes(channel)) {
        state.joinedChats.push(channel);
        if (!state.messages[channel]) state.messages[channel] = [];
        renderActiveChatsList();
    }
    // Switch to the channel immediately
    switchTab(channel);
    closeModal("search-modal");
}

// Sortable column headers
function setupSortableHeaders() {
    const thead = document.querySelector("#channels-table thead");
    if (!thead) return;
    const headers = thead.querySelectorAll("th");
    const sortKeys = ["name", "users", "topic", null];
    headers.forEach((th, idx) => {
        if (!sortKeys[idx]) return;
        th.style.cursor = "pointer";
        th.style.userSelect = "none";
        th.title = "Clic para ordenar";
        th.onclick = () => {
            const key = sortKeys[idx];
            if (searchSortKey === key) {
                searchSortAsc = !searchSortAsc;
            } else {
                searchSortKey = key;
                searchSortAsc = key === "name"; // names asc by default, users desc
            }
            // Update header indicators
            headers.forEach(h => h.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(searchSortAsc ? "sort-asc" : "sort-desc");
            renderSearchResults();
        };
    });
}

// Close modals when clicking overlay
window.onclick = (e) => {
    if (e.target.classList.contains("modal")) {
        e.target.classList.remove("active");
    }
};

// Startup
window.onload = () => {
    loadConfigAndPresets();
    
    // Initialize the primary session using the tab's sessionId
    createSession(sessionId, true);
    
    // Bind theme selector button and modal cards
    const btnThemeToggle = document.getElementById("btn-theme-toggle");
    if (btnThemeToggle) {
        btnThemeToggle.onclick = () => {
            openModal("theme-modal");
            setTheme(localStorage.getItem("selected_theme") || "tokyo-night");
        };
    }
    document.querySelectorAll(".theme-card").forEach(card => {
        card.onclick = () => {
            const themeName = card.getAttribute("data-theme");
            setTheme(themeName);
        };
    });
    
    // Bind sounds checkboxes
    const chkMention = document.getElementById("sound-mention");
    const chkPm = document.getElementById("sound-pm");
    const chkJoin = document.getElementById("sound-join");
    if (chkMention && chkPm && chkJoin) {
        chkMention.checked = soundSettings.mention;
        chkPm.checked = soundSettings.pm;
        chkJoin.checked = soundSettings.join;
        
        chkMention.onchange = (e) => {
            soundSettings.mention = e.target.checked;
            localStorage.setItem("sound_mention", soundSettings.mention);
        };
        chkPm.onchange = (e) => {
            soundSettings.pm = e.target.checked;
            localStorage.setItem("sound_pm", soundSettings.pm);
        };
        chkJoin.onchange = (e) => {
            soundSettings.join = e.target.checked;
            localStorage.setItem("sound_join", soundSettings.join);
        };
    }
    
    // Test sounds buttons
    const btnTestMention = document.getElementById("btn-test-mention-sound");
    const btnTestPm = document.getElementById("btn-test-pm-sound");
    const btnTestJoin = document.getElementById("btn-test-join-sound");
    if (btnTestMention) btnTestMention.onclick = () => playNotificationSound("mention");
    if (btnTestPm) btnTestPm.onclick = () => playNotificationSound("pm");
    if (btnTestJoin) btnTestJoin.onclick = () => playNotificationSound("join");
    
    // Bind mentions tab button and modal
    const btnMentionsTab = document.getElementById("btn-mentions-tab");
    if (btnMentionsTab) {
        btnMentionsTab.onclick = () => {
            openModal("mentions-modal");
            unreadMentionsCount = 0;
            updateMentionsBadge();
            renderMentionsModal();
        };
    }
    
    const btnClearMentions = document.getElementById("btn-clear-mentions");
    if (btnClearMentions) {
        btnClearMentions.onclick = () => {
            mentionsList = [];
            localStorage.setItem("irc_mentions", JSON.stringify(mentionsList));
            renderMentionsModal();
        };
    }

    setupSortableHeaders();
    
    // Bind verification banner close button
    const btnCloseVerification = document.getElementById("btn-close-verification");
    const verificationBanner = document.getElementById("verification-banner");
    if (btnCloseVerification && verificationBanner) {
        btnCloseVerification.onclick = () => {
            verificationBanner.classList.add("hidden");
        };
    }
    
    // Bind "Add Server" button from the left sidebar
    const btnAddServer = document.getElementById("btn-add-server");
    if (btnAddServer) {
        btnAddServer.onclick = () => {
            createSession(null, true);
        };
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// PERSONAL SUGGESTION PANEL  (only active when personal/ module is installed)
// ═══════════════════════════════════════════════════════════════════════════
function showPersonalSuggestionPanel(data) {
    const panelId = "personal-suggest-panel";
    let panel = document.getElementById(panelId);

    if (!panel) {
        panel = document.createElement("div");
        panel.id = panelId;
        panel.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 9999;
            width: 360px; max-height: 70vh; overflow-y: auto;
            background: var(--bg-sidebar, #1f2335);
            border: 1px solid var(--accent, #7aa2f7);
            border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            padding: 16px; font-size: 13px; color: var(--text-main, #a9b1d6);
        `;
        document.body.appendChild(panel);
    }

    const copyBtn = (text, label, idx) => `
        <div style="
            background: var(--bg-main,#1a1b26); border-radius:8px;
            padding:10px 12px; margin-bottom:8px; cursor:pointer;
            border:1px solid var(--border-color,#292e42);
            transition: border-color .2s;"
         onmouseenter="this.style.borderColor='var(--accent,#7aa2f7)'"
         onmouseleave="this.style.borderColor='var(--border-color,#292e42)'"
         onclick="navigator.clipboard.writeText(${JSON.stringify(text)}).then(()=>{
             this.style.borderColor='var(--green,#9ece6a)';
             setTimeout(()=>this.style.borderColor='var(--border-color,#292e42)',1500);
         })"
         title="Clic para copiar al portapapeles">
            <span style="color:var(--text-muted,#565f89);font-size:10px;text-transform:uppercase;
                         letter-spacing:.8px;">${label} ${idx+1}</span><br>
            <span style="line-height:1.5;">${text}</span>
        </div>`;

    const aperturas = (data.aperturas || []).map((t, i) => copyBtn(t, "Apertura", i)).join("");
    const filtros   = (data.filtros   || []).map((q, i) => copyBtn(q, "Filtro",   i)).join("");

    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="font-weight:700;color:var(--accent,#7aa2f7);">
                ✦ Nuevo contacto:
                <span style="color:var(--text-highlight,#fff)">${data.nick}</span>
            </span>
            <button onclick="document.getElementById('${panelId}').remove()"
                    style="background:none;border:none;color:var(--text-muted,#565f89);
                           cursor:pointer;font-size:18px;line-height:1;padding:0 4px;">✕</button>
        </div>
        <div style="font-size:11px;color:var(--text-muted,#565f89);margin-bottom:14px;
                    padding:8px;background:var(--bg-main,#1a1b26);border-radius:6px;">
            ${data.resumen || ""}
        </div>
        <div style="font-weight:600;color:var(--text-muted,#565f89);font-size:10px;
                    text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
            Aperturas sugeridas <span style="opacity:.4;font-weight:400;">(clic = copiar)</span>
        </div>
        ${aperturas}
        <div style="font-weight:600;color:var(--text-muted,#565f89);font-size:10px;
                    text-transform:uppercase;letter-spacing:1px;margin:14px 0 8px;">
            Preguntas de filtro <span style="opacity:.4;font-weight:400;">(clic = copiar)</span>
        </div>
        ${filtros}
        <button onclick="document.getElementById('${panelId}').remove()"
                style="width:100%;margin-top:14px;padding:8px;border-radius:6px;
                       border:1px solid var(--border-color,#292e42);
                       background:none;color:var(--text-muted,#565f89);
                       cursor:pointer;font-size:12px;">
            Cerrar panel
        </button>
    `;
}
