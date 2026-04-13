# 🐾 Veterinaria Chatbot - ENAE

Chatbot conversacional desarrollado para la gestión del proceso de esterilización en una clínica veterinaria.

Este proyecto forma parte del curso:
**Data Science e IA para la Toma de Decisiones — ENAE Business School**

---

# 🎯 Propósito del proyecto

El objetivo es diseñar y desarrollar un asistente conversacional capaz de:

- Guiar al usuario paso a paso en la solicitud de esterilización
- Validar condiciones clínicas antes de la cirugía
- Gestionar disponibilidad de agenda
- Registrar clientes, mascotas y citas
- Mejorar la eficiencia operativa de la clínica

---

# 🧩 Problema que resuelve

En entornos reales, las clínicas veterinarias se enfrentan a:

- Saturación de llamadas telefónicas
- Errores en la recogida de datos
- Reservas duplicadas o incorrectas
- Falta de validaciones clínicas previas
- Pérdida de tiempo en tareas repetitivas

Este chatbot automatiza el proceso garantizando:

- Datos estructurados
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

- **Python** → lógica principal
- **FastAPI** → API backend
- **SQLite** → base de datos
- **HTML + JavaScript** → interfaz web básica
- **Uvicorn** → servidor
- **Markdown** → documentación estructurada
- **Cursor (IA)** → desarrollo asistido

---

# 🏗️ Arquitectura del sistema

Usuario (Web)
↓
Frontend (HTML + JS)
↓
FastAPI (main.py)
↓
Lógica conversacional
↓
agenda.py (persistencia y validaciones)
↓
SQLite (agenda.db)

El sistema se apoya en documentación estructurada en `/docs`:

- Reglas de negocio
- Preoperatorio
- Postoperatorio

---

## 📋 Gestión del proyecto (Jira)

El desarrollo del proyecto ha sido gestionado mediante Jira siguiendo un enfoque tipo Kanban.

Se han definido 15 tickets que cubren todo el ciclo de desarrollo:

- Configuración inicial
- Diseño del flujo conversacional
- Persistencia en base de datos
- Validaciones clínicas
- Gestión de citas
- Pruebas funcionales
- Despliegue
- Limpieza final del repositorio

📄 Documentación completa de tickets:
👉 docs/tickets.md

---

# 🔄 Flujo funcional del chatbot

1. Identificación del cliente
2. Registro o recuperación de datos
3. Registro de mascota
4. Validaciones clínicas
5. Consulta de disponibilidad
6. Selección de fecha
7. Confirmación de cita

---

# 📋 Reglas de negocio implementadas

- Días operativos: lunes a jueves
- Capacidad diaria: 240 minutos
- Máximo 2 perros por día
- Bloqueo si:
  - No hay vacuna
  - No hay microchip
  - Perra en celo
- Control de fechas pasadas
- Citas no duplicadas

---

# 📂 Documentación de dominio

Ubicación: `/docs`

Incluye:

- `business-rules.md`
- `pre-operative-considerations.md`
- `post-operative-considerations.md`

Permite:

- Separar lógica de negocio del código
- Facilitar mantenimiento
- Preparar evolución a RAG

---

# 🧠 Metodología SDD (Spec Driven Development)

El proyecto sigue un enfoque basado en especificación:

- Cada funcionalidad nace en Jira
- Cada desarrollo está vinculado a un ticket
- GitHub refleja la implementación
- Jira refleja planificación y estado

Reglas:

- No se implementa sin ticket
- No se cierra sin validación
- Repo + Jira siempre sincronizados

---

# 🔧 Flujo de trabajo

1. Creación de ticket en Jira
2. Definición de requisitos
3. Implementación en código
4. Pruebas manuales
5. Actualización de Jira

---

# 🧪 Enriquecimiento de tickets

Se ha aplicado proceso de mejora de tickets:

De:

> "Crear chatbot"

A:

- Objetivo
- Criterios de aceptación
- Riesgos
- Dependencias

Este proceso mejora la calidad del desarrollo.

---

# 🤖 API

Endpoints principales:

### GET /

Estado del sistema

### POST /ask_bot

Procesa mensajes del usuario

Ejemplo:

{  
 "message": "quiero esterilizar a mi perro",  
 "session_id": "test-session"  
}

---

# 💬 Interfaz de chat

- Interfaz web simple
- Conexión directa con backend
- Uso en navegador💬 Interfaz de chat (VET-8)

---

# 🧠 Lógica del chatbot

- Integración con modelo LLM
- Prompt controlado
- Flujo guiado paso a paso
- Una pregunta por interacción

---

# 🔁 Memoria de conversación

El sistema utiliza `session_id` para mantener contexto:

- Cada sesión es independiente
- Permite coherencia en la conversación

Limitación actual:

- Memoria en runtime (no persistente)

---

# 📚 RAG (simulado)

Actualmente:

- Uso de documentos locales en `/docs`
- Simulación de recuperación de información

Mejora futura:

- Integración con fuente oficial online
- Recuperación dinámica de contenido

---

# 📅 Disponibilidad

- Sistema mock de fechas disponibles
- Generación dinámica

---

# ⚠️ Limitación actual

Actualmente:

- No hay integración con calendario real

Mejora futura:

- Google Calendar / Calendly
- Automatización completa de agenda

---

# 🗄️ Modelo de datos

### Clientes

- id
- nombre
- dni
- telefono
- email
- direccion

### Mascotas

- id
- cliente_id
- nombre
- especie
- sexo
- edad
- peso
- microchip
- vacuna

### Citas

- id
- fecha
- cliente_id
- mascota_id
- tipo_cirugia
- minutos
- estado

---

# 🚀 Instalación y ejecución

git clone [https://github.com/vegettux/veterinaria-chatbot](https://github.com/vegettux/veterinaria-chatbot)  
cd veterinaria-chatbot  

python -m venv venv  
venv\Scripts\activate  

pip install -r requirements.txt

### Configurar `.env`:

GROQ_API_KEY=tu_clave_groq
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=postgresql://usuario:password@host:5432/dbname

### Ejecutar:

uvicorn main:app --reload

python -m uvicorn main:app --reload

### Abrir en navegador:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

# 🌐 Despliegue

Aplicación desplegada en:

👉 [https://veterinaria-chatbot.vercel.app](https://veterinaria-chatbot.vercel.app)

## Integración en Vercel con Postgres

1. Crea una base de datos Postgres gestionada (por ejemplo Neon).
2. En Vercel, configura la variable de entorno `DATABASE_URL`.
3. Despliega el proyecto con `main.py` como entrada Python.
4. Ejecuta la migración de datos una sola vez:

```bash
python scripts/migrate_sqlite_to_postgres.py
```

5. Verifica los endpoints:
   - `GET /`
   - `POST /ask_bot`

---

# 🔗 Enlaces del proyecto

- GitHub:  
[https://github.com/vegettux/veterinaria-chatbot](https://github.com/vegettux/veterinaria-chatbot)
- Jira:  
[https://veterinaria-chatbot.atlassian.net](https://veterinaria-chatbot.atlassian.net)

---

# 🧪 Casos de uso probados

- Cliente nuevo
- Cliente registrado
- Perro / Gato
- Validaciones clínicas
- Fechas válidas / inválidas
- Reserva completa

---

# 📈 Mejoras futuras

- Integración con calendario real
- Notificaciones (email / WhatsApp)
- Panel administrativo
- Historial clínico
- RAG real con documentación veterinaria

---

# 📌 Conclusión

Este proyecto demuestra cómo un chatbot puede:

- Automatizar procesos reales
- Aplicar reglas de negocio complejas
- Mejorar la experiencia del cliente
- Reducir carga operativa

---

# 👨‍💻 Autor

**José Gil**  
Máster Big Data & IA — ENAE