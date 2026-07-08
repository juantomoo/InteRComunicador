# InteRComunicador 🚀

> **Cliente de Chat IRC Moderno de Alto Rendimiento para Terminal (TUI) y Web App Premium**

InteRComunicador es un cliente de salas de chat global diseñado para ser rápido, seguro, altamente personalizable y libre de bloqueos. Cuenta con una interfaz rica y reactiva de estética premium que puedes ejecutar en tu terminal clásica o en tu navegador web moderno.

Está construido en Python utilizando **Textual** (para el modo consola TUI) y **FastAPI + WebSockets** (para el modo Web App), manejando conexiones asíncronas directas al protocolo IRC para permitirte chatear con personas de todo el mundo con el máximo rendimiento.

---

## 🌟 Características Principales

### 🖥️ Interfaz Web App Premium (Navegador)
*   **🎨 Selector de Temas Visuales**: Selector interactivo integrado con 5 esquemas de color premium:
    *   *Tokyo Night* (Oscuro Cyberpunk original)
    *   *Dracula* (Esquema clásico de alto contraste)
    *   *Nord* (Estética ártica limpia y fría)
    *   *Solarized Dark* (Temática retro marina de contraste suave)
    *   *Light* (Tema claro minimalista y limpio)
*   **🔊 Alertas Sonoras Sintetizadas**: Sistema de audio nativo (Web Audio API) que sintetiza tonos configurables sin requerir recursos externos:
    *   *Menciones*: Campana doble aguda agradable.
    *   *Mensajes Privados (PM)*: Acorde dulce cálido.
    *   *Unirse a canal (Join)*: Efecto ascendente ligero.
*   **🔔 Notificaciones de Escritorio**: Sistema nativo de notificaciones push del sistema operativo para menciones y chats directos cuando la pestaña no está activa.
*   **🔍 Buscador Integrado en Chat**: Barra de búsqueda interactiva en el chat activo (`Ctrl+Shift+F`) con resaltado de coincidencias en tiempo real, contador de resultados y navegación de coincidencias anterior/siguiente.
*   **📂 Historial Local Persistente**: Sistema de persistencia local en `localStorage` con **autolimpieza de 15 días (TTL)** para mantener el rendimiento y liberar espacio automáticamente.
*   **⭐ Gestión de Favoritos e Ignorados**:
    *   *Favoritos*: Identificación de nicks favoritos con un ícono de estrella (`★`) en la lista de usuarios y notificaciones mejoradas.
    *   *Ignorados*: Lista negra persistente que oculta los mensajes y actividades de usuarios no deseados.
*   **🎛️ Menú de Acciones Colapsable**: Panel lateral de acciones rápidas plegable con persistencia de estado tras recargar la página.
*   **👤 Avatares Inteligentes y Personalizados**:
    *   Resolución automática de fotos de perfil (Gravatar/Libravatar) si el usuario tiene una cuenta registrada en su apodo o correo en el campo de Nombre Real (`realname`).
    *   Avatar autogenerado de Dicebear (`bottts-neutral`) como fallback basado en el nick.

### 📟 Interfaz de Terminal (TUI / Consola)
*   **Tokyo Night Aesthetic**: Paleta de colores oscura optimizada para terminales modernos de 256 colores y True Color.
*   **Navegación Eficiente**: Pestañas dedicadas para cada canal y charla privada, con indicadores visuales de mensajes no leídos.
*   **Tabla de Canales Interactiva**: Buscador interactivo de canales públicos mediante una tabla de datos ordenable que permite unirse con doble clic o Enter.

---

## 🚀 Cómo Iniciar

El proyecto incluye un script automatizado `run.sh` que configura automáticamente el entorno virtual (`venv`), actualiza `pip`, instala las dependencias necesarias e inicia la interfaz deseada.

### Ejecución Rápida
Abre una terminal en el directorio del proyecto y ejecuta:

```bash
./run.sh
```

El script te dará a elegir entre:
1.  **Interfaz Web Premium (Opción 1 - Recomendado)**: Levanta el backend FastAPI y te invita a abrir [http://localhost:8000](http://localhost:8000) en tu navegador.
2.  **Interfaz de Terminal (Opción 2)**: Inicia la consola interactiva basada en Textual en tu terminal actual.

### Ejecución Manual (Web App)
Si prefieres iniciar el servidor web directamente sin menús interactivos:

```bash
# Activar entorno virtual
source venv/bin/activate

# Iniciar servidor web
python web_server.py
```
Luego navega a [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## ⌨️ Atajos de Teclado del Sistema

### Atajos en Web App (Navegador)
*   `Ctrl + Shift + F`: Abrir/Cerrar la barra de búsqueda en el chat activo.
*   `Ctrl + F`: Abrir el modal de búsqueda de canales públicos.
*   `Ctrl + N`: Abrir diálogo para unirse a una nueva sala.
*   `Ctrl + P`: Abrir diálogo para iniciar chat privado con un usuario.
*   `Ctrl + G`: Abrir modal para registrar el nick actual con NickServ.
*   `Ctrl + W`: Cerrar la pestaña de chat activa.
*   `Escape`: Cerrar cualquier ventana emergente o modal abierto.

### Atajos en Terminal (TUI)
*   `Ctrl + C`: Salir de la aplicación de forma segura.
*   `Ctrl + F`: Buscar canales públicos en el servidor activo.
*   `Ctrl + N`: Unirse a un canal ingresando su nombre.
*   `Ctrl + P`: Iniciar chat privado (Mensaje Directo) con un usuario.
*   `Ctrl + R`: Registrar el nick actual en NickServ.

---

## 💬 Comandos de la Consola de Entrada

En la caja de texto inferior de cualquier pestaña activa, puedes ejecutar comandos rápidos usando la barra diagonal (`/`):

| Comando | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `/join #canal` | Unirse a un canal específico. | `/join #python` |
| `/part [#canal] [mensaje]` | Salir de un canal con un mensaje de despedida. | `/part #python ¡Hasta luego!` |
| `/query nick` | Abrir pestaña de chat privado directo con un usuario. | `/query maria` |
| `/msg nick mensaje` | Enviar mensaje privado rápido sin cambiar de pestaña. | `/msg pedro ¡hola!` |
| `/nick nuevo_nick` | Cambiar tu nombre o apodo actual en la red. | `/nick JuanPro` |
| `/list` | Abrir ventana interactiva de búsqueda de canales públicos. | `/list` |
| `/me acción` | Enviar una acción descriptiva en tercera persona. | `/me sonríe` |
| `/register contraseña email` | Registrar tu apodo actual con el servicio NickServ. | `/register secreta123 mail@ejemplo.com` |
| `/identify contraseña` | Iniciar sesión / identificarse con tu contraseña en NickServ. | `/identify secreta123` |
| `/verify código` | Validar el registro de tu nick usando el código recibido. | `/verify 98A7F` |
| `/away [mensaje]` | Marcarse como ausente en la red IRC con un estado. | `/away Ocupado almorzando` |
| `/back` o `/away` | Volver del estado ausente a disponible. | `/back` |
| `/clear` | Limpiar el historial visual de mensajes de la pestaña activa. | `/clear` |
| `/raw comando` | Enviar un comando crudo directo al protocolo IRC. | `/raw WHOIS pedro` |
| `/help` | Ver la lista de comandos detallada dentro del chat. | `/help` |

---

## 🛠️ Detalles Técnicos y Arquitectura

*   **FastAPI & Uvicorn**: Servidor asíncrono rápido encargado de servir la interfaz y canalizar la conexión WebSocket cliente-servidor.
*   **WebSockets**: Comunicación bidireccional en tiempo real entre la Web App y el cliente IRC asíncrono para renderizado de chat sin latencia.
*   **Asyncio Streams**: Conexiones nativas no-bloqueantes de Python al socket IRC.
*   **CSS Dinámico**: Estilizado premium responsivo con variables customizadas según el tema cargado en tiempo de ejecución.
*   **JSON Config**: Preferencias guardadas localmente en tu directorio de configuración local `~/.config/intercomunicador/config.json`.
