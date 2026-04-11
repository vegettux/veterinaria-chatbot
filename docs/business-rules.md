# 🧠 Reglas de Negocio — Clínica Veterinaria

## 1. Capacidad Operativa

- Días operativos de cirugía: lunes a jueves
- Ventana quirúrgica: 09:00 a 13:00
- Capacidad diaria máxima: 240 minutos

El sistema funciona por consumo de minutos, no por horas.

---

## 2. Tiempos de Cirugía

### Gatos
- Gato macho: 12 minutos
- Gata hembra: 15 minutos

### Perros
- Perro macho: 30 minutos
- Perra 0–10 kg: 45 minutos
- Perra 10–20 kg: 50 minutos
- Perra 20–30 kg: 60 minutos
- Perra 30–40 kg: 60 minutos
- Perra >40 kg: 70 minutos

---

## 3. Reglas de Disponibilidad

Para aceptar una cita deben cumplirse:

### Regla 1 — Capacidad
(minutos ocupados + minutos nueva cita) ≤ 240

### Regla 2 — Límite de perros
Máximo 2 perros por día

- Si ya hay 2 perros → no se aceptan más perros
- Sí se pueden seguir aceptando gatos si hay tiempo

---

## 4. Selección de cita

- El cliente NO elige hora
- El cliente solo elige el día

---

## 5. Ventanas de entrega

### Gatos
- Entrega: 08:00 – 09:00
- Recogida aproximada: 15:00

### Perros
- Entrega: 09:00 – 10:30
- Recogida aproximada: 12:00

---

## 6. Reglas clínicas obligatorias

- Microchip obligatorio
- Vacuna antirrábica obligatoria
- Animales deben estar vacunados y desparasitados
- Si no cumple → NO se puede operar

---

## 7. Casos especiales

### Perras en celo
- NO se pueden operar
- Esperar 2 meses tras el celo

### Animales con enfermedad
- Debe informarse antes
- Puede estar contraindicado

### Animales > 6 años
- Analítica preoperatoria obligatoria

---

## 8. Ayuno preoperatorio

- Comida: 8–12 horas antes
- Agua: hasta 1–2 horas antes

---

## 9. Política de cancelación

- Avisar con al menos 24 horas
- Puede aplicarse recargo si no se avisa

---

## 10. Restricciones del servicio

- La clínica NO atiende urgencias
- Solo gestiona:
  - Esterilización
  - Vacunación
  - Microchip

---

## 11. Confirmación de cita

Al confirmar una cita se debe informar:

- Día de la intervención
- Ventana de entrega
- Hora aproximada de recogida
- Instrucciones de ayuno
- Documentación necesaria

---

## 12. Reglas de decisión clínica para aceptación de cirugía

El sistema debe validar las siguientes condiciones antes de permitir una reserva:

### 1. Especie y tipo de intervención
- Solo se permite:
  - Esterilización canina (perros)
  - Esterilización felina (gatos)
  - Vacunación
  - Implantación de microchip

---

### 2. Sexo del animal
- El tipo de cirugía depende del sexo:
  - Macho → castración
  - Hembra → ovariohisterectomía

- Las hembras implican mayor tiempo quirúrgico y complejidad

---

### 3. Peso (solo perros)
- El peso determina la duración de la cirugía
- Impacta directamente en la disponibilidad de agenda

---

### 4. Estado de celo (solo perras)
- Si está en celo:
  - ❌ NO se permite la cirugía
  - Debe esperar al menos 2 meses tras finalizar el celo

---

### 5. Vacuna antirrábica
- Obligatoria
- Si no está al día:
  - ❌ NO se puede reservar cirugía

---

### 6. Microchip
- Obligatorio
- Puede implantarse el mismo día de la cirugía (con coste adicional)

---

### 7. Estado sanitario
- Debe estar vacunado y desparasitado
- Si no:
  - Puede requerir regularización previa

---

### 8. Enfermedades conocidas
- Si el animal tiene enfermedad:
  - Se debe evaluar previamente
  - La cirugía puede estar contraindicada

---

### 9. Edad
- Si el animal tiene más de 6 años:
  - Analítica preoperatoria obligatoria

---

## 13. Impacto en la agenda

Estas variables afectan directamente a:

- Duración de la cirugía
- Disponibilidad diaria (240 minutos)
- Número máximo de perros
- Posibilidad de aceptar o rechazar una cita

El sistema debe validar estas condiciones antes de confirmar cualquier reserva.