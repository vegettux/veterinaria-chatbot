# 🐾 Veterinaria Chatbot - ENAE

Chatbot conversacional desarrollado para la gestión del proceso de esterilización en una clínica veterinaria.

El sistema guía al usuario paso a paso desde la solicitud inicial hasta la confirmación de la cita, incluyendo validaciones clínicas, instrucciones preoperatorias y postoperatorias, y gestión de disponibilidad en tiempo real.

---

# 🎯 Propósito del proyecto

Este proyecto tiene como objetivo digitalizar y optimizar el proceso de reserva de esterilizaciones en clínicas veterinarias, reduciendo la carga operativa del personal administrativo y mejorando la experiencia del cliente.

El chatbot actúa como un asistente especializado que:

- Recoge información de forma estructurada
- Aplica reglas clínicas automáticamente
- Evita errores en la reserva de citas
- Ofrece disponibilidad real
- Genera confirmaciones coherentes y completas

---

# 🧩 Problema que resuelve

En entornos reales, las clínicas veterinarias se enfrentan a:

- Saturación de llamadas telefónicas
- Errores en la recogida de datos del cliente
- Reservas incorrectas o duplicadas
- Falta de validaciones previas
- Pérdida de tiempo en tareas repetitivas

Este chatbot automatiza ese flujo, garantizando:

- Datos correctos
- Validación clínica previa
- Control de agenda
- Reducción de errores humanos

---

# 👥 Público objetivo

- Clínicas veterinarias
- Personal administrativo
- Clientes que desean realizar una esterilización

---

# ⚙️ Tecnologías utilizadas

- **Python** → Lógica principal
- **FastAPI** → API backend
- **SQLite** → Persistencia de datos
- **HTML + JavaScript** → Interfaz web básica
- **python-dotenv** → Gestión de variables de entorno
- **Cursor** → Asistencia al desarrollo
- **Markdown** → Reglas de negocio y documentación viva del sistema

---

# 🧠 Arquitectura del sistema

El sistema sigue una arquitectura sencilla pero profesional:

```text
Usuario (Web)
↓
Frontend HTML + JS
↓
FastAPI (main.py)
↓
Lógica conversacional + reglas de decisión
↓
agenda.py (persistencia y validación de agenda)
↓
SQLite (agenda.db)

Además, la aplicación se apoya en documentación estructurada dentro de docs/ para separar:

reglas de negocio
consideraciones preoperatorias
consideraciones postoperatorias

📚 Base documental del sistema

El proyecto incorpora una base documental interna en formato Markdown:

docs/business-rules.md
docs/pre-operative-considerations.md
docs/post-operative-considerations.md

Esto permite:

separar el contenido del código
mantener una fuente de verdad del negocio
facilitar la evolución del sistema
preparar el proyecto para un futuro enfoque RAG
🔄 Flujo funcional del chatbot

El chatbot sigue un flujo estrictamente controlado:

1. Identificación del cliente

- Cliente registrado → búsqueda por DNI
- Cliente nuevo → registro completo
- Si el usuario cree ser cliente pero su DNI no existe:
  - el sistema lo detecta
  - solicita confirmación para alta nueva
  - reutiliza el DNI validado si autoriza el alta

2. Registro de mascota

- Nombre
- Especie
- Sexo
- Edad
- Peso (cuando aplica)
- Celo (cuando aplica)

3. Validaciones clínicas

- Microchip obligatorio
- Vacuna antirrábica obligatoria
- Estado sanitario
- Enfermedades conocidas
- Analítica en mayores de 6 años

4. Reglas de negocio

- Bloqueo si no hay vacuna
- Bloqueo por celo
- Bloqueo de fechas pasadas
- Bloqueo del día actual fuera de horario
- Bloqueo de citas duplicadas por mascota

5. Disponibilidad

- Cálculo según tipo de cirugía
- Restricción por tiempo
- Restricción por número máximo de perros por día

6. Confirmación

- Reserva real en base de datos
- Horarios de entrega y recogida
- Información documental asociada

🧾 Reglas de negocio implementadas

- Días operativos: lunes a jueves
- Capacidad diaria máxima: 240 minutos
- Máximo 2 perros por día
- Los gatos se limitan por tiempo disponible
- El cliente elige solo el día, no la hora
- Se calculan tiempos según:
  - especie
  - sexo
  - peso (en perras)

🔌 Endpoints disponibles

GET /
Devuelve la interfaz web del chatbot.

POST /ask_bot
Procesa los mensajes del usuario.

Ejemplo de request:
{
  "message": "quiero esterilizar a mi perro",
  "session_id": "test-session-001"
}

Ejemplo de response:
{
  "response": "¿Cuál es el nombre de tu mascota?",
  "session_id": "test-session-001"
}

GET /fechas_disponibles:
Devuelve fechas disponibles de cirugía.

🗃️ Modelo de datos (SQLite)

Tabla clientes:
- id
- nombre
- dni
- telefono
- email
- direccion

Tabla mascotas:
- id
- cliente_id
- nombre
- especie
- sexo
- peso
- edad
- tiene_microchip
- tiene_vacuna_rabia

Tabla citas:
- id
- fecha
- cliente_id
- mascota_id
- tipo_cirugia
- minutos
- estado

📁 Estructura del proyecto
VETERINARIA-CHATBOT/
│
├── main.py
├── agenda.py
├── agenda.db
├── requirements.txt
├── README.md
├── .env
├── .env.example
├── .gitignore
│
├── docs/
│   ├── business-rules.md
│   ├── pre-operative-considerations.md
│   └── post-operative-considerations.md
│
├── venv/
├── __pycache__/
└── .cursor/

🚀 Instalación y ejecución:

1. Clonar repositorio
- git clone <URL_DEL_REPOSITORIO>
- cd VETERINARIA-CHATBOT

2. Crear entorno virtual
- python -m venv venv
- venv\\Scripts\\activate

3. Instalar dependencias
- pip install -r requirements.txt

4. Configurar variables de entorno
- Crear archivo .env a partir de .env.example
OPENAI_API_KEY=your_openai_api_key_here

5. Ejecutar servidor
- python -m uvicorn main:app --reload

6. Acceder
- Abrir en navegador:
http://127.0.0.1:8000

🧪 Casos de uso probados / previstos
- Cliente nuevo
- Cliente registrado
- Cliente que cree estar registrado pero no existe en base de datos
- Alta autorizada tras DNI no encontrado
- Perro / perra / gato / gata
- Validación de vacuna
- Bloqueo por falta de microchip
- Bloqueo por celo
- Bloqueo por fecha inválida
- Confirmación de cita
- Consulta de cita existente
- Consulta de preoperatorio
- Consulta de postoperatorio

🧩 Mejoras futuras
- Sustituir fechas mock por fechas realmente calculadas desde agenda
- Integración con calendario real
- Integración con sistema real de clínica
- Notificaciones automáticas (WhatsApp / Email)
- Panel administrativo
- Historial clínico
- Enfoque RAG real sobre documentación veterinaria
- Registro formal de consentimiento y política de privacidad

📌 Conclusión
Este proyecto demuestra cómo un asistente conversacional puede automatizar procesos reales de negocio, aplicando reglas complejas y garantizando coherencia en la interacción.

Se ha priorizado:
- Control del flujo conversacional
- Validación de datos
- Persistencia real
- Separación entre lógica y documentación
- Escalabilidad del sistema

👨‍💻 Autor
José Gil
Máster Big Data & AI – ENAE