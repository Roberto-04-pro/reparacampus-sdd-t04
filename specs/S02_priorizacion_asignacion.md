# SPEC: S02 · Título: Asignación de Incidencias a Técnicos Activos por el Coordinador

- **Versión / autor / revisor / fecha:** v1.1 (Aprobada) / Autor: Osvaldo Navarro / Revisor: Roberto Rueda / Fecha: 06/10/2026
- **Requisito asociado:** RF02
- **Historia:** Como **coordinador de mantenimiento**, quiero **consultar las incidencias registradas con su prioridad calculada y asignar un técnico activo a cada reporte en estado `REGISTRADA`**, para **iniciar formalmente la gestión técnica cambiando el estado a `ASIGNADA` con trazabilidad en el historial**.

## Alcance y exclusiones
- **Incluye:** Verificación de rol `COORDINADOR` en sesión, validación de que la incidencia esté exactamente en estado `REGISTRADA`, comprobación de que el técnico exista, tenga rol `TECNICO` y esté activo (`activo = 1`), transición de estado a `ASIGNADA` y registro atómico del evento `ASIGNACION` en el historial.
- **Excluye:** Reasignación de una incidencia que ya esté en estado `ASIGNADA`, `EN_ATENCION`, `PENDIENTE_VALIDACION` o `CERRADA`; restricción por especialidad del técnico (explícitamente excluida en esta versión del caso); modificación manual de la prioridad calculada.

## Entradas: tipos, obligatoriedad y límites
1. `incidencia_id` (`int`, obligatorio en ruta): Identificador de una incidencia existente en estado `REGISTRADA`.
2. `tecnico_id` (`string`, obligatorio en formulario/payload): Identificador del usuario técnico tras `.strip()` (p. ej. `T01` o `T02`). Debe corresponder a un usuario existente en tabla `usuarios` con `rol = 'TECNICO'` y `activo = 1`.

## Precondiciones y permisos
- Usuario autenticado en sesión con rol `COORDINADOR` (`C01`).
- Ni `SOLICITANTE` (`S01`, `S02`) ni `TECNICO` (`T01`, `T02`) pueden ejecutar la asignación (rechazo HTTP 403).
- La incidencia debe encontrarse en estado `REGISTRADA`.

## Reglas y proceso
1. Comprobar que el usuario en sesión tenga rol `COORDINADOR`.
2. Consultar la incidencia por `incidencia_id` (si no existe, devolver HTTP 404).
3. Verificar que `incidencia.estado == 'REGISTRADA'`. Si el estado es `ASIGNADA` o cualquier otro, rechazar con HTTP 400/409 (prohibida la reasignación).
4. Consultar el usuario `tecnico_id` en la tabla `usuarios` y verificar que exista, tenga `rol == 'TECNICO'` y `activo == 1`.
5. En una transacción atómica SQLite:
   - Actualizar `incidencias` estableciendo `estado = 'ASIGNADA'` y `tecnico_asignado_id = tecnico_id`.
   - Insertar en `historial_eventos` un registro con `accion = 'ASIGNACION'`, `autor_id = C01`, `fecha_utc`, `estado_anterior = 'REGISTRADA'`, `estado_nuevo = 'ASIGNADA'` y detalle indicando el técnico asignado.

## Salidas y cambios persistidos
- **Persistencia:** Campo `estado = 'ASIGNADA'` y `tecnico_asignado_id` actualizados en `incidencias`; nuevo evento `ASIGNACION` en `historial_eventos`.
- **Salida HTTP:** Confirmación de asignación exitosa y vista actualizada de la incidencia.

## Errores y efectos que deben evitarse
- **Intento de reasignación (HTTP 400):** Si la incidencia ya está `ASIGNADA` (p. ej. a `T01`) y el coordinador intenta asignarla nuevamente a `T01` o `T02`, la operación se rechaza sin alterar el técnico ni agregar eventos al historial.
- **Técnico inexistente o inactivo (HTTP 400):** Si se envía un `tecnico_id` inexistente, de otro rol (p. ej. `S01`), o con `activo = 0`, se rechaza sin cambios.
- **Actor no autorizado (HTTP 403):** Si un solicitante o técnico intenta asignarse o asignar una incidencia, se rechaza sin cambios.

## Criterios de aceptación (Dado / Cuando / Entonces)
- **AC-S02-01 (Asignación normal exitosa):** **Dada** una incidencia en estado `REGISTRADA` y el coordinador `C01` autenticado, **cuando** `C01` la asigna al técnico activo `T01`, **entonces** la incidencia pasa a estado `ASIGNADA`, queda vinculada a `T01` y se registra el evento `ASIGNACION` en el historial con autor `C01` y fecha UTC.
- **AC-S02-02 (Prohibición de reasignación sobre incidencia ya ASIGNADA):** **Dada** una incidencia que ya se encuentra en estado `ASIGNADA` al técnico `T01`, **cuando** el coordinador `C01` intenta asignarla nuevamente a `T02` (o al mismo `T01`), **entonces** el servidor rechaza la operación con HTTP 400, conserva el estado `ASIGNADA` con `T01` y no agrega ningún evento al historial.
- **AC-S02-03 (Rechazo por permisos cuando otro rol intenta asignar):** **Dada** una incidencia en estado `REGISTRADA`, **cuando** el solicitante `S01` o el técnico `T01` intenta ejecutar la operación de asignación, **entonces** el servidor responde HTTP 403 Forbidden y la incidencia permanece en `REGISTRADA`.
- **AC-S02-04 (Rechazo al asignar a un técnico inactivo o usuario no técnico):** **Dada** una incidencia en estado `REGISTRADA`, **cuando** el coordinador `C01` intenta asignarla a un técnico con `activo = 0`, a un código inexistente `T99` o a un solicitante `S01`, **entonces** el servidor rechaza la operación con HTTP 400 y conserva el estado `REGISTRADA`.
- **AC-S02-05 (Incompatibilidad de estado en etapas posteriores):** **Dada** una incidencia en estado `EN_ATENCION`, `PENDIENTE_VALIDACION` o `CERRADA`, **cuando** el coordinador `C01` intenta asignarla, **entonces** el servidor rechaza la operación con HTTP 400 sin modificar el estado ni el historial.

## Diseño y tareas vinculadas a cada AC
- **Componente:** `app/services.py::asignar_tecnico()` y `app/routes.py::asignar_incidencia()`.
- **Tareas:**
  - `TASK-201` (Osvaldo Navarro): Implementar validación de estado `REGISTRADA`, rol `COORDINADOR` y estado `activo = 1` del técnico en `app/services.py` (AC-S02-01, AC-S02-02, AC-S02-04, AC-S02-05).
  - `TASK-202` (Juan Jiménez): Conectar selector de técnicos activos en plantilla de detalle para `COORDINADOR` y proteger endpoint `POST /incidencias/<id>/asignar` (AC-S02-01, AC-S02-03).

## Pruebas y resultados esperados
- `test_03_asignacion_correcta_y_prohibicion_reasignacion`: Comprueba transición `REGISTRADA` -> `ASIGNADA` por `C01`, rechazo de reasignación repetida, rechazo a técnico inactivo y rechazo cuando intenta asignar un rol distinto.

## Decisión de revisión / versión aprobada
- **Revisión v1.0 -> v1.1 (06/10/2026 por Roberto Rueda):** Se añadió AC-S02-04 explícito para verificar que no se pueda asignar un usuario con rol `SOLICITANTE` ni un técnico con `activo = 0`. **Decisión:** APROBADA v1.1 para implementación.
