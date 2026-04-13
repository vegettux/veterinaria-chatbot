# Checklist de validación Vercel + Postgres

## 1) Configuración de entorno
- [ ] `DATABASE_URL` configurada en Vercel (Preview y Production).
- [ ] `GROQ_API_KEY` configurada en Vercel.
- [ ] `GROQ_MODEL` configurada en Vercel (opcional, con valor por defecto).
- [ ] Deploy completado sin errores de build.

## 2) Migración de datos
- [ ] Ejecutar `python scripts/migrate_sqlite_to_postgres.py`.
- [ ] Verificar en consola conteos por tabla (`clientes`, `mascotas`, `citas`, `cambios_cita`).
- [ ] Confirmar que los IDs de relaciones (`cliente_id`, `mascota_id`) son consistentes.

## 3) Pruebas funcionales API
- [ ] `GET /` responde correctamente con la interfaz web.
- [ ] `POST /ask_bot` responde sin error en un flujo de sesión nuevo.
- [ ] Alta de cliente nuevo funciona.
- [ ] Alta de mascota nueva funciona.
- [ ] Reserva de cita confirmada funciona.
- [ ] Reprogramación de cita confirmada funciona.
- [ ] Las reglas de negocio se mantienen (lunes-jueves, 240 min/día, máximo 2 perros).

## 4) Pruebas de regresión mínima
- [ ] Confirmar ventana de entrega para gatos: 08:00-09:00.
- [ ] Confirmar ventana de entrega para perros: 09:00-10:30.
- [ ] Confirmar mensajes de confirmación con recogida aproximada y documentación requerida.
- [ ] Confirmar bloqueo cuando no hay vacuna antirrábica.
- [ ] Confirmar restricción de perra en celo.
