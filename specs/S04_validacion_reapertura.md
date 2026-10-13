# SPEC: S04 · Título: Validación de Solución (Confirmación, Rechazo) y Reapertura en 48 Horas UTC

- **Versión / autor / revisor / fecha:** v1.1 (Aprobada) / Autor: Juan Jiménez / Revisor: Roberto Rueda / Fecha: 07/10/2026
- **Requisito asociado:** RF04
- **Historia:** Como **solicitante dueño de una incidencia**, quiero **confirmar o rechazar con motivo una solución pendiente de validación, así como reabrir una incidencia cerrada dentro de las 48 horas siguientes al último cierre**, para **garantizar que el daño de infraestructura haya quedado verdaderamente solucionado antes de su cierre definitivo**.

## Alcance y exclusiones
- **Incluye:** Confirmación de solución (`PENDIENTE_VALIDACION` -> `CERRADA`) por el solicitante dueño; rechazo de solución (`PENDIENTE_VALIDACION` -> `EN_ATENCION`) con motivo de 10 a 300 caracteres conservando el mismo técnico y la solución anterior; reapertura (`CERRADA` -> `EN_ATENCION`) por el solicitante dueño con motivo de 10 a 300 caracteres cuando el tiempo transcurrido desde el último cierre en reloj UTC del servidor es `<= 48 horas` (`<= 172800` segundos), conservando el mismo técnico, todos los cierres y todas las soluciones anteriores.
- **Excluye:** Cierre automático por tiempo; confirmación, rechazo o reapertura por parte del coordinador, del técnico o de otro solicitante distinto al dueño; uso de la hora del navegador del cliente para validar el plazo de 48 horas.

## Entradas: tipos, obligatoriedad y límites
1. **Confirmar solución (`POST /incidencias/<id>/confirmar`):**
   - `incidencia_id` (`int`, obligatorio): Incidencia en estado `PENDIENTE_VALIDACION`.
2. **Rechazar solución (`POST /incidencias/<id>/rechazar`):**
   - `incidencia_id` (`int`, obligatorio): Incidencia en estado `PENDIENTE_VALIDACION`.
   - `motivo` (`string`, obligatorio): Motivo del rechazo de **10 a 300 caracteres** inclusive después de `strip()`.
3. **Reabrir incidencia (`POST /incidencias/<id>/reabrir`):**
   - `incidencia_id` (`int`, obligatorio): Incidencia en estado `CERRADA`.
   - `motivo` (`string`, obligatorio): Motivo de reapertura de **10 a 300 caracteres** inclusive después de `strip()`.

## Precondiciones y permisos
- Usuario autenticado con rol `SOLICITANTE` y cuyo `user_id` sea igual a `incidencia.autor_id` (solicitante dueño).
- Si otro solicitante (p. ej. `S02` sobre un reporte de `S01`), el coordinador `C01` o un técnico (`T01`, `T02`) intenta confirmar, rechazar o reabrir, el servidor responde HTTP `403 Forbidden`.

## Reglas y proceso
1. **Verificación de propiedad:** Comprobar en servidor `session['rol'] == 'SOLICITANTE'` y `incidencia.autor_id == session['user_id']`.
2. **Confirmar solución:**
   - Verificar `incidencia.estado == 'PENDIENTE_VALIDACION'`.
   - Obtener `now_utc` del reloj UTC del servidor.
   - En transacción SQLite: actualizar `estado = 'CERRADA'`, `fecha_ultimo_cierre = now_utc`, insertar registro en tabla `cierres` e insertar evento `'CIERRE'` en `historial_eventos`.
3. **Rechazar solución:**
   - Verificar `incidencia.estado == 'PENDIENTE_VALIDACION'`.
   - Validar `10 <= len(motivo.strip()) <= 300`.
   - En transacción SQLite: actualizar `estado = 'EN_ATENCION'` mantendo intactos `tecnico_asignado_id` y las soluciones anteriores; insertar evento `'RECHAZO_SOLUCION'` en `historial_eventos` con autor, fecha UTC y el motivo.
4. **Reabrir incidencia:**
   - Verificar `incidencia.estado == 'CERRADA'` y que exista `fecha_ultimo_cierre`.
   - Validar `10 <= len(motivo.strip()) <= 300`.
   - Calcular en servidor `delta_segundos = (now_utc - fecha_ultimo_cierre_utc).total_seconds()`.
   - Si `delta_segundos > 48 * 3600` (es decir, mayor a 172.800 segundos), rechazar con HTTP 400 sin modificar estado ni historial.
   - Si `0 <= delta_segundos <= 48 * 3600`, en transacción SQLite: actualizar `estado = 'EN_ATENCION'` conservando el mismo `tecnico_asignado_id`, todos los cierres en `cierres`, todas las soluciones en `soluciones`, e insertar evento `'REAPERTURA'` en `historial_eventos` con autor, fecha UTC y motivo.

## Salidas y cambios persistidos
- **Persistencia:** Actualización atómica en `incidencias`, registro en `cierres` (al confirmar) y nuevo evento en `historial_eventos` (`CIERRE`, `RECHAZO_SOLUCION` o `REAPERTURA`) conservando íntegros los registros previos.

## Errores y efectos que deben evitarse
- **Propietario ajeno o rol no permitido (HTTP 403):** Ni `S02`, ni `C01`, ni `T01` pueden confirmar, rechazar o reabrir un reporte de `S01`.
- **Motivo fuera de límites (HTTP 400):** Motivo de menos de 10 caracteres (p. ej. 9 chars tras `strip()`) o más de 300 caracteres se rechaza sin alterar el estado ni el historial.
- **Reapertura fuera de plazo (> 48 h UTC) (HTTP 400):** Si han transcurrido 48 horas y 1 segundo desde el último cierre UTC, se rechaza sin cambios.

## Criterios de aceptación (Dado / Cuando / Entonces)
- **AC-S04-01 (Confirmación de solución por el solicitante dueño):** **Dado** un reporte propio de `S01` en estado `PENDIENTE_VALIDACION`, **cuando** `S01` confirma la solución, **entonces** la incidencia pasa a estado `CERRADA`, se registra la fecha UTC del cierre y se añade el evento `CIERRE` en el historial.
- **AC-S04-02 (Rechazo válido conserva técnico y solución anterior):** **Dado** un reporte propio de `S01` en `PENDIENTE_VALIDACION` con técnico `T01` y solución registrada, **cuando** `S01` lo rechaza con el motivo `"El daño sigue presente en el toma"` (33 caracteres), **entonces** queda en estado `EN_ATENCION`, conserva el técnico `T01` y la solución anterior, y registra en el historial quién rechazó, cuándo (UTC) y por qué.
- **AC-S04-03 (Rechazo inválido por longitud de motivo):** **Dado** un reporte propio de `S01` en `PENDIENTE_VALIDACION`, **cuando** `S01` intenta rechazarlo con un motivo de 9 caracteres (`"Sigue mal"`) o de 301 caracteres tras `strip()`, **entonces** el servidor responde HTTP 400, la incidencia permanece en `PENDIENTE_VALIDACION` y no se agrega ningún evento al historial.
- **AC-S04-04 (Reapertura exactamente a las 48 horas UTC):** **Dada** una incidencia propia de `S01` en estado `CERRADA` con técnico `T01`, **cuando** `S01` solicita reabrirla con motivo válido `"Volvió a fallar la luminaria"` exactamente a las 48 horas (172.800 segundos) del último cierre UTC, **entonces** el servidor acepta la operación, pasa la incidencia a `EN_ATENCION` con el mismo técnico `T01`, conserva todos los cierres y soluciones anteriores y registra el evento `REAPERTURA`.
- **AC-S04-05 (Rechazo de reapertura después de las 48 horas UTC):** **Dada** una incidencia propia de `S01` en estado `CERRADA`, **cuando** `S01` intenta reabrirla transcurridas 48 horas y 1 segundo (172.801 segundos) desde el último cierre UTC, **entonces** el servidor rechaza la operación con HTTP 400 sin cambios en el estado (`CERRADA`) ni en el historial.
- **AC-S04-06 (Bloqueo a otro solicitante, coordinador o técnico):** **Dada** una incidencia de `S01` en `PENDIENTE_VALIDACION` o `CERRADA`, **cuando** otro solicitante (`S02`), el coordinador (`C01`) o el técnico (`T01`) intenta confirmarla, rechazarla o reabrirla, **entonces** el servidor responde HTTP 403 Forbidden sin efectos en la base de datos.

## Diseño y tareas vinculadas a cada AC
- **Componente:** `app/services.py::confirmar_solucion()`, `rechazar_solucion()`, `reabrir_incidencia()` con reloj UTC inyectable (`get_utc_now()`) para pruebas deterministas.
- **Tareas:**
  - `TASK-401` (Juan Jiménez): Implementar `confirmar_solucion` y `rechazar_solucion` con validación de propietario y longitud 10..300 (AC-S04-01, AC-S04-02, AC-S04-03, AC-S04-06).
  - `TASK-402` (Juan Jiménez): Implementar `reabrir_incidencia` con cálculo UTC en servidor `<= 48h` e inyección de reloj para pruebas automatizadas (AC-S04-04, AC-S04-05).

## Pruebas y resultados esperados
- `test_05_confirmacion_y_rechazo_solucion`: Verifica rechazo con motivo inválido (9 chars), rechazo válido (conservando técnico y solución previa) y confirmación a `CERRADA`.
- `test_06_reapertura_limite_exacto_48h_y_posterior`: Usa reloj UTC controlado en servidor para verificar éxito exactamente a las 48h (`timedelta(hours=48)`) y rechazo a las 48h + 1s (`timedelta(hours=48, seconds=1)`).
- `test_07_permisos_propietario_ajeno_y_coordinador`: Verifica HTTP 403 cuando `S02` o `C01` intentan validar o reabrir un reporte de `S01`.

## Decisión de revisión / versión aprobada
- **Revisión v1.0 -> v1.1 (07/10/2026 por Roberto Rueda):** Se especificó el uso de un proveedor de tiempo UTC en servidor (`app.services.get_utc_now`) para comprobar en `pytest` tanto el límite exacto de 48h (`172800s`) como un instante posterior (`172801s`) sin depender del navegador ni esperar 48 horas reales. **Decisión:** APROBADA v1.1 para implementación.
