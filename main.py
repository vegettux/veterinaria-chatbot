from datetime import datetime, timedelta
import logging
import os
import re
import unicodedata
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agenda import (
    buscar_cliente_por_dni,
    buscar_mascota_cliente_por_nombre,
    cancelar_cita_confirmada_por_mascota,
    existe_cita_mascota,
    get_fechas_disponibles_reales,
    listar_mascotas_cliente,
    db_healthcheck,
    obtener_cita_confirmada_por_mascota,
    registrar_cliente,
    registrar_mascota,
    reservar_cita,
    verificar_disponibilidad,
)

load_dotenv()

app = FastAPI(title="Veterinaria Chatbot API")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veterinaria.main")

conversation_store = {}
state_store = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str


HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot Veterinaria</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f4f7fb;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 760px;
            margin: 40px auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        .header {
            background: #2f855a;
            color: white;
            padding: 18px;
            font-size: 22px;
            font-weight: bold;
            text-align: center;
        }
        .chat-box {
            height: 480px;
            overflow-y: auto;
            padding: 20px;
            background: #fafafa;
        }
        .message {
            margin-bottom: 14px;
            padding: 12px 14px;
            border-radius: 10px;
            max-width: 85%;
            line-height: 1.45;
            white-space: pre-wrap;
        }
        .user {
            background: #dbeafe;
            margin-left: auto;
            text-align: right;
        }
        .bot {
            background: #e2e8f0;
            margin-right: auto;
            text-align: left;
        }
        .input-area {
            display: flex;
            gap: 10px;
            padding: 16px;
            border-top: 1px solid #ddd;
            background: white;
        }
        input {
            flex: 1;
            padding: 12px;
            border: 1px solid #ccc;
            border-radius: 8px;
            font-size: 16px;
        }
        button {
            background: #2f855a;
            color: white;
            border: none;
            padding: 12px 18px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover {
            background: #276749;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">Chatbot Veterinaria</div>

        <div id="chatBox" class="chat-box"></div>

        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Escribe tu mensaje...">
            <button onclick="sendMessage()">Enviar</button>
        </div>
    </div>

    <script>
        const sessionId = "sess-" + Math.random().toString(36).slice(2, 10);
        let bootstrapped = false;

        async function appendBotMessage(text) {
            const chatBox = document.getElementById("chatBox");
            const botDiv = document.createElement("div");
            botDiv.className = "message bot";
            botDiv.textContent = text;
            chatBox.appendChild(botDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function bootstrapChat() {
            if (bootstrapped) return;
            bootstrapped = true;

            try {
                const response = await fetch("/ask_bot", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        message: "__start__",
                        session_id: sessionId
                    })
                });

                const data = await response.json();
                await appendBotMessage(data.response);
            } catch (error) {
                await appendBotMessage("Se ha producido un error al iniciar el asistente.");
            }
        }

        async function sendMessage() {
            const input = document.getElementById("messageInput");
            const chatBox = document.getElementById("chatBox");
            const message = input.value.trim();

            if (!message) return;

            const userDiv = document.createElement("div");
            userDiv.className = "message user";
            userDiv.textContent = message;
            chatBox.appendChild(userDiv);

            input.value = "";

            try {
                const response = await fetch("/ask_bot", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    })
                });

                const data = await response.json();

                const botDiv = document.createElement("div");
                botDiv.className = "message bot";
                botDiv.textContent = data.response;
                chatBox.appendChild(botDiv);

                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (error) {
                const botDiv = document.createElement("div");
                botDiv.className = "message bot";
                botDiv.textContent = "Se ha producido un error al contactar con el asistente.";
                chatBox.appendChild(botDiv);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }

        document.getElementById("messageInput").addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMessage();
            }
        });

        bootstrapChat();
    </script>
</body>
</html>
"""


# =========================
# ESTADO
# =========================

def default_state():
    return {
        "phase": "start",
        "language": "es",
        "language_locked": False,
        "client": None,
        "client_new": {
            "dni": None,
            "nombre": None,
            "telefono": None,
            "email": None,
            "direccion": None,
        },
        "pending_dni_not_found": None,
        "pets": [],
        "active_pet": None,
        "offered_dates": [],
        "last_species": None,
        "last_sex": None,
        "last_age": None,
        "last_weight": None,
    }


def get_or_create_history(session_id: str):
    if session_id not in conversation_store:
        conversation_store[session_id] = []
    return conversation_store[session_id]


def get_or_create_state(session_id: str):
    if session_id not in state_store:
        state_store[session_id] = default_state()
    return state_store[session_id]


def reset_state(session_id: str):
    state_store[session_id] = default_state()


def guardar_respuesta(history, user_message: str, assistant_message: str):
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_message})


# =========================
# UTILIDADES DE TEXTO E IDIOMA
# =========================

def strip_accents(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(texto: str) -> str:
    return " ".join(strip_accents(texto.strip().lower()).split())


def texto(state: dict, es: str, en: str) -> str:
    return en if state.get("language") == "en" else es


def detectar_cambio_idioma_explicito(texto_usuario: str) -> Optional[str]:
    t = normalizar_texto(texto_usuario)

    if any(x in t for x in [
        "en ingles",
        "ingles",
        "in english",
        "english",
        "reply in english",
        "answer in english",
        "speak in english",
        "cambia a ingles",
        "cambiar a ingles",
        "habla en ingles",
    ]):
        return "en"

    if any(x in t for x in [
        "en espanol",
        "espanol",
        "español",
        "in spanish",
        "spanish",
        "reply in spanish",
        "answer in spanish",
        "speak in spanish",
        "cambia a espanol",
        "cambiar a espanol",
        "cambia a español",
        "cambiar a español",
        "habla en espanol",
        "habla en español",
    ]):
        return "es"

    return None


def detectar_idioma_por_turno(texto_usuario: str, state: dict) -> str:
    t = normalizar_texto(texto_usuario)

    english_markers = [
        "hello", "hi", "yes", "my dog", "my cat",
        "blood test", "surgery", "operation", "pick up", "drop off",
        "invoice", "emergency", "book", "spay", "castration",
        "pre-operative", "pre operative", "post-operative", "post operative",
        "what time", "when can i", "i want to", "can we do", "how long should",
        "dog", "cat",
    ]

    spanish_markers = [
        "hola", "si", "sí", "mi perro", "mi gato",
        "analitica", "analítica", "cirugia", "cirugía", "recoger", "llevar",
        "factura", "urgencia", "reservar", "esterilizacion", "esterilización",
        "preoperatorio", "postoperatorio", "que hora", "qué hora",
        "cuanto tiempo", "cuánto tiempo", "quiero", "perro", "gato",
    ]

    has_en = any(marker in t for marker in english_markers)
    has_es = any(marker in t for marker in spanish_markers)

    if has_en and not has_es:
        return "en"
    if has_es and not has_en:
        return "es"
    return state.get("language", "es")


def actualizar_idioma(state: dict, user_message: str):
    cambio = detectar_cambio_idioma_explicito(user_message)

    if cambio:
        state["language"] = cambio
        state["language_locked"] = True
        return

    if state.get("language_locked"):
        return

    state["language"] = detectar_idioma_por_turno(user_message, state)


def formatear_fecha_es(fecha_str: str) -> str:
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{dias[fecha_dt.weekday()]} {fecha_dt.day} de {meses[fecha_dt.month - 1]} de {fecha_dt.year}"


def formatear_fecha_en(fecha_str: str) -> str:
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    return fecha_dt.strftime("%A, %B %d, %Y")


def usuario_identificado(state: dict) -> bool:
    return bool(state.get("client"))


def usuario_identificado_y_mascota_cargada(state: dict) -> bool:
    return usuario_identificado(state) and bool(state.get("active_pet"))


def recordar_contexto_desde_texto(texto_usuario: str, state: dict):
    t = normalizar_texto(texto_usuario)

    if "gato" in t or "cat" in t:
        state["last_species"] = "gato"
    elif "perro" in t or "dog" in t:
        state["last_species"] = "perro"

    if "hembra" in t or "female" in t or "spay" in t:
        state["last_sex"] = "hembra"
    elif "macho" in t or "male" in t or "castration" in t:
        state["last_sex"] = "macho"

    edades = re.findall(r"\b(\d{1,2})\b", t)
    for e in edades:
        try:
            edad = int(e)
            if 0 <= edad <= 30:
                state["last_age"] = edad
                break
        except ValueError:
            pass

    pesos = re.findall(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*kg\b", t)
    for p in pesos:
        try:
            valor = float(p.replace(",", "."))
            if 0.1 <= valor <= 100:
                state["last_weight"] = valor
                break
        except ValueError:
            pass


def especie_contexto(state: dict) -> Optional[str]:
    if state.get("active_pet") and state["active_pet"].get("especie"):
        return state["active_pet"]["especie"]
    return state.get("last_species")


def sexo_contexto(state: dict) -> Optional[str]:
    if state.get("active_pet") and state["active_pet"].get("sexo"):
        return state["active_pet"]["sexo"]
    return state.get("last_sex")


def edad_contexto(state: dict) -> Optional[int]:
    if state.get("active_pet") and state["active_pet"].get("edad") is not None:
        return state["active_pet"]["edad"]
    return state.get("last_age")


def peso_contexto(state: dict) -> Optional[float]:
    if state.get("active_pet") and state["active_pet"].get("peso") not in (None, ""):
        try:
            return float(state["active_pet"]["peso"])
        except Exception:
            return None
    return state.get("last_weight")


# =========================
# MENSAJES
# =========================

def mensaje_inicio(state: dict) -> str:
    return texto(
        state,
        "Hola, soy el asistente de la clínica veterinaria especializado en esterilización y castración.\n\n"
        "Puedo ayudarte con:\n"
        "- reserva o cambio de cita de esterilización\n"
        "- instrucciones preoperatorias\n"
        "- horarios de entrega y recogida\n"
        "- logística general de la cirugía\n\n"
        "No atiendo urgencias, no realizo diagnósticos y no receto tratamientos.\n\n"
        "Pero para poder avanzar necesito saber si eres cliente de la clínica:\n"
        "1- Sí\n"
        "2- No",
        "Hello, I am the veterinary clinic assistant specialised in sterilisation and castration.\n\n"
        "I can help you with:\n"
        "- booking or changing a sterilisation appointment\n"
        "- pre-operative instructions\n"
        "- drop-off and pick-up times\n"
        "- general surgery logistics\n\n"
        "I do not handle emergencies, provide diagnoses, or prescribe treatments.\n\n"
        "But before we continue, I need to know whether you are already a client of the clinic:\n"
        "1- Yes\n"
        "2- No",
    )


def mensaje_saludo_simple(state: dict) -> str:
    return texto(
        state,
        "Hola. Antes de continuar, indícame si eres cliente de la clínica:\n1- Sí\n2- No",
        "Hello. Before we continue, please tell me whether you are already a client of the clinic:\n1- Yes\n2- No",
    )


def mensaje_error_si_no(state: dict) -> str:
    return texto(
        state,
        "No le he entendido, indique solo 1- Sí o 2- No.",
        "I didn't understand. Please answer only 1- Yes or 2- No.",
    )


def mensaje_cambio_idioma(state: dict) -> str:
    return texto(
        state,
        "De acuerdo. A partir de ahora te responderé en español.",
        "Understood. From now on I will reply in English.",
    )


def mensaje_otra_gestion(state: dict) -> str:
    return texto(
        state,
        "¿Deseas realizar otra consulta o gestión? Responde solo sí o no.",
        "Would you like to make another query or request? Please answer only yes or no.",
    )


def mensaje_volver_menu(state: dict) -> str:
    return texto(
        state,
        "Operación cancelada. Volvemos al menú principal del cliente.",
        "Operation cancelled. Returning to the main client menu.",
    )


def mensaje_saludo_identificado(state: dict) -> str:
    return texto(
        state,
        "Hola de nuevo. Ya te tengo identificado como cliente. Puedes hacer una consulta informativa o gestionar una mascota.\n\n"
        + construir_menu_cliente_identificado(state),
        "Hello again. I already have you identified as a client. You can ask an informational question or manage one of your pets.\n\n"
        + construir_menu_cliente_identificado(state),
    )


# =========================
# INTENTS
# =========================

def clasificar_categoria(especie: Optional[str], sexo: Optional[str], peso: Optional[float]) -> str:
    especie = (especie or "").lower()
    sexo = (sexo or "").lower()
    peso = float(peso or 0)

    if especie == "gato" and sexo == "macho":
        return "gato_macho"
    if especie == "gato" and sexo == "hembra":
        return "gata_hembra"
    if especie == "perro" and sexo == "macho":
        return "perro_macho"
    if especie == "perro" and sexo == "hembra":
        if peso <= 10:
            return "perra_0_10"
        if peso <= 20:
            return "perra_10_20"
        if peso <= 30:
            return "perra_20_30"
        if peso <= 40:
            return "perra_30_40"
        return "perra_40_mas"
    return "gato_macho"


def detectar_intent_global(texto_usuario: str) -> Optional[str]:
    t = normalizar_texto(texto_usuario)

    if t in {"atras", "atrás", "volver", "back"}:
        return "back"
    if t in {"cancelar", "cancel", "salir", "exit"}:
        return "cancel"
    if t in {"reiniciar", "reinicia", "reset", "empezar de nuevo", "start over"}:
        return "reset"

    if t in {"hola", "hello", "hi", "buenas"}:
        return "greeting"

    if any(x in t for x in ["what can you help me with", "what can you do", "en que puedes ayudarme", "que puedes hacer"]):
        return "scope"

    if any(x in t for x in ["cough", "prescribe", "vomit", "tos", "recetar", "prescribir", "medicina"]):
        return "medical_out_of_scope"

    if any(x in t for x in ["hit by a car", "bleeding", "emergency", "atropell", "sangrando", "urgencia", "accidente"]):
        return "emergency"

    if any(x in t for x in ["invoice", "speak to a person", "human", "factura", "hablar con una persona", "recepcion", "recepción"]):
        return "human_handoff"

    if any(x in t for x in ["drop off", "bring my cat", "bring my dog", "llevar a mi gato", "llevar a mi perro"]):
        return "dropoff"

    if any(x in t for x in ["pick up", "pickup", "when can i pick up", "recoger", "recogida"]):
        return "pickup"

    if any(x in t for x in ["blood test", "analitica", "analítica"]):
        return "blood_test"

    if any(x in t for x in ["in heat", "en celo"]):
        return "heat"

    if any(x in t for x in ["fast before", "how long should", "ayuno", "pre-op fasting"]):
        return "fasting"

    if any(x in t for x in ["drink water", "agua", "water right up until", "beber agua"]):
        return "water"

    if any(x in t for x in ["next week", "what days do you have capacity", "disponibilidad", "dias teneis disponibles", "dias tienen disponibles", "qué dias", "que dias"]):
        return "availability"

    if any(x in t for x in ["two other dogs", "dos perros", "large dog", "two dogs that day", "este jueves", "following tuesday", "martes siguiente"]):
        return "capacity_limit"

    return None


def interpretar_accion_mascota_libre(texto_usuario: str) -> Optional[int]:
    t = normalizar_texto(texto_usuario)

    mapa = {
        1: ["consultar cita", "ver cita", "check appointment", "appointment", "see appointment"],
        2: ["preoperatorio", "informacion del preoperatorio", "obtener informacion del preoperatorio",
            "pre operative instructions", "pre-operative instructions", "pre op instructions", "pre-op instructions"],
        3: ["postoperatorio", "informacion del postoperatorio", "obtener informacion del postoperatorio",
            "post operative instructions", "post-operative instructions", "post op instructions", "post-op instructions"],
        4: ["urgencia", "emergencia", "emergency", "emergency information"],
        5: ["cambiar cita", "solicitar cambio de cita", "reservar", "reservar cita", "book", "book surgery", "change appointment", "reschedule"],
    }

    for opcion, patrones in mapa.items():
        if t in patrones:
            return opcion
    return None


def texto_a_numero(texto_usuario: str) -> Optional[int]:
    t = normalizar_texto(texto_usuario)
    mapa = {
        "one": 1, "uno": 1,
        "two": 2, "dos": 2,
        "three": 3, "tres": 3,
        "four": 4, "cuatro": 4,
        "five": 5, "cinco": 5,
        "six": 6, "seis": 6,
        "seven": 7, "siete": 7,
    }
    return mapa.get(t)


# =========================
# RESPUESTAS INFORMATIVAS
# =========================

def respuesta_scope(state: dict) -> str:
    return texto(
        state,
        "Puedo ayudarte con citas, preoperatorio, recogida y logística de cirugía.",
        "I can help you with appointments, pre-operative instructions, pick-up times and surgery logistics.",
    )


def respuesta_fuera_scope(state: dict) -> str:
    return texto(
        state,
        "Lo siento, pero no puedo diagnosticar enfermedades ni recetar medicación. Para tos, vómitos, dolor u otros problemas clínicos, debes contactar con un veterinario. Si los síntomas son graves, acude a urgencias veterinarias.",
        "I'm sorry, but I cannot diagnose illnesses or prescribe medication. For cough, vomiting, pain or other clinical issues, you should contact a veterinarian. If the symptoms are severe, please go to an emergency veterinary clinic.",
    )


def respuesta_urgencia(state: dict) -> str:
    return texto(
        state,
        "La situación que describes parece una urgencia veterinaria. No debes esperar a una reserva. Acude ahora mismo a un centro veterinario de urgencias.",
        "The situation you describe sounds like a veterinary emergency. You should not wait for a booking. Please go to an emergency veterinary clinic immediately.",
    )


def respuesta_humano(state: dict) -> str:
    return texto(
        state,
        "Por supuesto. Si prefieres hablar con una persona, puedes contactar con recepción por teléfono o por email.",
        "Of course. If you prefer to speak to a person, you can contact reception by phone or email.",
    )


def respuesta_dropoff(state: dict) -> str:
    especie = especie_contexto(state)
    if especie == "perro":
        return texto(
            state,
            "Para un perro, la ventana de entrega el día de la cirugía es normalmente entre las 09:00 y las 10:30. Las cirugías se programan de lunes a jueves.",
            "For a dog, the drop-off window on the surgery day is usually between 09:00 and 10:30. Surgical procedures are scheduled from Monday to Thursday.",
        )
    return texto(
        state,
        "Para un gato, la ventana de entrega el día de la cirugía es normalmente entre las 08:00 y las 09:00. Debe acudir en transportín rígido, idealmente con manta o toalla.",
        "For a cat, the drop-off window on the surgery day is usually between 08:00 and 09:00. The cat should come in a rigid carrier, ideally with a blanket or towel.",
    )


def respuesta_pickup(state: dict) -> str:
    especie = especie_contexto(state)
    if especie == "perro":
        return texto(
            state,
            "Para un perro, la recogida habitual tras la cirugía es aproximadamente a las 12:00.",
            "For a dog, the usual pick-up time after surgery is around 12:00.",
        )
    return texto(
        state,
        "Para un gato, la recogida habitual tras la cirugía es aproximadamente a las 15:00.",
        "For a cat, the usual pick-up time after surgery is around 15:00.",
    )


def respuesta_blood_test(state: dict) -> str:
    edad = edad_contexto(state)
    if edad is None:
        return texto(
            state,
            "Si el animal tiene más de 6 años, la analítica preoperatoria es obligatoria. Por debajo de esa edad, suele ser recomendable pero no obligatoria.",
            "If the animal is older than 6 years, a pre-operative blood test is mandatory. Under that age, it is usually recommended but not mandatory.",
        )

    if edad > 6:
        return texto(
            state,
            f"Sí. Si el animal tiene {edad} años, la analítica preoperatoria es obligatoria antes de la esterilización.",
            f"Yes. If the animal is {edad} years old, a pre-operative blood test is mandatory before sterilisation.",
        )

    return texto(
        state,
        f"Si el animal tiene {edad} años, la analítica suele ser recomendable, pero no es obligatoria por debajo de 6 años.",
        f"If the animal is {edad} years old, a blood test is usually recommended, but it is not mandatory under the 6-year threshold.",
    )


def respuesta_heat(state: dict) -> str:
    return texto(
        state,
        "Una perra no puede programarse para esterilización mientras está en celo. Debe esperar aproximadamente 2 meses desde que finaliza el celo.",
        "A female dog cannot be scheduled for sterilisation while she is in heat. About 2 months must pass after the end of the heat cycle.",
    )


def respuesta_fasting(state: dict) -> str:
    return texto(
        state,
        "Antes de la operación, la regla habitual de ayuno es:\n- última comida entre 8 y 12 horas antes\n- agua permitida hasta 1 o 2 horas antes",
        "Before the operation, the usual fasting rule is:\n- last meal between 8 and 12 hours before surgery\n- water allowed until 1 or 2 hours before",
    )


def respuesta_water(state: dict) -> str:
    return texto(
        state,
        "No normalmente hasta justo antes de salir de casa. El agua suele permitirse solo hasta aproximadamente 1 o 2 horas antes de la operación.",
        "Not usually right up until leaving home. Water is normally allowed only until about 1 or 2 hours before the operation.",
    )


def respuesta_availability(state: dict) -> str:
    especie = especie_contexto(state) or "gato"
    sexo = sexo_contexto(state) or "hembra"
    peso = peso_contexto(state) or 4.0

    tipo = clasificar_categoria(especie, sexo, peso)
    fechas = get_fechas_disponibles_reales(tipo, limite=5)
    state["offered_dates"] = [f["fecha"] for f in fechas]

    if not fechas:
        return texto(
            state,
            "En este momento no hay fechas disponibles. Las cirugías se programan de lunes a jueves.",
            "There are currently no available dates. Surgical procedures are scheduled from Monday to Thursday.",
        )

    if state["language"] == "en":
        lineas = ["These are the next surgery dates with available capacity:"]
        for f in fechas:
            lineas.append(f"- {formatear_fecha_en(f['fecha'])}")
        lineas.append("")
        lineas.append("Surgical procedures are scheduled from Monday to Thursday only.")
        return "\n".join(lineas)

    lineas = ["Estas son las próximas fechas de cirugía con capacidad disponible:"]
    for f in fechas:
        lineas.append(f"- {f['texto']}")
    lineas.append("")
    lineas.append("Las cirugías se programan únicamente de lunes a jueves.")
    return "\n".join(lineas)


def respuesta_capacity_limit(state: dict) -> str:
    especie = "perro"
    sexo = sexo_contexto(state) or "hembra"
    peso = peso_contexto(state) or 35.0

    tipo = clasificar_categoria(especie, sexo, peso)
    fechas = get_fechas_disponibles_reales(tipo, limite=3)
    alternativa = fechas[0]["fecha"] if fechas else None
    alt_text = formatear_fecha_en(alternativa) if (alternativa and state["language"] == "en") else (
        formatear_fecha_es(alternativa) if alternativa else texto(state, "otra fecha disponible", "another available date")
    )

    return texto(
        state,
        f"Si ese día ya hay dos perros programados, la cirugía no puede aceptarse para esa fecha. La clínica aplica un máximo de dos perros por día y un límite diario de tiempo quirúrgico.\n\nUna alternativa razonable sería {alt_text}.",
        f"If there are already two dogs scheduled that day, the surgery cannot be accepted for that date. The clinic applies a maximum of two dogs per day and a daily surgery time limit.\n\nA reasonable alternative would be {alt_text}.",
    )


def construir_respuesta_informativa(intent: str, state: dict) -> str:
    if intent == "scope":
        return respuesta_scope(state)
    if intent == "medical_out_of_scope":
        return respuesta_fuera_scope(state)
    if intent == "emergency":
        return respuesta_urgencia(state)
    if intent == "human_handoff":
        return respuesta_humano(state)
    if intent == "dropoff":
        return respuesta_dropoff(state)
    if intent == "pickup":
        return respuesta_pickup(state)
    if intent == "blood_test":
        return respuesta_blood_test(state)
    if intent == "heat":
        return respuesta_heat(state)
    if intent == "fasting":
        return respuesta_fasting(state)
    if intent == "water":
        return respuesta_water(state)
    if intent == "availability":
        return respuesta_availability(state)
    if intent == "capacity_limit":
        return respuesta_capacity_limit(state)
    return texto(state, "No le he entendido.", "I didn't understand.")


# =========================
# MENÚS Y MASCOTAS
# =========================

def refrescar_mascotas_cliente(state: dict):
    if state["client"] and state["client"].get("id"):
        state["pets"] = listar_mascotas_cliente(state["client"]["id"])


def construir_menu_cliente_identificado(state: dict) -> str:
    nombre = state["client"]["nombre"]
    return texto(
        state,
        f"Te he identificado como cliente registrado, {nombre}.\n\n"
        "Indícame qué quieres hacer:\n"
        "1- Realizar una consulta informativa\n"
        "2- Gestionar una de mis mascotas",
        f"I have identified you as a registered client, {nombre}.\n\n"
        "Tell me what you want to do:\n"
        "1- Ask an informational question\n"
        "2- Manage one of my pets",
    )


def construir_menu_mascotas(state: dict) -> str:
    nombres = [m["nombre"].capitalize() for m in state.get("pets", [])]

    if state["language"] == "en":
        lineas = ["These pets are registered under your client profile. Tell me which pet you want to manage, or type the name of a new pet:"]
        for idx, nombre in enumerate(nombres, start=1):
            lineas.append(f"{idx}- {nombre}")
        lineas.append(f"{len(nombres) + 1}- New pet")
        return "\n".join(lineas)

    lineas = ["Tienes registradas estas mascotas. Indícame sobre qué mascota quieres gestionar la intervención, o si es una nueva mascota escribe su nombre:"]
    for idx, nombre in enumerate(nombres, start=1):
        lineas.append(f"{idx}- {nombre}")
    lineas.append(f"{len(nombres) + 1}- Nueva mascota")
    return "\n".join(lineas)


def construir_menu_mascota(state: dict) -> str:
    nombre = state["active_pet"]["nombre"].capitalize()
    fecha = obtener_cita_confirmada_por_mascota(state["active_pet"]["id"])

    if state["language"] == "en":
        if fecha:
            cabecera = f"I have loaded {nombre}. There is currently a confirmed appointment for {formatear_fecha_en(fecha)}."
            opcion_5 = f"5- Request an appointment change for {nombre}"
        else:
            cabecera = f"I have loaded {nombre}. There is currently no confirmed appointment."
            opcion_5 = f"5- Book a new procedure for {nombre}"

        return (
            f"{cabecera}\n\n"
            "Tell me what you want to do:\n"
            f"1- Check appointment for {nombre}\n"
            "2- Get pre-operative information\n"
            "3- Get post-operative information\n"
            "4- Emergency information\n"
            f"{opcion_5}"
        )

    if fecha:
        cabecera = f"He cargado a {nombre}. Actualmente tiene una cita confirmada para el {formatear_fecha_es(fecha)}."
        opcion_5 = f"5- Solicitar cambio de cita de {nombre}"
    else:
        cabecera = f"He cargado a {nombre}. No tiene ninguna cita confirmada."
        opcion_5 = f"5- Reservar una nueva intervención para {nombre}"

    return (
        f"{cabecera}\n\n"
        "Indícame qué quieres hacer:\n"
        f"1- Consultar cita de {nombre}\n"
        "2- Obtener información del preoperatorio\n"
        "3- Obtener información del postoperatorio\n"
        "4- Información en caso de urgencia\n"
        f"{opcion_5}"
    )


def seleccionar_pet_activa(state: dict, pet: dict):
    state["active_pet"] = {
        "id": pet["id"],
        "cliente_id": pet["cliente_id"],
        "nombre": pet["nombre"],
        "especie": pet["especie"],
        "sexo": pet["sexo"],
        "peso": pet["peso"],
        "edad": pet["edad"],
        "microchip": pet["tiene_microchip"],
        "vacuna_rabia": pet["tiene_vacuna_rabia"],
        "vacunado_desparasitado": None,
        "enfermedad": None,
        "detalle_enfermedad": None,
        "registrada": True,
    }
    state["last_species"] = pet["especie"]
    state["last_sex"] = pet["sexo"]
    state["last_age"] = pet["edad"]
    try:
        state["last_weight"] = float(pet["peso"]) if pet["peso"] is not None else None
    except Exception:
        state["last_weight"] = None


def iniciar_alta_mascota(state: dict, nombre: str):
    state["active_pet"] = {
        "id": None,
        "cliente_id": state["client"]["id"],
        "nombre": nombre.strip().lower(),
        "especie": None,
        "sexo": None,
        "peso": None,
        "edad": None,
        "microchip": None,
        "vacuna_rabia": None,
        "vacunado_desparasitado": None,
        "enfermedad": None,
        "detalle_enfermedad": None,
        "registrada": False,
    }


# =========================
# RESPUESTAS DETALLADAS DE MASCOTA
# =========================

def respuesta_preoperatorio_detallada(pet: dict, state: dict) -> str:
    especie = pet["especie"]
    sexo = pet["sexo"]
    edad = pet["edad"]
    peso = pet["peso"]
    categoria = clasificar_categoria(especie, sexo, float(peso or 0))
    nombre = pet["nombre"].capitalize()

    if state["language"] == "en":
        lineas = [f"Pre-operative instructions for {nombre}:", ""]
        lineas.append(f"- Surgical category: {categoria}")
        if peso not in (None, "", 0):
            lineas.append(f"- Declared weight: {peso} kg")
        lineas.append("- Rabies vaccination up to date.")
        lineas.append("- Microchip implanted, or authorisation to implant it on the same day.")
        lineas.append("- Suitable general health status.")
        lineas.append("- Proper vaccination and deworming status.")
        if edad is not None and edad > 6:
            lineas.append("- Because the animal is older than 6 years, a pre-operative blood test is mandatory.")
        if especie == "perro" and sexo == "hembra":
            lineas.append("- If she is in heat, surgery cannot be scheduled.")
            lineas.append("- At least 2 months must pass after the end of heat.")
        lineas.append("- Last meal between 8 and 12 hours before surgery.")
        lineas.append("- Water allowed until 1 or 2 hours before surgery.")
        lineas.append("- Bring signed informed consent.")
        lineas.append("- Bring health booklet or pet passport.")
        if especie == "gato":
            lineas.append("- Bring the cat in a rigid carrier, ideally with a blanket or towel.")
        else:
            lineas.append("- Bring the dog with a lead or harness, and a muzzle if needed.")
        return "\n".join(lineas)

    lineas = [f"Instrucciones preoperatorias para {nombre}:", ""]
    lineas.append(f"- Categoría quirúrgica: {categoria}")
    if peso not in (None, "", 0):
        lineas.append(f"- Peso declarado: {peso} kg")
    lineas.append("- Vacuna antirrábica al día.")
    lineas.append("- Microchip implantado o autorización para implantarlo el mismo día.")
    lineas.append("- Estado sanitario adecuado.")
    lineas.append("- Vacunación y desparasitación correctas.")
    if edad is not None and edad > 6:
        lineas.append("- Al tener más de 6 años, requiere analítica preoperatoria obligatoria.")
    if especie == "perro" and sexo == "hembra":
        lineas.append("- Si está en celo, no puede operarse.")
        lineas.append("- Debe esperar al menos 2 meses tras finalizar el celo.")
    lineas.append("- Última comida entre 8 y 12 horas antes.")
    lineas.append("- Puede beber agua hasta 1 o 2 horas antes.")
    lineas.append("- Consentimiento informado firmado.")
    lineas.append("- Cartilla o pasaporte del animal.")
    if especie == "gato":
        lineas.append("- Debe acudir en transportín rígido, idealmente con manta o toalla.")
    else:
        lineas.append("- Debe acudir con correa o arnés, y con bozal si es necesario.")
    return "\n".join(lineas)


def respuesta_postoperatorio_detallada(pet: dict, state: dict) -> str:
    nombre = pet["nombre"].capitalize()

    if state["language"] == "en":
        return (
            f"Post-operative instructions for {nombre}:\n\n"
            "- Keep the animal in a calm and warm environment.\n"
            "- Avoid stress and intense physical activity.\n"
            "- Offer water once fully awake.\n"
            "- Offer a small meal 6 to 8 hours later.\n"
            "- Stitches are internal and absorbable.\n"
            "- Prevent licking the wound.\n"
            "- Use an Elizabethan collar or protective body if needed.\n"
            "- Contact the clinic if there is bleeding, discharge, an open wound, fever or severe lethargy."
        )

    return (
        f"Instrucciones postoperatorias para {nombre}:\n\n"
        "- Mantener en ambiente tranquilo y cálido.\n"
        "- Evitar estrés y actividad física intensa.\n"
        "- Dar agua cuando esté completamente despierta/o.\n"
        "- Dar comida entre 6 y 8 horas después, en poca cantidad.\n"
        "- Los puntos son internos y reabsorbibles.\n"
        "- Evitar que lama la herida.\n"
        "- Usar collar isabelino o body si es necesario.\n"
        "- Contactar con la clínica si hay sangrado, supuración, herida abierta, fiebre o decaimiento importante."
    )


def construir_texto_fechas(tipo_cirugia: str, state: dict):
    fechas = get_fechas_disponibles_reales(tipo_cirugia, limite=5)
    state["offered_dates"] = [f["fecha"] for f in fechas]

    if not fechas:
        return texto(
            state,
            "En este momento no hay fechas disponibles para ese tipo de cirugía.\nPor favor, contacta con la clínica para revisar una alternativa.",
            "There are currently no available dates for that type of surgery.\nPlease contact the clinic to review an alternative.",
        )

    if state["language"] == "en":
        lineas = ["Available surgery dates:"]
        for f in fechas:
            lineas.append(f"- {formatear_fecha_en(f['fecha'])}")
    else:
        lineas = ["Fechas disponibles para la cirugía:"]
        for f in fechas:
            lineas.append(f"- {f['texto']}")

    if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
        lineas.append("")
        lineas.append(texto(state, "La entrega para perros es entre las 09:00 y las 10:30.", "Dog drop-off is between 09:00 and 10:30."))
        lineas.append(texto(state, "La recogida aproximada es a las 12:00.", "Approximate pick-up time is 12:00."))
    else:
        lineas.append("")
        lineas.append(texto(state, "La entrega para gatos es entre las 08:00 y las 09:00.", "Cat drop-off is between 08:00 and 09:00."))
        lineas.append(texto(state, "La recogida aproximada es a las 15:00.", "Approximate pick-up time is 15:00."))

    lineas.append("")
    lineas.append(texto(
        state,
        "Indícame qué día prefieres, eligiendo una de las fechas ofrecidas.",
        "Please tell me which day you prefer by choosing one of the offered dates.",
    ))
    return "\n".join(lineas)


# =========================
# VALIDADORES
# =========================

def validar_opcion_si_no(texto_usuario: str) -> Optional[bool]:
    t = normalizar_texto(texto_usuario)
    if t in {"1", "si", "sí", "yes", "y"}:
        return True
    if t in {"2", "no", "n"}:
        return False
    return None


def validar_dni(texto_usuario: str) -> Optional[str]:
    t = texto_usuario.strip().upper()
    if re.fullmatch(r"\d{8}[A-Z]", t):
        return t
    return None


def validar_nombre_persona(texto_usuario: str) -> Optional[str]:
    t = texto_usuario.strip()
    patron = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{2,80}$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_telefono(texto_usuario: str) -> Optional[str]:
    t = re.sub(r"\s+", "", texto_usuario.strip())
    if re.fullmatch(r"\d{9}", t):
        return t
    return None


def validar_email(texto_usuario: str) -> Optional[str]:
    t = texto_usuario.strip()
    patron = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_direccion(texto_usuario: str) -> Optional[str]:
    t = texto_usuario.strip()
    if len(t) >= 5:
        return t
    return None


def validar_menu_numerico(texto_usuario: str, min_op: int, max_op: int) -> Optional[int]:
    t = texto_usuario.strip()
    if not t.isdigit():
        return None
    op = int(t)
    if min_op <= op <= max_op:
        return op
    return None


def validar_nombre_mascota(texto_usuario: str) -> Optional[str]:
    t = texto_usuario.strip()
    patron = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]{2,40}$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_especie(texto_usuario: str) -> Optional[str]:
    t = normalizar_texto(texto_usuario)
    if t in {"perro", "dog"}:
        return "perro"
    if t in {"gato", "cat"}:
        return "gato"
    return None


def validar_sexo(texto_usuario: str) -> Optional[str]:
    t = normalizar_texto(texto_usuario)
    if t in {"macho", "male"}:
        return "macho"
    if t in {"hembra", "female"}:
        return "hembra"
    return None


def validar_entero_positivo(texto_usuario: str, min_val=0, max_val=30) -> Optional[int]:
    t = normalizar_texto(texto_usuario)
    if t.isdigit():
        n = int(t)
        if min_val <= n <= max_val:
            return n
    return None


def validar_decimal_positivo(texto_usuario: str, min_val=0.1, max_val=100.0) -> Optional[float]:
    t = normalizar_texto(texto_usuario).replace(",", ".")
    try:
        n = float(t)
        if min_val <= n <= max_val:
            return n
    except ValueError:
        pass
    return None


def validar_opcion_accion_mascota(texto_usuario: str) -> Optional[int]:
    return validar_menu_numerico(texto_usuario, 1, 5)


def validar_fecha(texto_usuario: str) -> Optional[str]:
    t = normalizar_texto(texto_usuario)
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }

    for sep in ["/", "-"]:
        if sep in t:
            partes = [p.strip() for p in t.split(sep)]
            try:
                if len(partes) == 2:
                    dia = int(partes[0])
                    mes = int(partes[1])
                    anio = datetime.now().year
                    return datetime(anio, mes, dia).strftime("%Y-%m-%d")
                if len(partes) == 3:
                    dia = int(partes[0])
                    mes = int(partes[1])
                    anio = int(partes[2])
                    if anio < 100:
                        anio = 2000 + anio
                    return datetime(anio, mes, dia).strftime("%Y-%m-%d")
            except ValueError:
                pass

    palabras = t.replace(",", " ").replace(".", " ").split()
    dia = None
    mes = None
    anio = datetime.now().year

    for palabra in palabras:
        if palabra.isdigit():
            numero = int(palabra)
            if 1 <= numero <= 31 and dia is None:
                dia = numero
                continue
            if numero >= 100:
                anio = numero
            elif 25 <= numero <= 99:
                anio = 2000 + numero
        if palabra in meses:
            mes = meses[palabra]

    if dia and mes:
        try:
            return datetime(anio, mes, dia).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


# =========================
# ENDPOINTS
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE


@app.get("/healthz")
def healthz():
    db = db_healthcheck()
    return {
        "status": "ok" if db.get("status") == "ok" else "degraded",
        "db": db,
        "env": {
            "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
            "POSTGRES_URL": bool(os.getenv("POSTGRES_URL")),
            "POSTGRES_PRISMA_URL": bool(os.getenv("POSTGRES_PRISMA_URL")),
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        },
    }


@app.get("/fechas_disponibles")
def fechas_disponibles(tipo: str = "perro_macho"):
    return {"fechas": get_fechas_disponibles_reales(tipo)}


@app.post("/ask_bot")
def ask_bot(data: ChatRequest):
    try:
        session_id = data.session_id.strip() if data.session_id else "default"
        user_message = data.message.strip()

        history = get_or_create_history(session_id)
        state = get_or_create_state(session_id)

        if user_message == "__start__":
            state["phase"] = "client_status"
            respuesta = mensaje_inicio(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if not user_message:
            return {
                "response": texto(state, "Por favor, escribe un mensaje.", "Please type a message."),
                "session_id": session_id,
            }

        cambio_exp = detectar_cambio_idioma_explicito(user_message)
        actualizar_idioma(state, user_message)
        recordar_contexto_desde_texto(user_message, state)

        if cambio_exp:
            respuesta = mensaje_cambio_idioma(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        intent = detectar_intent_global(user_message)

        if intent == "reset":
            idioma = state.get("language", "es")
            idioma_locked = state.get("language_locked", False)
            reset_state(session_id)
            state = get_or_create_state(session_id)
            state["language"] = idioma
            state["language_locked"] = idioma_locked
            state["phase"] = "client_status"
            respuesta = mensaje_inicio(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if intent == "cancel":
            if usuario_identificado(state):
                state["active_pet"] = None
                state["phase"] = "client_identified"
                respuesta = mensaje_volver_menu(state) + "\n\n" + construir_menu_cliente_identificado(state)
            else:
                state["phase"] = "client_status"
                respuesta = mensaje_inicio(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if intent == "back":
            if state["phase"] == "info_mode":
                state["phase"] = "client_identified"
                respuesta = construir_menu_cliente_identificado(state)
            elif usuario_identificado_y_mascota_cargada(state):
                state["active_pet"] = None
                state["phase"] = "pet_selection"
                refrescar_mascotas_cliente(state)
                respuesta = construir_menu_mascotas(state)
            elif usuario_identificado(state):
                state["phase"] = "client_identified"
                respuesta = construir_menu_cliente_identificado(state)
            else:
                state["phase"] = "client_status"
                respuesta = mensaje_inicio(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        # antes de identificarse
        if not usuario_identificado(state):
            if intent == "greeting":
                respuesta = mensaje_saludo_simple(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if intent in {"scope", "medical_out_of_scope", "emergency", "human_handoff"}:
                respuesta = construir_respuesta_informativa(intent, state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "start":
            state["phase"] = "client_status"
            respuesta = mensaje_inicio(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "post_pet_resolution":
            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                state["phase"] = "client_identified"
                respuesta = construir_menu_cliente_identificado(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            respuesta = texto(
                state,
                "De acuerdo. Gracias por contactar con la clínica veterinaria. Hasta pronto.",
                "Understood. Thank you for contacting the veterinary clinic. Goodbye.",
            )
            guardar_respuesta(history, user_message, respuesta)
            reset_state(session_id)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "client_status":
            if intent == "greeting":
                respuesta = mensaje_saludo_simple(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                state["phase"] = "existing_client_dni"
                respuesta = texto(state, "Por favor, indícame tu DNI.", "Please provide your ID number.")
            else:
                state["phase"] = "new_client_dni"
                respuesta = texto(state, "Para darte de alta como nuevo cliente, por favor, indícame tu DNI.", "To register you as a new client, please provide your ID number.")

            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "existing_client_dni":
            dni = validar_dni(user_message)
            if dni is None:
                respuesta = texto(state, "No le he entendido, indique un DNI válido.", "I didn't understand. Please provide a valid ID number.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cliente = buscar_cliente_por_dni(dni)
            if not cliente:
                state["pending_dni_not_found"] = dni
                state["phase"] = "confirm_new_client_from_missing_dni"
                respuesta = texto(
                    state,
                    "No he encontrado ningún cliente con ese DNI en la base de datos de la clínica.\nCompruebe si el número de DNI es correcto.\n\nSi el DNI es correcto y desea continuar con la gestión, ¿nos autoriza a darlo de alta como nuevo cliente en la base de datos de la clínica?\n1- Sí\n2- No",
                    "I could not find any client with that ID number in the clinic database.\nPlease check whether the ID number is correct.\n\nIf the ID number is correct and you wish to continue, do you authorise us to register you as a new client in the clinic database?\n1- Yes\n2- No",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client"] = cliente
            refrescar_mascotas_cliente(state)
            state["phase"] = "client_identified"
            respuesta = construir_menu_cliente_identificado(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "confirm_new_client_from_missing_dni":
            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                state["client_new"]["dni"] = state["pending_dni_not_found"]
                state["pending_dni_not_found"] = None
                state["phase"] = "new_client_nombre"
                respuesta = texto(state, "De acuerdo. Para continuar con el alta como nuevo cliente, indíqueme su nombre y apellidos.", "Understood. To continue with the new client registration, please provide your full name.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["pending_dni_not_found"] = None
            state["phase"] = "client_status"
            respuesta = mensaje_saludo_simple(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_dni":
            dni = validar_dni(user_message)
            if dni is None:
                respuesta = texto(state, "No le he entendido, indique su DNI.", "I didn't understand. Please provide your ID number.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cliente_existente = buscar_cliente_por_dni(dni)
            if cliente_existente:
                state["client"] = cliente_existente
                refrescar_mascotas_cliente(state)
                state["phase"] = "client_identified"
                respuesta = construir_menu_cliente_identificado(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["dni"] = dni
            state["phase"] = "new_client_nombre"
            respuesta = texto(state, "Dígame su nombre y apellidos.", "Please provide your full name.")
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_nombre":
            nombre = validar_nombre_persona(user_message)
            if nombre is None:
                respuesta = texto(state, "No le he entendido, indique su nombre y apellidos.", "I didn't understand. Please provide your full name.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["nombre"] = nombre
            state["phase"] = "new_client_telefono"
            respuesta = texto(state, "Indícame tu número de teléfono.", "Please provide your phone number.")
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_telefono":
            telefono = validar_telefono(user_message)
            if telefono is None:
                respuesta = texto(state, "No le he entendido, indique su número de teléfono.", "I didn't understand. Please provide your phone number.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["telefono"] = telefono
            state["phase"] = "new_client_email"
            respuesta = texto(state, "Indícame tu email.", "Please provide your email.")
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_email":
            email = validar_email(user_message)
            if email is None:
                respuesta = texto(state, "No le he entendido, indique un email válido.", "I didn't understand. Please provide a valid email.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["email"] = email
            state["phase"] = "new_client_direccion"
            respuesta = texto(state, "Indícame tu dirección.", "Please provide your address.")
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_direccion":
            direccion = validar_direccion(user_message)
            if direccion is None:
                respuesta = texto(state, "No le he entendido, indique su dirección.", "I didn't understand. Please provide your address.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["direccion"] = direccion
            exito, resultado = registrar_cliente(
                state["client_new"]["nombre"],
                state["client_new"]["dni"],
                state["client_new"]["telefono"],
                state["client_new"]["email"],
                state["client_new"]["direccion"],
            )

            if not exito:
                state["phase"] = "new_client_dni"
                respuesta = texto(
                    state,
                    f"No se ha podido completar el registro: {resultado} Indique de nuevo su DNI.",
                    f"The registration could not be completed: {resultado} Please provide your ID number again.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client"] = {
                "id": int(resultado),
                "nombre": state["client_new"]["nombre"],
                "dni": state["client_new"]["dni"],
                "telefono": state["client_new"]["telefono"],
                "email": state["client_new"]["email"],
                "direccion": state["client_new"]["direccion"],
            }
            refrescar_mascotas_cliente(state)
            state["phase"] = "client_identified"
            respuesta = construir_menu_cliente_identificado(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "client_identified":
            if intent == "greeting":
                respuesta = mensaje_saludo_identificado(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            op = validar_menu_numerico(user_message, 1, 2)

            if op is None:
                if intent in {"scope", "medical_out_of_scope", "emergency", "human_handoff",
                              "dropoff", "pickup", "blood_test", "heat", "fasting", "water",
                              "availability", "capacity_limit"}:
                    respuesta = construir_respuesta_informativa(intent, state)
                    guardar_respuesta(history, user_message, respuesta)
                    return {"response": respuesta, "session_id": session_id}

                respuesta = texto(
                    state,
                    "No te he entendido. Puedes:\n"
                    "1- Escribir 1 o 2\n"
                    "2- Hacer una pregunta directamente\n"
                    "3- Escribir 'atrás' para volver\n\n"
                    + construir_menu_cliente_identificado(state),
                    "I didn't understand. You can:\n"
                    "1- Type 1 or 2\n"
                    "2- Ask a question directly\n"
                    "3- Type 'back' to return\n\n"
                    + construir_menu_cliente_identificado(state),
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if op == 1:
                state["phase"] = "info_mode"
                respuesta = texto(
                    state,
                    "De acuerdo. Puedes hacerme tu consulta informativa.",
                    "Understood. You may ask me your informational question.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            refrescar_mascotas_cliente(state)
            state["phase"] = "pet_selection"
            respuesta = construir_menu_mascotas(state) if state["pets"] else texto(
                state,
                "No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota.",
                "There are no pets registered for this client. Please tell me your pet's name.",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "info_mode":
            if intent == "greeting":
                respuesta = texto(
                    state,
                    "Hola. Estoy listo para tu consulta informativa.",
                    "Hello. I'm ready for your informational question.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if intent in {"scope", "medical_out_of_scope", "emergency", "human_handoff",
                          "dropoff", "pickup", "blood_test", "heat", "fasting", "water",
                          "availability", "capacity_limit"}:
                respuesta = construir_respuesta_informativa(intent, state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            op = validar_menu_numerico(user_message, 1, 2)
            if op == 2:
                refrescar_mascotas_cliente(state)
                state["phase"] = "pet_selection"
                respuesta = construir_menu_mascotas(state) if state["pets"] else texto(
                    state,
                    "No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota.",
                    "There are no pets registered for this client. Please tell me your pet's name.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            respuesta = texto(
                state,
                "No te he entendido. Puedes hacerme una pregunta informativa, escribir 2 para gestionar una mascota o escribir 'atrás' para volver.",
                "I didn't understand. You can ask me an informational question, type 2 to manage a pet, or type 'back' to return.",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "pet_selection":
            refrescar_mascotas_cliente(state)
            total = len(state["pets"])

            if total == 0:
                nombre_nueva = validar_nombre_mascota(user_message)
                if nombre_nueva is not None:
                    iniciar_alta_mascota(state, nombre_nueva)
                    state["phase"] = "new_pet_especie"
                    respuesta = texto(
                        state,
                        f"Gracias. ¿Qué especie es {state['active_pet']['nombre'].capitalize()}, perro o gato?",
                        f"Thank you. What species is {state['active_pet']['nombre'].capitalize()}, dog or cat?",
                    )
                    guardar_respuesta(history, user_message, respuesta)
                    return {"response": respuesta, "session_id": session_id}

                respuesta = texto(
                    state,
                    "No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota.",
                    "There are no pets registered for this client. Please tell me your pet's name.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            op = validar_menu_numerico(user_message, 1, total + 1)
            if op is None:
                op = texto_a_numero(user_message)

            if op is not None:
                if 1 <= op <= total:
                    pet = state["pets"][op - 1]
                    seleccionar_pet_activa(state, pet)
                    state["phase"] = "existing_pet_action"
                    respuesta = construir_menu_mascota(state)
                    guardar_respuesta(history, user_message, respuesta)
                    return {"response": respuesta, "session_id": session_id}

                if op == total + 1:
                    state["phase"] = "new_pet_name"
                    respuesta = texto(
                        state,
                        "Indique el nombre de su nueva mascota para proceder a su registro:",
                        "Please provide the name of your new pet to proceed with registration:",
                    )
                    guardar_respuesta(history, user_message, respuesta)
                    return {"response": respuesta, "session_id": session_id}

            pet = buscar_mascota_cliente_por_nombre(state["client"]["id"], user_message)
            if pet:
                seleccionar_pet_activa(state, pet)
                state["phase"] = "existing_pet_action"
                respuesta = construir_menu_mascota(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            nombre_nueva = validar_nombre_mascota(user_message)
            if nombre_nueva is not None:
                iniciar_alta_mascota(state, nombre_nueva)
                state["phase"] = "new_pet_especie"
                respuesta = texto(
                    state,
                    f"Gracias. ¿Qué especie es {state['active_pet']['nombre'].capitalize()}, perro o gato?",
                    f"Thank you. What species is {state['active_pet']['nombre'].capitalize()}, dog or cat?",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            respuesta = construir_menu_mascotas(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_name":
            nombre_mascota = validar_nombre_mascota(user_message)
            if nombre_mascota is None:
                respuesta = texto(
                    state,
                    "No le he entendido, indique el nombre de su nueva mascota.",
                    "I didn't understand. Please provide the name of your new pet.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            iniciar_alta_mascota(state, nombre_mascota)
            state["phase"] = "new_pet_especie"
            respuesta = texto(
                state,
                f"Gracias. ¿Qué especie es {state['active_pet']['nombre'].capitalize()}, perro o gato?",
                f"Thank you. What species is {state['active_pet']['nombre'].capitalize()}, dog or cat?",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_especie":
            especie = validar_especie(user_message)
            if especie is None:
                respuesta = texto(
                    state,
                    f"No le he entendido.\n\nIndique si {state['active_pet']['nombre'].capitalize()} es perro o gato.\n\n(O escriba 'atrás' para volver al menú)",
                    f"I didn't understand.\n\nPlease indicate whether {state['active_pet']['nombre'].capitalize()} is a dog or a cat.\n\n(Type 'back' to return to the menu)",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["especie"] = especie
            state["phase"] = "new_pet_sexo"
            respuesta = texto(
                state,
                f"Perfecto. ¿{state['active_pet']['nombre'].capitalize()} es macho o hembra?",
                f"Perfect. Is {state['active_pet']['nombre'].capitalize()} male or female?",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_sexo":
            sexo = validar_sexo(user_message)
            if sexo is None:
                respuesta = texto(
                    state,
                    f"No le he entendido. Indique si {state['active_pet']['nombre'].capitalize()} es macho o hembra.",
                    f"I didn't understand. Please indicate whether {state['active_pet']['nombre'].capitalize()} is male or female.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["sexo"] = sexo
            state["phase"] = "new_pet_edad"
            respuesta = texto(
                state,
                f"¿Cuántos años tiene {state['active_pet']['nombre'].capitalize()}?",
                f"How old is {state['active_pet']['nombre'].capitalize()}?",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_edad":
            edad = validar_entero_positivo(user_message, 0, 30)
            if edad is None:
                respuesta = texto(
                    state,
                    f"No le he entendido. Indique la edad en número de {state['active_pet']['nombre'].capitalize()}.",
                    f"I didn't understand. Please provide the age of {state['active_pet']['nombre'].capitalize()} as a number.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["edad"] = edad

            if state["active_pet"]["especie"] == "perro" and state["active_pet"]["sexo"] == "hembra":
                state["phase"] = "new_pet_peso"
                respuesta = texto(
                    state,
                    f"¿Cuánto pesa aproximadamente {state['active_pet']['nombre'].capitalize()}?",
                    f"What is the approximate weight of {state['active_pet']['nombre'].capitalize()}?",
                )
            else:
                state["phase"] = "clinical_microchip"
                respuesta = texto(
                    state,
                    f"¿{state['active_pet']['nombre'].capitalize()} tiene microchip?\n1- Sí\n2- No",
                    f"Does {state['active_pet']['nombre'].capitalize()} have a microchip?\n1- Yes\n2- No",
                )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_peso":
            peso = validar_decimal_positivo(user_message, 0.1, 100.0)
            if peso is None:
                respuesta = texto(
                    state,
                    f"No le he entendido. Indique el peso en número de {state['active_pet']['nombre'].capitalize()}.",
                    f"I didn't understand. Please provide the weight of {state['active_pet']['nombre'].capitalize()} as a number.",
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["peso"] = peso
            state["phase"] = "new_pet_celo"
            respuesta = texto(
                state,
                f"¿{state['active_pet']['nombre'].capitalize()} está actualmente en celo?\n1- Sí\n2- No",
                f"Is {state['active_pet']['nombre'].capitalize()} currently in heat?\n1- Yes\n2- No",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_celo":
            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                respuesta = respuesta_heat(state)
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            state["phase"] = "clinical_microchip"
            respuesta = texto(
                state,
                f"¿{state['active_pet']['nombre'].capitalize()} tiene microchip?\n1- Sí\n2- No",
                f"Does {state['active_pet']['nombre'].capitalize()} have a microchip?\n1- Yes\n2- No",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_microchip":
            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["active_pet"]["microchip"] = valor
            state["phase"] = "clinical_vacuna"
            respuesta = texto(
                state,
                "¿Tiene la vacuna antirrábica al día?\n1- Sí\n2- No",
                "Is the rabies vaccination up to date?\n1- Yes\n2- No",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_vacuna":
            valor = validar_opcion_si_no(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no(state)
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["active_pet"]["vacuna_rabia"] = valor

            if not valor:
                respuesta = texto(
                    state,
                    "La vacuna antirrábica es obligatoria. Sin la vacuna antirrábica al día no se puede realizar la esterilización.",
                    "Rabies vaccination is mandatory. Sterilisation cannot be performed until the rabies vaccination is up to date.",
                )
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if not state["active_pet"]["registrada"]:
                peso_valor = state["active_pet"]["peso"] if state["active_pet"]["peso"] is not None else 0.0
                mascota_id = registrar_mascota(
                    state["client"]["id"],
                    state["active_pet"]["nombre"],
                    state["active_pet"]["especie"],
                    state["active_pet"]["sexo"],
                    peso_valor,
                    state["active_pet"]["edad"] if state["active_pet"]["edad"] is not None else 0,
                    state["active_pet"]["microchip"] if state["active_pet"]["microchip"] is not None else False,
                    state["active_pet"]["vacuna_rabia"],
                )
                pet = buscar_mascota_cliente_por_nombre(state["client"]["id"], state["active_pet"]["nombre"])
                if pet:
                    seleccionar_pet_activa(state, pet)
                else:
                    state["active_pet"]["id"] = mascota_id
                    state["active_pet"]["registrada"] = True
                refrescar_mascotas_cliente(state)

            state["phase"] = "existing_pet_action"
            respuesta = construir_menu_mascota(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "existing_pet_action":
            op = validar_opcion_accion_mascota(user_message)
            if op is None:
                op = interpretar_accion_mascota_libre(user_message)

            if op is None:
                respuesta = texto(
                    state,
                    "No le he entendido. Por favor, seleccione una opción válida:\n\n" + construir_menu_mascota(state),
                    "I didn't understand. Please select a valid option:\n\n" + construir_menu_mascota(state),
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]

            if op == 1:
                fecha = obtener_cita_confirmada_por_mascota(pet["id"])
                if fecha:
                    respuesta = texto(
                        state,
                        f"{pet['nombre'].capitalize()} tiene una cita confirmada para el {formatear_fecha_es(fecha)}.",
                        f"{pet['nombre'].capitalize()} has a confirmed appointment for {formatear_fecha_en(fecha)}.",
                    )
                else:
                    respuesta = texto(
                        state,
                        f"No consta ninguna cita confirmada para {pet['nombre'].capitalize()}.",
                        f"There is no confirmed appointment recorded for {pet['nombre'].capitalize()}.",
                    )
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 2:
                respuesta = respuesta_preoperatorio_detallada(pet, state)
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 3:
                respuesta = respuesta_postoperatorio_detallada(pet, state)
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 4:
                respuesta = respuesta_urgencia(state)
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 5:
                fecha_actual = obtener_cita_confirmada_por_mascota(pet["id"])
                tipo_cirugia = clasificar_categoria(pet["especie"], pet["sexo"], float(pet["peso"] or 0))

                if fecha_actual:
                    fecha_actual_dt = datetime.strptime(fecha_actual, "%Y-%m-%d").date()
                    hoy = datetime.now().date()

                    if fecha_actual_dt - hoy < timedelta(days=1):
                        respuesta = texto(
                            state,
                            f"{pet['nombre'].capitalize()} ya tiene una cita confirmada para el {formatear_fecha_es(fecha_actual)}.\n\nNo es posible solicitar el cambio de cita con menos de 24 horas de antelación.",
                            f"{pet['nombre'].capitalize()} already has a confirmed appointment for {formatear_fecha_en(fecha_actual)}.\n\nIt is not possible to request an appointment change with less than 24 hours' notice.",
                        )
                        state["phase"] = "post_pet_resolution"
                        respuesta_final = respuesta + "\n\n" + mensaje_otra_gestion(state)
                        guardar_respuesta(history, user_message, respuesta_final)
                        return {"response": respuesta_final, "session_id": session_id}

                    state["phase"] = "waiting_for_reschedule_date"
                    respuesta = texto(
                        state,
                        f"{pet['nombre'].capitalize()} ya tiene una cita confirmada para el {formatear_fecha_es(fecha_actual)}.\n\nVoy a mostrarte nuevas fechas disponibles para solicitar el cambio de cita.\n\n{construir_texto_fechas(tipo_cirugia, state)}",
                        f"{pet['nombre'].capitalize()} already has a confirmed appointment for {formatear_fecha_en(fecha_actual)}.\n\nI will show you new available dates to request an appointment change.\n\n{construir_texto_fechas(tipo_cirugia, state)}",
                    )
                else:
                    state["phase"] = "waiting_for_date"
                    respuesta = texto(
                        state,
                        f"De acuerdo. Voy a gestionar la intervención para {pet['nombre'].capitalize()}.\n\n{construir_texto_fechas(tipo_cirugia, state)}",
                        f"Understood. I will manage the procedure for {pet['nombre'].capitalize()}.\n\n{construir_texto_fechas(tipo_cirugia, state)}",
                    )

                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "waiting_for_reschedule_date":
            fecha_detectada = validar_fecha(user_message)
            if fecha_detectada is None:
                respuesta = texto(state, "Por favor, indícame una fecha válida para el cambio de cita.", "Please tell me a valid date for the appointment change.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if state["offered_dates"] and fecha_detectada not in state["offered_dates"]:
                fechas_legibles = [
                    formatear_fecha_en(f) if state["language"] == "en" else formatear_fecha_es(f)
                    for f in state["offered_dates"]
                ]
                respuesta = texto(
                    state,
                    "Debes elegir una de las fechas que te he ofrecido previamente para el cambio de cita.\nFechas válidas:\n- " + "\n- ".join(fechas_legibles),
                    "You must choose one of the dates previously offered for the appointment change.\nValid dates:\n- " + "\n- ".join(fechas_legibles),
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]
            tipo_cirugia = clasificar_categoria(pet["especie"], pet["sexo"], float(pet["peso"] or 0))

            disponible, mensaje = verificar_disponibilidad(fecha_detectada, tipo_cirugia)
            if not disponible:
                respuesta = texto(state, f"No hay disponibilidad para ese día. {mensaje}", f"There is no availability for that day. {mensaje}")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cancelada = cancelar_cita_confirmada_por_mascota(pet["id"])
            if not cancelada:
                respuesta = texto(state, "No se ha podido tramitar el cambio de cita en este momento.", "The appointment change could not be processed at this time.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            exito, mensaje = reservar_cita(fecha_detectada, state["client"]["id"], pet["id"], tipo_cirugia)
            if not exito:
                respuesta = texto(state, f"No se ha podido completar el cambio de cita. {mensaje}", f"The appointment change could not be completed. {mensaje}")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_texto = formatear_fecha_en(fecha_detectada) if state["language"] == "en" else formatear_fecha_es(fecha_detectada)
            if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
                entrega = "09:00 and 10:30" if state["language"] == "en" else "09:00 y 10:30"
                recogida = "12:00"
            else:
                entrega = "08:00 and 09:00" if state["language"] == "en" else "08:00 y 09:00"
                recogida = "15:00"

            state["phase"] = "post_pet_resolution"
            state["offered_dates"] = []
            refrescar_mascotas_cliente(state)

            respuesta = texto(
                state,
                f"El cambio de cita para la esterilización de {pet['nombre'].capitalize()} ha quedado confirmado para el {fecha_texto}.\n\n- Entrega: entre las {entrega}.\n- Recogida aproximada: {recogida}.\n- Recuerda traer el consentimiento informado y la cartilla o pasaporte de {pet['nombre'].capitalize()}.\n\n{mensaje_otra_gestion(state)}",
                f"The appointment change for the sterilisation of {pet['nombre'].capitalize()} has been confirmed for {fecha_texto}.\n\n- Drop-off: between {entrega}.\n- Approximate pick-up: {recogida}.\n- Remember to bring the signed consent form and the health booklet or passport for {pet['nombre'].capitalize()}.\n\n{mensaje_otra_gestion(state)}",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "waiting_for_date":
            fecha_detectada = validar_fecha(user_message)
            if fecha_detectada is None:
                respuesta = texto(state, "Por favor, indícame una fecha válida para la cirugía.", "Please provide a valid date for the surgery.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if state["offered_dates"] and fecha_detectada not in state["offered_dates"]:
                fechas_legibles = [
                    formatear_fecha_en(f) if state["language"] == "en" else formatear_fecha_es(f)
                    for f in state["offered_dates"]
                ]
                respuesta = texto(
                    state,
                    "Debes elegir una de las fechas que te he ofrecido previamente.\nFechas válidas:\n- " + "\n- ".join(fechas_legibles),
                    "You must choose one of the dates previously offered.\nValid dates:\n- " + "\n- ".join(fechas_legibles),
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_dt = datetime.strptime(fecha_detectada, "%Y-%m-%d")
            ahora = datetime.now()

            if fecha_dt.date() < ahora.date():
                respuesta = texto(state, "No hay disponibilidad para ese día. No se pueden reservar citas para días pasados.", "There is no availability for that day. Appointments cannot be booked for past dates.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if fecha_dt.date() == ahora.date() and ahora.hour >= 17:
                respuesta = texto(state, "No hay disponibilidad para ese día. No es posible reservar cita para hoy porque el horario de reserva ya no está disponible.", "There is no availability for that day. It is not possible to book for today because the booking time window is no longer available.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]
            tipo_cirugia = clasificar_categoria(pet["especie"], pet["sexo"], float(pet["peso"] or 0))

            if existe_cita_mascota(fecha_detectada, pet["id"]):
                respuesta = texto(state, f"Ya existe una cita confirmada para {pet['nombre'].capitalize()} en esa fecha. Por favor, elige otro día.", f"There is already a confirmed appointment for {pet['nombre'].capitalize()} on that date. Please choose another day.")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            disponible, mensaje = verificar_disponibilidad(fecha_detectada, tipo_cirugia)
            if not disponible:
                respuesta = texto(state, f"No hay disponibilidad para ese día. {mensaje}", f"There is no availability for that day. {mensaje}")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            exito, mensaje = reservar_cita(fecha_detectada, state["client"]["id"], pet["id"], tipo_cirugia)
            if not exito:
                respuesta = texto(state, f"No se ha podido reservar la cita. {mensaje}", f"The appointment could not be booked. {mensaje}")
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_texto = formatear_fecha_en(fecha_detectada) if state["language"] == "en" else formatear_fecha_es(fecha_detectada)
            if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
                entrega = "09:00 and 10:30" if state["language"] == "en" else "09:00 y 10:30"
                recogida = "12:00"
            else:
                entrega = "08:00 and 09:00" if state["language"] == "en" else "08:00 y 09:00"
                recogida = "15:00"

            state["phase"] = "post_pet_resolution"
            state["offered_dates"] = []
            refrescar_mascotas_cliente(state)

            respuesta = texto(
                state,
                f"La cita para la esterilización de {pet['nombre'].capitalize()} queda confirmada para el {fecha_texto}.\n\n- Entrega: entre las {entrega}.\n- Recogida aproximada: {recogida}.\n- Recuerda traer el consentimiento informado y la cartilla o pasaporte de {pet['nombre'].capitalize()}.\n\n{mensaje_otra_gestion(state)}",
                f"The appointment for the sterilisation of {pet['nombre'].capitalize()} has been confirmed for {fecha_texto}.\n\n- Drop-off: between {entrega}.\n- Approximate pick-up: {recogida}.\n- Remember to bring the signed consent form and the health booklet or passport for {pet['nombre'].capitalize()}.\n\n{mensaje_otra_gestion(state)}",
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        respuesta = texto(state, "No le he entendido. ¿Puede repetir la opción?", "I didn't understand. Could you repeat the option?")
        guardar_respuesta(history, user_message, respuesta)
        return {"response": respuesta, "session_id": session_id}

    except Exception as e:
        logger.exception("Error en /ask_bot. session_id=%s", data.session_id if data.session_id else "default")
        return {
            "response": f"Error: {str(e)}",
            "session_id": data.session_id if data.session_id else "default",
        }