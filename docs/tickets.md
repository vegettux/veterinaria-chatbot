# 📋 Trazabilidad completa del proyecto (Jira → Desarrollo)

Este documento recoge la planificación y ejecución del proyecto a través de tickets gestionados en Jira, manteniendo trazabilidad directa con el código implementado en el repositorio.

## 🧩 TICKET 1 — Configuración inicial del proyecto y entorno de desarrollo
**Estado:** Finalizado

### Descripción
Configuración inicial del proyecto VETERINARIA-CHATBOT en entorno local.

### Trabajo realizado
- Creación de la estructura base del proyecto
- Configuración de entorno Python
- Creación de archivos principales:
  - main.py
  - agenda.py
  - agenda.db
  - requirements.txt
  - README.md
  - .env
  - .gitignore
- Preparación del entorno con FastAPI y Uvicorn
- Organización del repositorio

### Objetivo
Disponer de una base técnica estable.

### Resultado esperado
Proyecto ejecutable en local.

---

## 🧩 TICKET 2 — Diseño del flujo conversacional
**Estado:** Finalizado

### Trabajo realizado
- Definición del comportamiento del asistente
- Diseño del prompt
- Flujo paso a paso
- Control de una pregunta por mensaje
- Reglas para:
  - cliente registrado
  - cliente nuevo
  - mascota
  - validaciones
  - preoperatorio
  - disponibilidad
  - confirmación
  - postoperatorio

### Objetivo
Conversación coherente y natural.

---

## 🧩 TICKET 3 — Identificación de cliente registrado
**Estado:** Finalizado

### Trabajo realizado
- Pregunta inicial de cliente
- Solicitud de DNI / nombre
- Búsqueda en SQLite
- Funciones:
  - buscar_cliente_por_dni
  - buscar_cliente_por_nombre

### Objetivo
Evitar duplicidades.

---

## 🧩 TICKET 4 — Alta de cliente nuevo
**Estado:** Finalizado

### Trabajo realizado
- Captura de:
  - nombre
  - DNI
  - teléfono
  - email
  - dirección
- Persistencia en SQLite

### Objetivo
Registrar nuevos clientes.

---

## 🧩 TICKET 5 — Registro de mascota
**Estado:** Finalizado

### Trabajo realizado
- Captura de:
  - nombre
  - especie
  - sexo
  - edad
  - peso
  - celo
  - microchip
  - vacuna
- Asociación con cliente

### Objetivo
Disponer de datos clínicos.

---

## 🧩 TICKET 6 — Validaciones clínicas
**Estado:** En curso

### Trabajo realizado
- Validación de microchip
- Validación de vacuna
- Bloqueo de flujo si no cumple
- Gestión de enfermedades

### Objetivo
Evitar errores clínicos.

---

## 🧩 TICKET 7 — Gestión de disponibilidad
**Estado:** Finalizado

### Trabajo realizado
- Generación de fechas
- Validación de fechas
- Bloqueo de fechas pasadas
- Cálculo de cirugía

### Objetivo
Fechas coherentes.

---

## 🧩 TICKET 8 — Reserva de citas
**Estado:** Finalizado

### Trabajo realizado
- Inserción en DB:
  - fecha
  - cliente_id
  - mascota_id
  - tipo_cirugia
- Confirmación al usuario

### Objetivo
Persistir citas.

---

## 🧩 TICKET 9 — Control de errores
**Estado:** En curso

### Trabajo realizado
- Corrección de bugs
- Mejora del flujo
- Validación de respuestas
- Pruebas iterativas

### Objetivo
Sistema robusto.

---

## 🧩 TICKET 10 — Pruebas funcionales
**Estado:** En curso

### Casos probados
- cliente nuevo
- cliente registrado
- perro / gato
- validaciones
- reservas

### Objetivo
Validación completa.

---

## 🧩 TICKET 11 — Documentación
**Estado:** En curso

### Trabajo realizado
- README
- Arquitectura
- endpoints
- flujo
- instalación

### Objetivo
Facilitar evaluación.

---

## 🧩 TICKET 12 — Cambio de cita
**Estado:** Finalizado

### Trabajo realizado
- Detección de cita existente
- Nuevas fechas
- Validación
- Actualización DB

### Objetivo
Permitir reprogramación.

---

## 🧩 TICKET 13 — Documentación externa (docs/)
**Estado:** Finalizado

### Trabajo realizado
- Creación carpeta docs/
- Archivos:
  - business-rules.md
  - pre-operative-considerations.md
  - post-operative-considerations.md

### Objetivo
Separar lógica del código.

---

## 🧩 TICKET 14 — Despliegue en Vercel
**Estado:** Finalizado

### Trabajo realizado
- Configuración despliegue
- Validación en producción

### Objetivo
Acceso público.

---

## 🧩 TICKET 15 — Limpieza del repositorio
**Estado:** Finalizado

### Trabajo realizado
- Eliminación de:
  - agenda.db
  - .env
- Configuración .gitignore
- Limpieza de archivos

### Objetivo
Repositorio profesional.

---

# 🔗 Enlace Jira

https://veterinaria-chatbot.atlassian.net