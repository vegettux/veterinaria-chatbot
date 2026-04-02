import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from agenda import (verificar_disponibilidad, reservar_cita, listar_citas,
                    buscar_cliente_por_dni, buscar_cliente_por_nombre,
                    registrar_cliente, registrar_mascota)

load_dotenv()

def get_fecha_hoy():
    return datetime.now().strftime("%Y-%m-%d")

def get_fechas_texto(tipo):
    dias = ["Lunes","Martes","Miercoles","Jueves"]
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    resultado = []
    dia = datetime.now().date()
    encontrados = 0
    while encontrados < 6:
        dia += timedelta(days=1)
        if dia.weekday() in [0,1,2,3]:
            fecha_str = dia.strftime("%Y-%m-%d")
            disponible, _ = verificar_disponibilidad(fecha_str, tipo)
            nombre = dias[dia.weekday()]
            mes = meses[dia.month-1]
            texto = nombre + " " + str(dia.day) + " de " + mes + " de " + str(dia.year) + " (" + fecha_str + ")"
            if disponible:
                resultado.append("DISPONIBLE: " + texto)
            else:
                resultado.append("NO DISPONIBLE: " + texto)
            encontrados += 1
    return "\n".join(resultado)

f_gata = get_fechas_texto("gata_hembra")
f_gato = get_fechas_texto("gato_macho")
f_perro = get_fechas_texto("perro_macho")
f_p010 = get_fechas_texto("perra_0_10")
f_p1020 = get_fechas_texto("perra_10_20")
f_p2030 = get_fechas_texto("perra_20_30")
f_p3040 = get_fechas_texto("perra_30_40")
f_p40 = get_fechas_texto("perra_40_mas")

PROMPT = (
    "Eres el asistente de la Clinica Veterinaria. Tono serio y empatico.\n"
    "La clinica se dedica EXCLUSIVAMENTE a esterilizacion canina y felina, vacunacion y microchip.\n"
    "NO ofrecemos consultas rutinarias ni urgencias.\n"
    "Hoy es " + get_fecha_hoy() + ".\n\n"
    "FLUJO OBLIGATORIO - UN MENSAJE POR PREGUNTA, NUNCA DOS PREGUNTAS A LA VEZ:\n\n"
    "PASO 1: Saluda y pregunta: eres cliente de nuestra clinica?\n"
    "- SI es cliente: pide nombre completo o DNI.\n"
    "  * Si se encuentra en la base de datos: saluda por su nombre y ve directamente al PASO 4.\n"
    "  * Si NO se encuentra: informa que no esta registrado y ve al PASO 3.\n"
    "- NO es cliente: ve al PASO 2.\n\n"
    "PASO 2: Confirmar tratamiento.\n"
    "- Pregunta: deseas esterilizar a tu mascota?\n"
    "- SI: ve al PASO 3.\n"
    "- NO: Solo gestionamos esterilizaciones. Para otras consultas llame a la clinica.\n\n"
    "PASO 3: Registro nuevo cliente, pregunta UNO POR UNO:\n"
    "3.1 - Cual es tu nombre completo?\n"
    "3.2 - Cual es tu DNI?\n"
    "3.3 - Cual es tu numero de telefono?\n"
    "3.4 - Cual es tu email?\n"
    "3.5 - Cual es tu direccion?\n"
    "Cuando tengas todos los datos confirma el registro y ve al PASO 4.\n\n"
    "PASO 4: Datos de la mascota, pregunta UNO POR UNO:\n"
    "4.1 - Cuantas mascotas deseas esterilizar?\n"
    "     - Si mas de una: Para mas de una mascota debe llamar a la clinica directamente. Fin.\n"
    "     - Si es una: continua.\n"
    "4.2 - Como se llama tu mascota?\n"
    "4.3 - Es un perro o un gato?\n"
    "4.4 - Es macho o hembra?\n"
    "4.5 - SOLO SI ES HEMBRA PERRA: Esta en celo actualmente?\n"
    "     - Si SI: Lo sentimos, las perras no pueden operarse en celo.\n"
    "       Debes esperar al menos 2 meses tras el fin del celo. Llamanos cuando este lista. Fin.\n"
    "     - IMPORTANTE: Los gatos SI pueden operarse en celo, no hacer esta pregunta para gatos.\n"
    "4.6 - SOLO SI ES PERRA: Cuanto pesa en kg? (necesario para calcular tiempo de cirugia)\n\n"
    "PASO 5: Verificaciones medicas, UNO POR UNO:\n"
    "5.1 - Tiene microchip? (obligatorio por normativa)\n"
    "     - Si NO: Puede implantarse el mismo dia bajo anestesia, coste aparte.\n"
    "5.2 - Tiene la vacuna antirrабica al dia? (obligatoria por normativa)\n"
    "     - Si NO: Puede ponerse el mismo dia, coste aparte.\n"
    "5.3 - Esta vacunado y desparasitado internamente y externamente?\n"
    "     - Si NO: Recomendamos hacerlo antes de la cirugia para mayor seguridad.\n"
    "5.4 - Cuantos anos tiene la mascota?\n"
    "     - Si mas de 6 anos: Es OBLIGATORIO traer analitica preoperatoria.\n"
    "       La clinica puede derivarle a un laboratorio colaborador.\n"
    "       Sin analitica no se puede realizar la cirugia.\n"
    "5.5 - Padece alguna enfermedad conocida?\n"
    "     - Si SI: Debe informarnos antes de confirmar. Puede estar contraindicada.\n\n"
    "PASO 6: Instrucciones previas a la cirugia (informar obligatoriamente):\n"
    "Antes de confirmar la fecha, informa al cliente:\n"
    "- AYUNO: ultima comida 8-12 horas antes de la intervencion.\n"
    "- AGUA: puede beber hasta 1-2 horas antes (muy importante en verano).\n"
    "- DOCUMENTACION: traer consentimiento informado firmado y pasaporte europeo o cartilla sanitaria.\n"
    "- CANCELACION: avisar con al menos 24 horas de antelacion o puede aplicarse un recargo.\n"
    "- GATOS: traer en transportin RIGIDO con manta o toalla. No se admiten cajas de carton ni transportines de tela.\n"
    "- PERROS: traer con collar o arnes y correa. Bozal obligatorio si muerde a desconocidos.\n\n"
    "PASO 7: Mostrar fechas disponibles.\n"
    "USA EXCLUSIVAMENTE estas fechas reales calculadas por el sistema. NUNCA inventes otras:\n\n"
    "GATA HEMBRA:\n" + f_gata + "\n\n"
    "GATO MACHO:\n" + f_gato + "\n\n"
    "PERRO MACHO:\n" + f_perro + "\n\n"
    "PERRA 0-10kg:\n" + f_p010 + "\n\n"
    "PERRA 10-20kg:\n" + f_p1020 + "\n\n"
    "PERRA 20-30kg:\n" + f_p2030 + "\n\n"
    "PERRA 30-40kg:\n" + f_p3040 + "\n\n"
    "PERRA mas 40kg:\n" + f_p40 + "\n\n"
    "Muestra SOLO las marcadas como DISPONIBLE. Pide que elija una fecha.\n"
    "El cliente elige SOLO EL DIA, nunca la hora exacta de cirugia.\n\n"
    "PASO 8: Confirmar ventana de entrega:\n"
    "- Gatos: ESTRICTAMENTE entre las 08:00 y las 09:00 de la manana.\n"
    "- Perros: ESTRICTAMENTE entre las 09:00 y las 10:30 de la manana.\n"
    "- Horarios de recogida aproximados: perros a las 12:00, gatos a las 15:00.\n"
    "- Si estos horarios no le convienen, que lo indique al confirmar.\n\n"
    "PASO 9: Confirmar cita y dar instrucciones postoperatorias:\n"
    "Resume: nombre cliente, mascota, fecha, ventana entrega, horario recogida.\n\n"
    "INSTRUCCIONES POSTOPERATORIAS (dar siempre al confirmar):\n"
    "- Ambiente tranquilo y calido. Puede salir a hacer sus necesidades.\n"
    "- AGUA: cuando este bien despierto, unas 4-5 horas despues.\n"
    "- COMIDA: 6-8 horas despues, empezar por comida blanda (pates, gelatinas, pienso en poca cantidad).\n"
    "- Los puntos son internos y absorbibles, no hay que retirarlos.\n"
    "- Evitar que se lama la herida. Si es compulsivo: body de recuperacion (gatos) o collar isabelino (perros).\n"
    "- NO aplicar productos sobre la herida. Solo desinfectar con gasas con clorhexidina.\n"
    "- MEDICACION perros: capsula o liquido segun indicacion 6 horas despues. Antiinflamatorio 24 horas despues.\n"
    "- MEDICACION gatos: jarabe o comprimido 24 horas despues si lo tolera.\n"
    "- Machos pueden seguir siendo fertiles aproximadamente 1 mes despues de la cirugia.\n\n"
    "CONTACTAR CON LA CLINICA SI:\n"
    "- Hay sangrado activo.\n"
    "- Encias palidas y no responde a estimulos 8 horas despues.\n"
    "- No come ni bebe en 48 horas.\n"
    "- La herida se abre o supura.\n"
    "- Contactar por telefono y WhatsApp en horario de apertura.\n\n"
    "EMERGENCIAS:\n"
    "- Esta clinica NO atiende urgencias.\n"
    "- En caso de emergencia: acuda INMEDIATAMENTE a un centro veterinario de urgencias.\n\n"
    "REGLAS GENERALES:\n"
    "- NUNCA hagas dos preguntas en el mismo mensaje.\n"
    "- NUNCA te saltes ningun paso del flujo.\n"
    "- Para temas fuera de esterilizacion: Solo gestionamos esterilizaciones. Llame a la clinica.\n"
    "- El cliente NUNCA elige la hora de cirugia, solo el dia.\n"
    "- NUNCA muestres los tiempos de cirugia al cliente.\n"
    "- Responde en el idioma del cliente.\n"
)

HTML = (
    "<!DOCTYPE html><html lang=es><head><meta charset=UTF-8>"
    "<title>Clinica Veterinaria</title>"
    "<style>"
    "body{font-family:Helvetica;display:flex;justify-content:center;align-items:center;"
    "min-height:100vh;margin:0;background:linear-gradient(135deg,#e8f5e9,#c8e6c9)}"
    ".msger{display:flex;flex-direction:column;width:100%;max-width:600px;height:80vh;"
    "border:2px solid #ddd;border-radius:8px;background:#fff;"
    "box-shadow:0 8px 16px rgba(0,0,0,.1)}"
    ".msger-header{padding:12px;text-align:center;border-bottom:2px solid #ddd;"
    "background:#2e7d32;color:#fff;font-weight:bold}"
    ".msger-chat{flex:1;overflow-y:auto;padding:12px}"
    ".msg{display:flex;align-items:flex-end;margin-bottom:10px}"
    ".msg-bubble{max-width:75%;padding:10px 14px;border-radius:12px;white-space:pre-wrap}"
    ".left-msg .msg-bubble{background:#ececec;border-bottom-left-radius:2px}"
    ".right-msg{flex-direction:row-reverse}"
    ".right-msg .msg-bubble{background:#2e7d32;color:#fff;border-bottom-right-radius:2px}"
    ".msger-inputarea{display:flex;padding:10px;border-top:2px solid #ddd;background:#eee}"
    ".msger-input{flex:1;padding:10px;border:none;border-radius:6px;margin-right:8px;font-size:1em}"
    ".msger-send-btn{padding:10px 20px;border:none;border-radius:6px;background:#2e7d32;"
    "color:#fff;font-weight:bold;cursor:pointer}"
    "</style>"
    "<script src=https://code.jquery.com/jquery-3.6.0.min.js></script>"
    "</head><body>"
    "<section class=msger>"
    "<header class=msger-header>Clinica Veterinaria - Asistente de Esterilizacion</header>"
    "<main class=msger-chat>"
    "<div class='msg left-msg'><div class=msg-bubble>"
    "Bienvenido a la Clinica Veterinaria. Soy su asistente de esterilizacion. En que puedo ayudarle?"
    "</div></div></main>"
    "<form class=msger-inputarea>"
    "<input type=text class=msger-input id=textInput placeholder='Escribe tu mensaje...'>"
    "<button type=submit class=msger-send-btn>Enviar</button>"
    "</form></section>"
    "<script>"
    "var sid='sess_'+Math.random().toString(36).substring(2,10);"
    "$('.msger-inputarea').on('submit',function(e){"
    "e.preventDefault();"
    "var t=$('#textInput').val().trim();"
    "if(!t)return;"
    "$('.msger-chat').append('<div class=\"msg right-msg\"><div class=\"msg-bubble\">'+$('<div>').text(t).html()+'</div></div>');"
    "$('#textInput').val('');"
    "$('.msger-chat').scrollTop($('.msger-chat')[0].scrollHeight);"
    "$.post('/ask_bot',{msg:t,session_id:sid}).done(function(d){"
    "$('.msger-chat').append('<div class=\"msg left-msg\"><div class=\"msg-bubble\">'+$('<div>').text(d.msg).html()+'</div></div>');"
    "$('.msger-chat').scrollTop($('.msger-chat')[0].scrollHeight);"
    "});});"
    "</script></body></html>"
)

app = Flask(__name__)
store = {}

def get_session_history(session_id):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

def get_bot_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm
    return RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )

bot_chain = get_bot_chain()

@app.route("/")
def home():
    return HTML

@app.route("/ask_bot", methods=["POST"])
def ask_bot():
    user_msg = (request.form.get("msg") or "").strip()
    session_id = (request.form.get("session_id") or "default").strip()
    if not user_msg:
        return jsonify({"msg": "Por favor escribe un mensaje."})
    try:
        config = {"configurable": {"session_id": session_id}}
        response = bot_chain.invoke({"input": user_msg}, config=config)
        return jsonify({"msg": response.content})
    except Exception as e:
        return jsonify({"msg": "Error: " + str(e)})

@app.route("/buscar_cliente", methods=["POST"])
def buscar_cliente_endpoint():
    data = request.json
    dni = data.get("dni", "")
    nombre = data.get("nombre", "")
    if dni:
        cliente = buscar_cliente_por_dni(dni)
    else:
        cliente = buscar_cliente_por_nombre(nombre)
    if cliente:
        return jsonify({"encontrado": True, "cliente": cliente})
    return jsonify({"encontrado": False})

@app.route("/registrar_cliente", methods=["POST"])
def registrar_cliente_endpoint():
    data = request.json
    exito, resultado = registrar_cliente(
        data.get("nombre"), data.get("dni"),
        data.get("telefono"), data.get("email"), data.get("direccion")
    )
    return jsonify({"exito": exito,
                    "cliente_id": resultado if exito else None,
                    "mensaje": "Cliente registrado." if exito else resultado})

@app.route("/registrar_mascota", methods=["POST"])
def registrar_mascota_endpoint():
    data = request.json
    mascota_id = registrar_mascota(
        data.get("cliente_id"), data.get("nombre"),
        data.get("especie"), data.get("sexo"),
        data.get("peso", 0), data.get("edad", 0),
        data.get("microchip", False), data.get("vacuna_rabia", False)
    )
    return jsonify({"mascota_id": mascota_id})

@app.route("/reservar", methods=["POST"])
def reservar():
    data = request.json
    exito, msg = reservar_cita(
        data.get("fecha"), data.get("cliente_id"),
        data.get("mascota_id"), data.get("tipo_cirugia")
    )
    return jsonify({"exito": exito, "mensaje": msg})

@app.route("/citas", methods=["GET"])
def ver_citas():
    fecha = request.args.get("fecha")
    citas = listar_citas(fecha)
    return jsonify({"citas": citas})

@app.route("/fechas_disponibles", methods=["GET"])
def fechas_disponibles():
    tipo = request.args.get("tipo", "gata_hembra")
    dias = ["Lunes","Martes","Miercoles","Jueves"]
    meses = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    operativos = []
    dia = datetime.now().date()
    while len(operativos) < 8:
        dia += timedelta(days=1)
        if dia.weekday() in [0,1,2,3]:
            fecha_str = dia.strftime("%Y-%m-%d")
            disponible, _ = verificar_disponibilidad(fecha_str, tipo)
            operativos.append({
                "fecha": fecha_str,
                "texto": dias[dia.weekday()] + " " + str(dia.day) + " de " + meses[dia.month-1] + " de " + str(dia.year),
                "disponible": disponible
            })
    disponibles = [d for d in operativos if d["disponible"]]
    return jsonify({"fechas": disponibles[:5]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
