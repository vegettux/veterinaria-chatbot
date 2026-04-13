from datetime import datetime, timedelta
import os
import re
from typing import Optional

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
    obtener_cita_confirmada_por_mascota,
    registrar_cliente,
    registrar_mascota,
    reservar_cita,
    verificar_disponibilidad,
)

app = FastAPI(title="Veterinaria Chatbot API")

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
            max-width: 700px;
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
            height: 420px;
            overflow-y: auto;
            padding: 20px;
            background: #fafafa;
        }
        .message {
            margin-bottom: 14px;
            padding: 12px 14px;
            border-radius: 10px;
            max-width: 80%;
            line-height: 1.4;
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

        <div id="chatBox" class="chat-box">
            <div class="message bot">Hola, soy el asistente de la clínica veterinaria especializado en esterilización. ¿En qué puedo ayudarte?</div>
        </div>

        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Escribe tu mensaje...">
            <button onclick="sendMessage()">Enviar</button>
        </div>
    </div>

    <script>
        const sessionId = "sess-" + Math.random().toString(36).slice(2, 10);

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
                    headers: {
                        "Content-Type": "application/json"
                    },
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
    </script>
</body>
</html>
"""


# =========================
# DOCUMENTOS
# =========================

def cargar_documento(nombre_archivo: str) -> str:
    ruta = os.path.join("docs", nombre_archivo)
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "No se ha podido cargar la información en este momento."


def limpiar_markdown_para_chat(texto: str) -> str:
    lineas_limpias = []

    for linea in texto.splitlines():
        l = linea.strip()

        if not l:
            lineas_limpias.append("")
            continue

        if l == "---":
            continue

        l = re.sub(r"^#{1,6}\s*", "", l)
        l = l.replace("**", "")

        lineas_limpias.append(l)

    texto_final = "\n".join(lineas_limpias)
    texto_final = re.sub(r"\n{3,}", "\n\n", texto_final).strip()
    return texto_final


def obtener_texto_documento_chat(nombre_archivo: str) -> str:
    return limpiar_markdown_para_chat(cargar_documento(nombre_archivo))


# =========================
# ESTADO
# =========================

def default_state():
    return {
        "phase": "start",
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
# UTILIDADES
# =========================

def normalizar_texto(texto: str) -> str:
    return " ".join(texto.strip().lower().split())


def formatear_fecha_es(fecha_str: str) -> str:
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{dias[fecha_dt.weekday()]} {fecha_dt.day} de {meses[fecha_dt.month - 1]} de {fecha_dt.year}"


def clasificar_categoria_mascota(pet: dict) -> dict:
    especie = (pet.get("especie") or "").lower()
    sexo = (pet.get("sexo") or "").lower()
    peso = float(pet.get("peso") or 0)

    if especie == "gato" and sexo == "macho":
        return {
            "categoria": "gato_macho",
            "etiqueta": "gato macho",
            "cirugia": "castración felina macho",
        }

    if especie == "gato" and sexo == "hembra":
        return {
            "categoria": "gata_hembra",
            "etiqueta": "gata hembra",
            "cirugia": "ovariohisterectomía felina hembra",
        }

    if especie == "perro" and sexo == "macho":
        return {
            "categoria": "perro_macho",
            "etiqueta": "perro macho",
            "cirugia": "castración canina macho",
        }

    if especie == "perro" and sexo == "hembra":
        if peso <= 10:
            categoria = "perra_0_10"
            tramo = "0–10 kg"
        elif peso <= 20:
            categoria = "perra_10_20"
            tramo = "10–20 kg"
        elif peso <= 30:
            categoria = "perra_20_30"
            tramo = "20–30 kg"
        elif peso <= 40:
            categoria = "perra_30_40"
            tramo = "30–40 kg"
        else:
            categoria = "perra_40_mas"
            tramo = "+40 kg"

        return {
            "categoria": categoria,
            "etiqueta": f"perra hembra {tramo}",
            "cirugia": "ovariohisterectomía canina hembra",
        }

    return {
        "categoria": "desconocida",
        "etiqueta": "categoría no definida",
        "cirugia": "no definida",
    }


def obtener_tipo_cirugia_desde_pet(pet: dict) -> str:
    return clasificar_categoria_mascota(pet)["categoria"]


def construir_texto_fechas(tipo_cirugia: str, state: dict):
    fechas = get_fechas_disponibles_reales(tipo_cirugia, limite=5)
    state["offered_dates"] = [f["fecha"] for f in fechas]

    if not fechas:
        return (
            "En este momento no hay fechas disponibles para ese tipo de cirugía.\n"
            "Por favor, contacta con la clínica para revisar una alternativa."
        )

    lineas = ["Fechas disponibles para la cirugía:"]
    for f in fechas:
        lineas.append(f"- {f['texto']}")

    if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
        lineas.append("")
        lineas.append("La entrega para perros es entre las 09:00 y las 10:30.")
        lineas.append("La recogida aproximada es a las 12:00.")
    else:
        lineas.append("")
        lineas.append("La entrega para gatos es entre las 08:00 y las 09:00.")
        lineas.append("La recogida aproximada es a las 15:00.")

    lineas.append("")
    lineas.append("Indícame qué día prefieres, eligiendo una de las fechas ofrecidas.")
    return "\n".join(lineas)


def construir_respuesta_preoperatorio_filtrada(pet: dict) -> str:
    info = clasificar_categoria_mascota(pet)

    nombre = (pet.get("nombre") or "tu mascota").capitalize()
    edad = pet.get("edad")
    peso = pet.get("peso")

    lineas = [f"Instrucciones preoperatorias para {nombre}:", ""]

    lineas.append("Clasificación clínica:")
    lineas.append(f"- Categoría: {info['etiqueta']}")
    lineas.append(f"- Tipo de cirugía prevista: {info['cirugia']}")

    if peso not in (None, "", 0):
        lineas.append(f"- Peso declarado: {peso} kg")

    lineas.append("")
    lineas.append("Requisitos obligatorios antes de la cirugía:")
    lineas.extend([
        "- Vacuna antirrábica al día.",
        "- Microchip implantado o autorización para implantarlo el mismo día.",
        "- Estado sanitario adecuado.",
        "- Vacunación y desparasitación correctas.",
    ])
    lineas.append("")

    if edad is not None and edad > 6:
        lineas.append("Caso especial aplicable:")
        lineas.append("- Al tener más de 6 años, requiere analítica preoperatoria obligatoria.")
        lineas.append("")

    if info["categoria"].startswith("perra_"):
        lineas.append("Caso especial aplicable:")
        lineas.append("- Si está en celo, no puede operarse.")
        lineas.append("- Debe esperar al menos 2 meses tras finalizar el celo.")
        lineas.append("")

    lineas.append("Ayuno preoperatorio:")
    lineas.extend([
        "- Última comida entre 8 y 12 horas antes.",
        "- Puede beber agua hasta 1 o 2 horas antes.",
    ])
    lineas.append("")

    lineas.append("Documentación obligatoria:")
    lineas.extend([
        "- Consentimiento informado firmado.",
        "- Cartilla o pasaporte del animal.",
    ])
    lineas.append("")

    if (pet.get("especie") or "").lower() == "gato":
        lineas.append("Cómo debe acudir el animal:")
        lineas.extend([
            "- En transportín rígido.",
            "- Con manta o toalla.",
            "- Si trae varios gatos, cada uno en su propio transportín.",
        ])
    else:
        lineas.append("Cómo debe acudir el animal:")
        lineas.extend([
            "- Con correa o arnés.",
            "- Con bozal si muerde a desconocidos.",
        ])

    lineas.append("")
    lineas.append("Información adicional:")
    lineas.extend([
        "- Si existe una enfermedad conocida, debe comunicarse previamente a la clínica.",
        "- Si no puede acudir, debe avisar con al menos 24 horas de antelación.",
        "- Para dudas relacionadas con la cirugía puede contactar por teléfono o WhatsApp en horario de apertura.",
    ])

    return "\n".join(lineas).strip()


def construir_respuesta_postoperatorio_filtrada(pet: dict) -> str:
    info = clasificar_categoria_mascota(pet)

    nombre = (pet.get("nombre") or "tu mascota").capitalize()
    edad = pet.get("edad")
    peso = pet.get("peso")

    lineas = [f"Instrucciones postoperatorias para {nombre}:", ""]

    lineas.append("Clasificación clínica:")
    lineas.append(f"- Categoría: {info['etiqueta']}")
    lineas.append(f"- Tipo de cirugía realizada: {info['cirugia']}")

    if peso not in (None, "", 0):
        lineas.append(f"- Peso declarado: {peso} kg")

    lineas.append("")

    if info["categoria"] == "gato_macho":
        lineas.extend([
            "Aspectos específicos de su caso:",
            "- La recuperación suele ser más rápida.",
            "- El control postoperatorio suele ser más sencillo.",
            "",
        ])
    elif info["categoria"] == "gata_hembra":
        lineas.extend([
            "Aspectos específicos de su caso:",
            "- Al ser una cirugía abdominal, requiere mayor control de la herida.",
            "- Deben evitarse saltos y actividad intensa.",
            "",
        ])
    elif info["categoria"] == "perro_macho":
        lineas.extend([
            "Aspectos específicos de su caso:",
            "- La recuperación suele ser más sencilla que en una perra hembra.",
            "- Debe vigilarse bien la herida y evitar el lamido.",
            "",
        ])
    elif info["categoria"].startswith("perra_"):
        lineas.extend([
            "Aspectos específicos de su caso:",
            "- Requiere más vigilancia durante los primeros días.",
            "- Al tratarse de cirugía más invasiva, debe controlarse mejor la herida.",
            "- Debe evitar actividad física intensa durante más tiempo.",
            "",
        ])

    lineas.append("Cuidados generales:")
    lineas.extend([
        "- Mantener en ambiente tranquilo y cálido.",
        "- Evitar estrés y actividad física intensa.",
        "- Dar agua cuando esté completamente despierta/o.",
        "- Dar comida entre 6 y 8 horas después, en poca cantidad.",
        "- Los puntos son internos y reabsorbibles.",
        "- Evitar que lama la herida.",
        "- Usar collar isabelino o body si es necesario.",
        "- Limpiar solo con clorhexidina.",
    ])
    lineas.append("")

    lineas.append("Signos normales:")
    lineas.extend([
        "- Somnolencia.",
        "- Menor actividad.",
        "- Ligera inflamación.",
    ])
    lineas.append("")

    lineas.append("Signos de alerta:")
    lineas.extend([
        "- Sangrado.",
        "- Supuración.",
        "- Herida abierta.",
        "- Decaimiento extremo.",
        "- Fiebre.",
        "- Falta de apetito prolongada.",
    ])

    if (pet.get("sexo") or "").lower() == "macho":
        lineas.append("")
        lineas.append("Observación adicional:")
        lineas.append("- Los machos pueden seguir siendo fértiles aproximadamente 1 mes tras la cirugía.")

    if edad is not None and edad > 6:
        lineas.append("")
        lineas.append("Seguimiento especial:")
        lineas.append("- Al tratarse de un animal de más de 6 años, conviene una vigilancia más estrecha.")

    return "\n".join(lineas).strip()


def respuesta_preoperatorio(pet: dict) -> str:
    return construir_respuesta_preoperatorio_filtrada(pet)


def respuesta_postoperatorio(pet: dict) -> str:
    return construir_respuesta_postoperatorio_filtrada(pet)


def respuesta_urgencia() -> str:
    return (
        "Esta clínica no atiende urgencias. En caso de emergencia, acuda inmediatamente "
        "a un centro veterinario de urgencias."
    )


def refrescar_mascotas_cliente(state: dict):
    if state["client"] and state["client"].get("id"):
        state["pets"] = listar_mascotas_cliente(state["client"]["id"])


def extraer_nombres_mascotas_cliente(state: dict) -> list[str]:
    return [m["nombre"].capitalize() for m in state.get("pets", [])]


def construir_menu_mascotas(state: dict) -> str:
    nombres = extraer_nombres_mascotas_cliente(state)
    lineas = [
        "Tienes registradas estas mascotas. Indícame sobre qué mascota quieres gestionar la intervención, o si es una nueva mascota escribe su nombre:",
    ]
    for idx, nombre in enumerate(nombres, start=1):
        lineas.append(f"{idx}- {nombre}")
    lineas.append(f"{len(nombres) + 1}- Nueva mascota")
    return "\n".join(lineas)


def nombre_mascota_bonito(state: dict) -> str:
    if state.get("active_pet") and state["active_pet"].get("nombre"):
        return state["active_pet"]["nombre"].capitalize()
    return "Tu mascota"


def construir_menu_mascota(state: dict) -> str:
    nombre = nombre_mascota_bonito(state)
    fecha = None

    if state.get("active_pet") and state["active_pet"].get("id"):
        fecha = obtener_cita_confirmada_por_mascota(state["active_pet"]["id"])

    if fecha:
        cabecera = f"He cargado a {nombre}. Actualmente tiene una cita confirmada para el {formatear_fecha_es(fecha)}."
        opcion_5 = f"5- Solicitar cambio de cita de {nombre}"
    else:
        cabecera = f"He cargado a {nombre}. No tiene ninguna cita confirmada."
        opcion_5 = f"5- Reservar una nueva intervención para {nombre}"

    return (
        f"{cabecera}\n\n"
        f"Indícame qué quieres hacer:\n"
        f"1- Consultar cita de {nombre}\n"
        f"2- Obtener información del preoperatorio\n"
        f"3- Obtener información del postoperatorio\n"
        f"4- Información en caso de urgencia\n"
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


def construir_mensaje_otra_gestion(state: dict) -> str:
    nombre = nombre_mascota_bonito(state)
    return (
        f"Espero que la gestión sobre {nombre} haya quedado aclarada. "
        f"¿Deseas realizar otra consulta o gestión sobre alguna de tus mascotas? Responde solo sí o no."
    )


# =========================
# MENSAJES
# =========================

def mensaje_inicio() -> str:
    return (
        "No le he entendido, soy el asistente de la clínica veterinaria especializado en esterilización.\n"
        "¿Ya eres cliente de la clínica?\n"
        "1- Sí\n"
        "2- No"
    )


def mensaje_error_si_no() -> str:
    return "No le he entendido, le ruego indique Sí o No."


def mensaje_dni() -> str:
    return "Por favor, indícame tu DNI."


def mensaje_dni_nuevo() -> str:
    return "Para darte de alta como nuevo cliente, por favor, indícame tu DNI."


# =========================
# VALIDADORES
# =========================

def validar_opcion_cliente(texto: str) -> Optional[bool]:
    t = normalizar_texto(texto)
    if t in {"1", "si", "sí"}:
        return True
    if t in {"2", "no"}:
        return False
    return None


def validar_dni(texto: str) -> Optional[str]:
    t = texto.strip().upper()
    if re.fullmatch(r"\d{8}[A-Z]", t):
        return t
    return None


def validar_nombre_persona(texto: str) -> Optional[str]:
    t = texto.strip()
    if not (2 <= len(t.split()) <= 4):
        return None
    patron = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]+(?: [A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]+){1,3}$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_telefono(texto: str) -> Optional[str]:
    t = re.sub(r"\s+", "", texto.strip())
    if re.fullmatch(r"\d{9}", t):
        return t
    return None


def validar_email(texto: str) -> Optional[str]:
    t = texto.strip()
    patron = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_direccion(texto: str) -> Optional[str]:
    t = texto.strip()
    if len(t) >= 5:
        return t
    return None


def validar_menu_numerico(texto: str, min_op: int, max_op: int) -> Optional[int]:
    if not texto:
        return None
    t = texto.strip()
    if not t.isdigit():
        return None
    op = int(t)
    if min_op <= op <= max_op:
        return op
    return None


def validar_nombre_mascota(texto: str) -> Optional[str]:
    t = texto.strip()
    patron = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]{2,20}$"
    if re.fullmatch(patron, t):
        return t
    return None


def validar_especie(texto: str) -> Optional[str]:
    t = normalizar_texto(texto)
    if t in {"perro", "gato"}:
        return t
    return None


def validar_sexo(texto: str) -> Optional[str]:
    t = normalizar_texto(texto)
    if t in {"macho", "hembra"}:
        return t
    return None


def validar_entero_positivo(texto: str, min_val=0, max_val=30) -> Optional[int]:
    t = normalizar_texto(texto)
    if t.isdigit():
        n = int(t)
        if min_val <= n <= max_val:
            return n
    return None


def validar_decimal_positivo(texto: str, min_val=0.1, max_val=100.0) -> Optional[float]:
    t = normalizar_texto(texto).replace(",", ".")
    try:
        n = float(t)
        if min_val <= n <= max_val:
            return n
    except ValueError:
        pass
    return None


def validar_opcion_accion_mascota(texto: str) -> Optional[int]:
    return validar_menu_numerico(texto, 1, 5)


def validar_fecha(texto: str) -> Optional[str]:
    t = normalizar_texto(texto)
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }

    for sep in ["/", "-"]:
        if sep in t:
            partes = [p.strip() for p in t.split(sep)]
            try:
                if len(partes) == 2:
                    dia = int(partes[0])
                    mes = int(partes[1])
                    anio = datetime.now().year
                    if 1 <= dia <= 31 and 1 <= mes <= 12:
                        return f"{anio:04d}-{mes:02d}-{dia:02d}"
                if len(partes) == 3:
                    dia = int(partes[0])
                    mes = int(partes[1])
                    anio = int(partes[2])
                    if anio < 100:
                        anio = 2000 + anio
                    if 1 <= dia <= 31 and 1 <= mes <= 12:
                        return f"{anio:04d}-{mes:02d}-{dia:02d}"
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
        return f"{anio:04d}-{mes:02d}-{dia:02d}"

    return None


# =========================
# ENDPOINTS
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE


@app.get("/fechas_disponibles")
def fechas_disponibles(tipo: str = "perro_macho"):
    return {"fechas": get_fechas_disponibles_reales(tipo)}


@app.post("/ask_bot")
def ask_bot(data: ChatRequest):
    try:
        session_id = data.session_id.strip() if data.session_id else "default"
        user_message = data.message.strip()

        if not user_message:
            return {"response": "Por favor, escribe un mensaje.", "session_id": session_id}

        history = get_or_create_history(session_id)
        state = get_or_create_state(session_id)
        texto = normalizar_texto(user_message)

        if texto in {"reinicia", "reiniciar", "reset", "empezar de nuevo", "nuevo proceso"}:
            reset_state(session_id)
            state = get_or_create_state(session_id)
            state["phase"] = "client_status"
            conversation_store[session_id] = []
            respuesta = mensaje_inicio()
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "start":
            respuesta = mensaje_inicio()
            state["phase"] = "client_status"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "post_pet_resolution":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                refrescar_mascotas_cliente(state)
                state["phase"] = "pet_selection"
                respuesta = (
                    construir_menu_mascotas(state)
                    if state["pets"]
                    else "No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota."
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            respuesta = "De acuerdo. Gracias por contactar con la clínica veterinaria. Hasta pronto."
            guardar_respuesta(history, user_message, respuesta)
            reset_state(session_id)
            conversation_store[session_id] = []
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "client_status":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                state["phase"] = "existing_client_dni"
                respuesta = mensaje_dni()
            else:
                state["phase"] = "new_client_dni"
                respuesta = mensaje_dni_nuevo()

            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "existing_client_dni":
            dni = validar_dni(user_message)
            if dni is None:
                respuesta = "No le he entendido, indique un DNI válido."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cliente = buscar_cliente_por_dni(dni)
            if not cliente:
                state["pending_dni_not_found"] = dni
                state["phase"] = "confirm_new_client_from_missing_dni"
                respuesta = (
                    "No he encontrado ningún cliente con ese DNI en la base de datos de la clínica.\n"
                    "Compruebe si el número de DNI es correcto.\n\n"
                    "Si el DNI es correcto y desea continuar con la gestión, ¿nos autoriza a darlo de alta como nuevo cliente en la base de datos de la clínica?\n"
                    "1- Sí\n"
                    "2- No"
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client"] = cliente
            refrescar_mascotas_cliente(state)
            state["phase"] = "pet_selection"

            if state["pets"]:
                respuesta = (
                    f"He encontrado tus datos como cliente registrado, {cliente['nombre']}. "
                    f"{construir_menu_mascotas(state)}"
                )
            else:
                respuesta = (
                    f"He encontrado tus datos como cliente registrado, {cliente['nombre']}. "
                    f"No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota."
                )

            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "confirm_new_client_from_missing_dni":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = "No le he entendido. Responda 1- Sí o 2- No."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if valor:
                state["client_new"]["dni"] = state["pending_dni_not_found"]
                state["pending_dni_not_found"] = None
                state["phase"] = "new_client_nombre"
                respuesta = "De acuerdo. Para continuar con el alta como nuevo cliente, indíqueme su nombre y apellidos."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["pending_dni_not_found"] = None
            state["phase"] = "client_status"
            respuesta = (
                "De acuerdo. Si lo prefiere, puede verificar de nuevo el DNI o contactar directamente con la clínica para revisar sus datos."
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_dni":
            dni = validar_dni(user_message)
            if dni is None:
                respuesta = "No le he entendido, indique su DNI."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cliente_existente = buscar_cliente_por_dni(dni)
            if cliente_existente:
                state["client"] = cliente_existente
                refrescar_mascotas_cliente(state)
                state["phase"] = "pet_selection"
                if state["pets"]:
                    respuesta = (
                        f"Ya existe un cliente registrado con ese DNI: {cliente_existente['nombre']}. "
                        f"{construir_menu_mascotas(state)}"
                    )
                else:
                    respuesta = (
                        f"Ya existe un cliente registrado con ese DNI: {cliente_existente['nombre']}. "
                        f"No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota."
                    )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["dni"] = dni
            state["phase"] = "new_client_nombre"
            respuesta = "Dígame su nombre y apellidos."
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_nombre":
            nombre = validar_nombre_persona(user_message)
            if nombre is None:
                respuesta = "No le he entendido, indique su nombre y apellidos."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["nombre"] = nombre
            state["phase"] = "new_client_telefono"
            respuesta = "Indícame tu número de teléfono."
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_telefono":
            telefono = validar_telefono(user_message)
            if telefono is None:
                respuesta = "No le he entendido, indique su número de teléfono."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["telefono"] = telefono
            state["phase"] = "new_client_email"
            respuesta = "Indícame tu email."
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_email":
            email = validar_email(user_message)
            if email is None:
                respuesta = "No le he entendido, indique un email válido."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["client_new"]["email"] = email
            state["phase"] = "new_client_direccion"
            respuesta = "Indícame tu dirección."
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_client_direccion":
            direccion = validar_direccion(user_message)
            if direccion is None:
                respuesta = "No le he entendido, indique su dirección."
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
                respuesta = f"No se ha podido completar el registro: {resultado} Indique de nuevo su DNI."
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
            state["phase"] = "pet_selection"

            respuesta = (
                f"Gracias, {state['client']['nombre']}. Has quedado registrado como cliente. "
                f"Indícame el nombre de tu mascota."
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
                    respuesta = f"Gracias. ¿Qué especie es {nombre_mascota_bonito(state)}, perro o gato?"
                    guardar_respuesta(history, user_message, respuesta)
                    return {"response": respuesta, "session_id": session_id}

                respuesta = "No tengo mascotas registradas para este cliente. Indícame el nombre de tu mascota."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            op = validar_menu_numerico(user_message, 1, total + 1)
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
                    respuesta = "Indique el nombre de su nueva mascota para proceder a su registro:"
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
                respuesta = f"Gracias. ¿Qué especie es {nombre_mascota_bonito(state)}, perro o gato?"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            respuesta = "No le he entendido. " + construir_menu_mascotas(state)
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_name":
            nombre_mascota = validar_nombre_mascota(user_message)
            if nombre_mascota is None:
                respuesta = "No le he entendido, indique el nombre de su nueva mascota."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            iniciar_alta_mascota(state, nombre_mascota)
            state["phase"] = "new_pet_especie"
            respuesta = f"Gracias. ¿Qué especie es {nombre_mascota_bonito(state)}, perro o gato?"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "existing_pet_action":
            op = validar_opcion_accion_mascota(user_message)

            if op is None:
                respuesta = (
                    "No le he entendido. Por favor, seleccione una opción válida:\n\n"
                    + construir_menu_mascota(state)
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]

            if op == 1:
                fecha = obtener_cita_confirmada_por_mascota(pet["id"])
                if fecha:
                    respuesta = f"{pet['nombre'].capitalize()} tiene una cita confirmada para el {formatear_fecha_es(fecha)}."
                else:
                    respuesta = f"No consta ninguna cita confirmada para {pet['nombre'].capitalize()}."
                state["phase"] = "post_pet_resolution"
                respuesta_final = f"{respuesta}\n\n{construir_mensaje_otra_gestion(state)}"
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 2:
                respuesta = respuesta_preoperatorio(pet)
                state["phase"] = "post_pet_resolution"
                respuesta_final = f"{respuesta}\n\n{construir_mensaje_otra_gestion(state)}"
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 3:
                respuesta = respuesta_postoperatorio(pet)
                state["phase"] = "post_pet_resolution"
                respuesta_final = f"{respuesta}\n\n{construir_mensaje_otra_gestion(state)}"
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 4:
                respuesta = respuesta_urgencia()
                state["phase"] = "post_pet_resolution"
                respuesta_final = f"{respuesta}\n\n{construir_mensaje_otra_gestion(state)}"
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            if op == 5:
                fecha_actual = obtener_cita_confirmada_por_mascota(pet["id"])
                tipo_cirugia = obtener_tipo_cirugia_desde_pet(pet)

                if fecha_actual:
                    fecha_actual_dt = datetime.strptime(fecha_actual, "%Y-%m-%d").date()
                    hoy = datetime.now().date()

                    if fecha_actual_dt - hoy < timedelta(days=1):
                        respuesta = (
                            f"{pet['nombre'].capitalize()} ya tiene una cita confirmada para el {formatear_fecha_es(fecha_actual)}.\n\n"
                            "No es posible solicitar el cambio de cita con menos de 24 horas de antelación."
                        )
                        state["phase"] = "post_pet_resolution"
                        respuesta_final = f"{respuesta}\n\n{construir_mensaje_otra_gestion(state)}"
                        guardar_respuesta(history, user_message, respuesta_final)
                        return {"response": respuesta_final, "session_id": session_id}

                    state["phase"] = "waiting_for_reschedule_date"
                    respuesta = (
                        f"{pet['nombre'].capitalize()} ya tiene una cita confirmada para el {formatear_fecha_es(fecha_actual)}.\n\n"
                        f"Voy a mostrarte nuevas fechas disponibles para solicitar el cambio de cita.\n\n"
                        f"{construir_texto_fechas(tipo_cirugia, state)}"
                    )
                else:
                    state["phase"] = "waiting_for_date"
                    respuesta = (
                        f"De acuerdo. Voy a gestionar la intervención para {pet['nombre'].capitalize()}.\n\n"
                        f"{construir_texto_fechas(tipo_cirugia, state)}"
                    )

                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_especie":
            especie = validar_especie(user_message)
            if especie is None:
                respuesta = f"No le he entendido. Indique si {nombre_mascota_bonito(state)} es perro o gato."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["especie"] = especie
            state["phase"] = "new_pet_sexo"
            respuesta = f"Perfecto. ¿{nombre_mascota_bonito(state)} es macho o hembra?"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_sexo":
            sexo = validar_sexo(user_message)
            if sexo is None:
                respuesta = f"No le he entendido. Indique si {nombre_mascota_bonito(state)} es macho o hembra."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["sexo"] = sexo
            state["phase"] = "new_pet_edad"
            respuesta = f"¿Cuántos años tiene {nombre_mascota_bonito(state)}?"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_edad":
            edad = validar_entero_positivo(user_message, 0, 30)
            if edad is None:
                respuesta = f"No le he entendido. Indique la edad en número de {nombre_mascota_bonito(state)}."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["edad"] = edad

            if state["active_pet"]["especie"] == "perro" and state["active_pet"]["sexo"] == "hembra":
                state["phase"] = "new_pet_peso"
                respuesta = f"¿{nombre_mascota_bonito(state)} pesa aproximadamente?"
            else:
                state["phase"] = "clinical_microchip"
                respuesta = f"¿{nombre_mascota_bonito(state)} tiene microchip?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_peso":
            peso = validar_decimal_positivo(user_message, 0.1, 100.0)
            if peso is None:
                respuesta = f"No le he entendido. Indique el peso en número de {nombre_mascota_bonito(state)}."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["peso"] = peso
            state["phase"] = "new_pet_celo"
            respuesta = f"¿{nombre_mascota_bonito(state)} está actualmente en celo?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "new_pet_celo":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            if valor:
                respuesta = (
                    f"{nombre_mascota_bonito(state)} no puede operarse en este momento. "
                    f"Debe esperar al menos 2 meses tras finalizar el celo."
                )
                state["phase"] = "post_pet_resolution"
                respuesta_final = respuesta + "\n\n" + construir_mensaje_otra_gestion(state)
                guardar_respuesta(history, user_message, respuesta_final)
                return {"response": respuesta_final, "session_id": session_id}

            state["phase"] = "clinical_microchip"
            respuesta = f"¿{nombre_mascota_bonito(state)} tiene microchip?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_microchip":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["microchip"] = valor
            state["phase"] = "clinical_vacuna"

            if not valor:
                respuesta = (
                    "El microchip es obligatorio. Puede implantarse el mismo día de la cirugía con un coste adicional.\n\n"
                    "¿Tiene la vacuna antirrábica al día?\n1- Sí\n2- No"
                )
            else:
                respuesta = "¿Tiene la vacuna antirrábica al día?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_vacuna":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["active_pet"]["vacuna_rabia"] = valor

            if not valor:
                respuesta = (
                    "La vacuna antirrábica es obligatoria. Sin la vacuna antirrábica al día no se puede realizar la esterilización.\n\n"
                    "Quedo a la espera de que indiques que la vacuna ya está regularizada."
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

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

            state["phase"] = "clinical_vacunado_desparasitado"
            respuesta = f"¿Está {nombre_mascota_bonito(state)} vacunada y desparasitada?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_vacunado_desparasitado":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["vacunado_desparasitado"] = valor
            state["phase"] = "clinical_enfermedad"
            respuesta = f"¿{nombre_mascota_bonito(state)} tiene alguna enfermedad conocida?\n1- Sí\n2- No"
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_enfermedad":
            valor = validar_opcion_cliente(user_message)
            if valor is None:
                respuesta = mensaje_error_si_no()
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            state["active_pet"]["enfermedad"] = valor

            if valor:
                state["phase"] = "clinical_detalle_enfermedad"
                respuesta = f"¿Cuál es la enfermedad conocida de {nombre_mascota_bonito(state)}?"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            edad = state["active_pet"]["edad"] or 0
            analitica = (
                f"Dado que {nombre_mascota_bonito(state)} tiene {edad} años, no es necesaria una analítica preoperatoria."
                if edad <= 6
                else f"Como {nombre_mascota_bonito(state)} tiene más de 6 años, es obligatoria una analítica preoperatoria."
            )
            tipo_cirugia = obtener_tipo_cirugia_desde_pet(state["active_pet"])
            state["phase"] = "waiting_for_date"

            preop_texto = respuesta_preoperatorio(state["active_pet"])
            respuesta = (
                f"{analitica}\n\n"
                f"Ahora, te informaré sobre las instrucciones preoperatorias:\n\n"
                f"{preop_texto}\n\n"
                f"Ahora voy a indicarte la disponibilidad para la cirugía.\n\n"
                f"{construir_texto_fechas(tipo_cirugia, state)}"
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "clinical_detalle_enfermedad":
            detalle = user_message.strip()
            if len(detalle) < 2:
                respuesta = f"No le he entendido. Indique la enfermedad conocida de {nombre_mascota_bonito(state)}."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}
            state["active_pet"]["detalle_enfermedad"] = detalle
            respuesta = "Debes comunicar esa enfermedad a la clínica antes de confirmar la cirugía, ya que puede estar contraindicada según el caso."
            state["phase"] = "post_pet_resolution"
            respuesta_final = respuesta + "\n\n" + construir_mensaje_otra_gestion(state)
            guardar_respuesta(history, user_message, respuesta_final)
            return {"response": respuesta_final, "session_id": session_id}

        if state["phase"] == "waiting_for_reschedule_date":
            fecha_detectada = validar_fecha(user_message)
            if fecha_detectada is None:
                respuesta = "Por favor, indícame una fecha válida para el cambio de cita."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if state["offered_dates"] and fecha_detectada not in state["offered_dates"]:
                fechas_legibles = [formatear_fecha_es(f) for f in state["offered_dates"]]
                respuesta = (
                    "Debes elegir una de las fechas que te he ofrecido previamente para el cambio de cita.\n"
                    "Fechas válidas:\n- " + "\n- ".join(fechas_legibles)
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]
            tipo_cirugia = obtener_tipo_cirugia_desde_pet(pet)

            disponible, mensaje = verificar_disponibilidad(fecha_detectada, tipo_cirugia)
            if not disponible:
                respuesta = f"No hay disponibilidad para ese día. {mensaje}"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            cancelada = cancelar_cita_confirmada_por_mascota(pet["id"])
            if not cancelada:
                respuesta = "No se ha podido tramitar el cambio de cita en este momento."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            exito, mensaje = reservar_cita(
                fecha_detectada,
                state["client"]["id"],
                pet["id"],
                tipo_cirugia,
            )
            if not exito:
                respuesta = f"No se ha podido completar el cambio de cita. {mensaje}"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_texto = formatear_fecha_es(fecha_detectada)
            if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
                entrega = "entre 09:00 y 10:30"
                recogida = "a las 12:00"
            else:
                entrega = "entre 08:00 y 09:00"
                recogida = "a las 15:00"

            state["phase"] = "post_pet_resolution"
            state["offered_dates"] = []
            refrescar_mascotas_cliente(state)

            respuesta = (
                f"El cambio de cita para la esterilización de {pet['nombre'].capitalize()} ha quedado confirmado para el {fecha_texto}.\n\n"
                f"- Entrega: {entrega}.\n"
                f"- Recogida aproximada: {recogida}.\n"
                f"- Recuerda traer el consentimiento informado y la cartilla o pasaporte de {pet['nombre'].capitalize()}.\n\n"
                f"Quedamos a tu disposición el día de la intervención.\n\n"
                f"{construir_mensaje_otra_gestion(state)}"
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        if state["phase"] == "waiting_for_date":
            fecha_detectada = validar_fecha(user_message)
            if fecha_detectada is None:
                respuesta = "Por favor, indícame una fecha válida para la cirugía."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if state["offered_dates"] and fecha_detectada not in state["offered_dates"]:
                fechas_legibles = [formatear_fecha_es(f) for f in state["offered_dates"]]
                respuesta = (
                    "Debes elegir una de las fechas que te he ofrecido previamente.\n"
                    "Fechas válidas:\n- " + "\n- ".join(fechas_legibles)
                )
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_dt = datetime.strptime(fecha_detectada, "%Y-%m-%d")
            ahora = datetime.now()

            if fecha_dt.date() < ahora.date():
                respuesta = "No hay disponibilidad para ese día. No se pueden reservar citas para días pasados."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            if fecha_dt.date() == ahora.date() and ahora.hour >= 17:
                respuesta = "No hay disponibilidad para ese día. No es posible reservar cita para hoy porque el horario de reserva ya no está disponible."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            pet = state["active_pet"]
            tipo_cirugia = obtener_tipo_cirugia_desde_pet(pet)

            if existe_cita_mascota(fecha_detectada, pet["id"]):
                respuesta = f"Ya existe una cita confirmada para {pet['nombre'].capitalize()} en esa fecha. Por favor, elige otro día."
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            disponible, mensaje = verificar_disponibilidad(fecha_detectada, tipo_cirugia)
            if not disponible:
                respuesta = f"No hay disponibilidad para ese día. {mensaje}"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            exito, mensaje = reservar_cita(
                fecha_detectada,
                state["client"]["id"],
                pet["id"],
                tipo_cirugia,
            )
            if not exito:
                respuesta = f"No se ha podido reservar la cita. {mensaje}"
                guardar_respuesta(history, user_message, respuesta)
                return {"response": respuesta, "session_id": session_id}

            fecha_texto = formatear_fecha_es(fecha_detectada)
            if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
                entrega = "entre 09:00 y 10:30"
                recogida = "a las 12:00"
            else:
                entrega = "entre 08:00 y 09:00"
                recogida = "a las 15:00"

            state["phase"] = "post_pet_resolution"
            state["offered_dates"] = []
            refrescar_mascotas_cliente(state)

            respuesta = (
                f"La cita para la esterilización de {pet['nombre'].capitalize()} queda confirmada para el {fecha_texto}.\n\n"
                f"- Entrega: {entrega}.\n"
                f"- Recogida aproximada: {recogida}.\n"
                f"- Recuerda traer el consentimiento informado y la cartilla o pasaporte de {pet['nombre'].capitalize()}.\n\n"
                f"Quedamos a tu disposición el día de la intervención.\n\n"
                f"{construir_mensaje_otra_gestion(state)}"
            )
            guardar_respuesta(history, user_message, respuesta)
            return {"response": respuesta, "session_id": session_id}

        respuesta = "No le he entendido. ¿Puede repetir la opción?"
        guardar_respuesta(history, user_message, respuesta)
        return {"response": respuesta, "session_id": session_id}

    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "session_id": data.session_id if data.session_id else "default",
        }