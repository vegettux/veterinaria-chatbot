# 🐾 Veterinaria Chatbot - ENAE

Chatbot conversacional desarrollado para la gestión del proceso de esterilización en una clínica veterinaria.

Este proyecto forma parte del curso:
**Data Science e IA para la Toma de Decisiones — ENAE Business School**

---

# 🎯 Objetivo del proyecto

Diseñar un asistente conversacional capaz de:

- Guiar al cliente paso a paso en el proceso de esterilización
- Validar condiciones clínicas antes de la cirugía
- Gestionar la disponibilidad quirúrgica en tiempo real
- Registrar clientes, mascotas y citas
- Reducir errores operativos y carga administrativa

---

# 🧩 Problema de negocio

En clínicas veterinarias reales:

- Saturación de llamadas
- Errores en recogida de datos
- Duplicidad de citas
- Falta de validación clínica previa
- Pérdida de tiempo en tareas repetitivas

---

# 💡 Solución propuesta

Este chatbot implementa:

- Flujo guiado paso a paso
- Validaciones clínicas automáticas
- Motor de agenda basado en reglas de negocio
- Persistencia estructurada de datos
- Interacción multidioma (ES/EN)

---

## 🔗 Enlaces del proyecto

- GitHub (código):  
  https://github.com/vegettux/veterinaria-chatbot  

- Aplicación desplegada (Vercel):  
  https://veterinaria-chatbot.vercel.app  

- Gestión del proyecto (Jira):  
  https://veterinaria-chatbot.atlassian.net  

  > 💡 Se recomienda acceder primero a la aplicación desplegada para probar el flujo completo del chatbot.

---

# 🧠 Valor diferencial

Este proyecto NO es un chatbot simple. Implementa:

### ✔ Máquina de estados conversacional
- Control total del flujo
- Validación por fases
- Prevención de errores de usuario

### ✔ Motor de agenda quirúrgica
- Basado en consumo de minutos
- Reglas reales de clínica
- Restricciones operativas complejas

### ✔ Sistema multidioma dinámico
- Detección automática de idioma
- Cambio en caliente durante la conversación

---

## 🏗️ Arquitectura del sistema

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
Base de datos (SQLite / PostgreSQL)

---

## ⚙️ Tecnologías utilizadas

- **Python** → lógica principal
- **FastAPI** → API backend
- **SQLite / PostgreSQL** → base de datos
- **Uvicorn** → servidor
- **HTML + JavaScript** → interfaz web
- **dotenv** → configuración entorno

---

## 📡 API

## Endpoint principal

### POST `/ask_bot`

Procesa la conversación del usuario:

 json
{
  "message": "quiero esterilizar a mi perro",
  "session_id": "123"
}

---


## 📡 Otros endpoints

### GET /
Interfaz web del chatbot

### GET /healthz
Estado del sistema y entorno

### GET /fechas_disponibles
Devuelve disponibilidad quirúrgica real

---

## 🔄 Flujo conversacional

### 1. Inicio
- Mensaje de bienvenida  
- Identificación de cliente  

### 2. Identificación
- Cliente existente → búsqueda por DNI  
- Cliente nuevo → registro  

### 3. Selección de acción
- Consulta informativa  
- Gestión de mascota  

### 4. Gestión de mascota
- Selección o alta  
- Consulta de cita  
- Cambio de cita  
- Información clínica  

### 5. Validaciones
- Edad  
- Vacunas  
- Microchip  
- Estado clínico  

### 6. Reserva
- Validación de disponibilidad  
- Confirmación de cita  

---

## 🧠 Lógica conversacional

El sistema funciona mediante:

- `session_id` → memoria de conversación  
- `conversation_store` → estado en runtime  

Control por fases:
- identificación  
- selección  
- operación  

---

## 🌐 Sistema multidioma

El chatbot:

- Detecta idioma automáticamente  
- Mantiene idioma durante la conversación  
- Permite cambio dinámico (ej: "español", "english")  

---

## 📋 Reglas de negocio

### Capacidad operativa
- Días: lunes a jueves  
- Capacidad diaria: 240 minutos  
- Sistema basado en tiempo quirúrgico  

---

### Tiempos de cirugía

#### Gatos
- Macho: 12 min  
- Hembra: 15 min  

#### Perros
- Macho: 30 min  
- Hembra:
  - 0–10 kg: 45 min  
  - 10–20 kg: 50 min  
  - 20–30 kg: 60 min  
  - 30–40 kg: 60 min  
  - +40 kg: 70 min  

---

### Restricciones
- Máximo 2 perros por día  
- No duplicidad de citas  
- Control de fechas válidas  

---

### Validaciones clínicas
- Microchip obligatorio  
- Vacuna antirrábica obligatoria  
- Estado sanitario adecuado  

---

### Casos especiales
- Perras en celo → ❌ NO operables  
- Animales > 6 años → analítica obligatoria  

---

## 🗄️ Modelo de datos

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

## 🧪 Casos de uso cubiertos

- Cliente nuevo  
- Cliente existente  
- Perro / gato  
- Consulta clínica  
- Reserva completa  
- Cambio de cita  
- Validación de reglas  

---

## ⚠️ Limitaciones actuales

- Memoria en runtime (no persistente)  
- No integración con calendario real  
- No notificaciones externas  

---

## 🚀 Mejoras futuras

- Integración con Google Calendar  
- Notificaciones (email / WhatsApp)  
- Panel administrativo  
- Persistencia de sesiones  
- RAG real con documentación veterinaria  

---

## 🧠 Metodología

Desarrollo basado en:

- Enfoque iterativo  
- Validación continua  
- Modelado de flujo conversacional  
- Implementación de reglas reales de negocio  

---

## 🔧 Instalación

bash
git clone https://github.com/vegettux/veterinaria-chatbot
cd veterinaria-chatbot

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

---

## ⚙️ Configuración

Crear archivo `.env`:

env
OPENAI_API_KEY=tu_clave
DATABASE_URL=sqlite:///./agenda.db

---

## ▶️ Ejecución

bash
uvicorn main:app --reload

---

## 🌐 Acceso

* Web: http://127.0.0.1:8000
* Docs: http://127.0.0.1:8000/docs

---

## 🌐 Despliegue

La aplicación está desplegada en la nube utilizando Vercel:

👉 https://veterinaria-chatbot.vercel.app  

---

## ⚙️ Infraestructura

- **Frontend + Backend** desplegados en Vercel
- **API FastAPI** ejecutándose como serverless
- **Base de datos**:
  - SQLite en local
  - PostgreSQL en entorno cloud (producción)

---

## 🔗 Variables de entorno

Configuradas en Vercel:

- `DATABASE_URL`
- `OPENAI_API_KEY` (si se usa LLM)
- `POSTGRES_URL` (opcional)

---

## 🚀 Flujo de despliegue

1. Push a GitHub  
2. Vercel detecta cambios automáticamente  
3. Build y despliegue automático  
4. API disponible en producción  

---

## 🧪 Verificación en producción

Endpoints disponibles:

- GET `/` → interfaz del chatbot  
- POST `/ask_bot` → interacción con el chatbot  
- GET `/healthz` → estado del sistema  

---

## ⚠️ Consideraciones

- En producción se usa PostgreSQL (no SQLite)  
- El sistema sigue funcionando con las mismas reglas de negocio  
- La memoria de conversación sigue siendo en runtime (no persistente)  

---

## 🧠 Nota técnica

El sistema está diseñado para ser independiente del motor de base de datos, 
permitiendo funcionar tanto en SQLite (desarrollo local) como en PostgreSQL (producción en Vercel) 
sin cambios en la lógica de negocio.

---

## 👨‍💻 Autor

José Gil
Máster Big Data & IA — ENAE
