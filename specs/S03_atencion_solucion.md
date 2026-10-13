# SPEC: S03 · Título: Inicio de Atención y Registro de Solución por el Técnico Asignado

- **Versión / autor / revisor / fecha:** v1.1 (Aprobada) / Autor: Juan Jiménez / Revisor: Osvaldo Navarro / Fecha: 07/10/2026
- **Requisito asociado:** RF03
- **Historia:** Como **técnico asignado**, quiero **iniciar la atención de una incidencia asignada a mí y posteriormente registrar la solución aplicada**, para **informar las acciones correctivas realizadas y enviar el reporte a validación del solicitante dueño**.

## Alcance y exclusiones
- **Incluye:** Transición de `ASIGNADA` a `EN_ATENCION` ejecutada exclusivamente por el técnico asignado; registro de solución (20 a 800 caracteres tras `strip()`) desde `EN_ATENCION` pasando a `PENDIENTE_VALIDACION`; preservación de todas las soluciones previas en caso de reintentos tras rechazo o reapertura; registro atómico en el historial.
- **Excluye:** Cierre directo del reporte por parte del técnico; atención por un técnico distinto al asignado; registro de solución directamente desde `ASIGNADA` sin haber iniciado atención primero.

## Entradas: tipos, obligatoriedad y límites
1. **Para iniciar atención (`POST /incidencias/<id>/iniciar`):**
   - `incidencia_id` (`int`, obligatorio): Identificador de la incidencia en estado `ASIGNADA`.
2. **Para registrar solución (`POST /incidencias/<id>/solucion`):**
   - `incidencia_id` (`int`, obligatorio): Identificador de la incidencia en estado `EN_ATENCION`.
   - `solucion` (`string`, obligatorio): Descripción técnica de la solución aplicada. Longitud obligatoria de **20 a 800 caracteres** inclusive después de retirar espacios externos (`strip()`).

## Precondiciones y permisos
- Usuario autenticado con rol `TECNICO` y cuyo `user_id` coincida exactamente con `incidencia.tecnico_asignado_id`.
- Otro técnico (p. ej. `T02` sobre una incidencia asignada a `T01`), el coordinador `C01` o cualquier solicitante reciben HTTP `403 Forbidden`.

## Reglas y proceso
1. **Inicio de atención:**
   - Verificar que el usuario en sesión sea `TECNICO` y que `incidencia.tecnico_asignado_id == session['user_id']`.
   - Verificar que `incidencia.estado == 'ASIGNADA'`.
   - En transacción SQLite: cambiar `estado` a `'EN_ATENCION'` e insertar evento `'INICIO_ATENCION'` en `historial_eventos`.
2. **Registro de solución:**
   - Verificar que el usuario en sesión sea `TECNICO` y que `incidencia.tecnico_asignado_id == session['user_id']`.
   - Verificar que `incidencia.estado == 'EN_ATENCION'` (si está en `ASIGNADA`, rechazar con HTTP 400).
   - Aplicar `solucion_limpia = solucion.strip()` y comprobar `20 <= len(solucion_limpia) <= 800`.
   - En transacción SQLite:
     - Insertar registro en tabla `soluciones` (conservando el histórico de todas las soluciones propuestas).
     - Actualizar `solucion_actual = solucion_limpia` y `estado = 'PENDIENTE_VALIDACION'` en `incidencias`.
     - Insertar evento `'REGISTRO_SOLUCION'` en `historial_eventos` incluyendo el texto de la solución, autor y fecha UTC.

## Salidas y cambios persistidos
- **Persistencia:** Estado actualizado (`EN_ATENCION` y luego `PENDIENTE_VALIDACION`), nueva fila en `soluciones` y eventos correspondientes en `historial_eventos`.
- **Salida HTTP:** Vista de detalle actualizada reflejando el nuevo estado y la solución registrada.

## Errores y efectos que deben evitarse
- **Técnico no asignado (HTTP 403):** Si `T02` intenta iniciar atención o registrar solución en un reporte de `T01`, se rechaza sin modificar estado ni historial.
- **Solución antes de iniciar atención (HTTP 400):** Si `T01` intenta enviar una solución cuando la incidencia aún está en `ASIGNADA`, se rechaza sin cambios.
- **Longitud de solución fuera de rango (HTTP 400):** Menos de 20 caracteres o más de 800 caracteres tras `strip()` se rechaza sin cambios.
- **Intento de cierre por el técnico (HTTP 403):** El técnico nunca puede pasar una incidencia a `CERRADA`.

## Criterios de aceptación (Dado / Cuando / Entonces)
- **AC-S03-01 (Inicio de atención normal por técnico asignado):** **Dada** una incidencia en estado `ASIGNADA` al técnico `T01`, **cuando** `T01` solicita iniciar la atención, **entonces** la incidencia pasa a estado `EN_ATENCION` y se guarda el evento `INICIO_ATENCION` con autor `T01` y fecha UTC.
- **AC-S03-02 (Registro de solución válida desde EN_ATENCION):** **Dada** una incidencia en estado `EN_ATENCION` asignada a `T01`, **cuando** `T01` registra una solución de 45 caracteres `"Se reemplazó el breaker térmico de 20A dañado"`, **entonces** la incidencia pasa a `PENDIENTE_VALIDACION`, guarda la solución y registra el evento `REGISTRO_SOLUCION` en el historial.
- **AC-S03-03 (Rechazo a técnico no asignado o a otros roles):** **Dada** una incidencia asignada a `T01` en estado `ASIGNADA` o `EN_ATENCION`, **cuando** el técnico `T02`, el coordinador `C01` o el solicitante `S01` intenta iniciar atención o registrar solución, **entonces** el servidor responde HTTP 403 Forbidden y conserva estado e historial sin cambios.
- **AC-S03-04 (Rechazo al registrar solución antes de iniciar atención):** **Dada** una incidencia en estado `ASIGNADA` al técnico `T01`, **cuando** `T01` intenta registrar una solución sin haber pasado antes a `EN_ATENCION`, **entonces** el servidor rechaza la operación con HTTP 400 y la incidencia permanece en `ASIGNADA`.
- **AC-S03-05 (Límites de longitud de solución: 19, 20 y 800 caracteres tras strip):** **Dada** una incidencia en `EN_ATENCION` asignada a `T01`, **cuando** `T01` envía una solución de 19 caracteres o de 801 caracteres (tras `strip()`), **entonces** el servidor responde HTTP 400 y mantiene el estado `EN_ATENCION`; y **cuando** envía exactamente 20 o 800 caracteres, **entonces** acepta la transición a `PENDIENTE_VALIDACION`.

## Diseño y tareas vinculadas a cada AC
- **Componente:** `app/services.py::iniciar_atencion()`, `app/services.py::registrar_solucion()` y rutas en `app/routes.py`.
- **Tareas:**
  - `TASK-301` (Juan Jiménez): Implementar `iniciar_atencion` y `registrar_solucion` con validación de pertenencia `tecnico_asignado_id` y límites 20..800 post-`strip()` (AC-S03-01 a AC-S03-05).
  - `TASK-302` (Juan Jiménez): Diseñar controles en vista de detalle para el técnico asignado y tabla de soluciones históricas (AC-S03-01, AC-S03-02).

## Pruebas y resultados esperados
- `test_04_atencion_tecnico_permisos_y_orden_estados`: Verifica bloqueo a `T02` (HTTP 403), bloqueo de solución en estado `ASIGNADA` (HTTP 400), rechazo de solución de 19 chars (HTTP 400), e inicio y solución válidos por `T01`.

## Decisión de revisión / versión aprobada
- **Revisión v1.0 -> v1.1 (07/10/2026 por Osvaldo Navarro):** Se verificó que cuando una incidencia vuelve a `EN_ATENCION` tras un rechazo o reapertura, el registro de una nueva solución no debe sobrescribir la fila previa en la tabla `soluciones` ni en `historial_eventos`. Se documentó en Reglas y Proceso. **Decisión:** APROBADA v1.1 para implementación.
