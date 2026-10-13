# SPEC: S05 · Título: Consulta Filtrada por Permisos, Historial Inmutable y Tablero del Coordinador

- **Versión / autor / revisor / fecha:** v1.1 (Aprobada) / Autor: Roberto Rueda / Revisor: Osvaldo Navarro / Fecha: 07/10/2026
- **Requisito asociado:** RF05
- **Historia:** Como **actor autenticado del sistema (solicitante, técnico o coordinador)**, quiero **consultar las incidencias según mis permisos aplicando filtros por estado y prioridad, revisar el historial inmutable de cada reporte y, como coordinador, visualizar el tablero de métricas**, para **hacer seguimiento transparente al estado de la infraestructura y al porcentaje de cumplimiento**.

## Alcance y exclusiones
- **Incluye:** Listado de incidencias filtrado en servidor según el rol en sesión (`SOLICITANTE`: solo propias; `TECNICO`: solo asignadas a él; `COORDINADOR`: todas); filtros combinables por `estado` y `prioridad`; vista de detalle con historial cronológico inmutable (creación, asignación, inicios de atención, soluciones, rechazos, cierres y reaperturas) sin opción de edición ni borrado; tablero exclusivo del coordinador con conteos por estado, conteos por prioridad, listado/cantidad de incidencias `CRITICA` no cerradas y porcentaje de cierre `CERRADAS / total * 100` con un decimal (`0,0 %` cuando hay cero registros).
- **Excluye:** Edición o eliminación de eventos del historial o de incidencias; exportación a formatos externos; acceso de solicitantes o técnicos al tablero del coordinador.

## Entradas: tipos, obligatoriedad y límites
1. **Consulta de listado (`GET /incidencias`):**
   - `estado` (`string`, opcional en query string): Si se envía no vacío, debe ser uno de `{'REGISTRADA', 'ASIGNADA', 'EN_ATENCION', 'PENDIENTE_VALIDACION', 'CERRADA'}`.
   - `prioridad` (`string`, opcional en query string): Si se envía no vacío, debe ser uno de `{'CRITICA', 'ALTA', 'NORMAL'}`.
2. **Consulta de detalle e historial (`GET /incidencias/<id>`):**
   - `incidencia_id` (`int`, obligatorio en ruta).
3. **Tablero del coordinador (`GET /tablero`):**
   - Sin parámetros de entrada; requiere sesión activa con rol `COORDINADOR`.

## Precondiciones y permisos
- Todo acceso requiere sesión autenticada (usuarios no autenticados son redirigidos a `/login`).
- En `GET /incidencias/<id>`:
  - Si `rol == 'SOLICITANTE'` y `incidencia.autor_id != user_id` -> HTTP `403 Forbidden`.
  - Si `rol == 'TECNICO'` y `incidencia.tecnico_asignado_id != user_id` -> HTTP `403 Forbidden`.
  - Si `rol == 'COORDINADOR'` -> acceso permitido a cualquier incidencia.
- En `GET /tablero`:
  - Solo `rol == 'COORDINADOR'`; para `SOLICITANTE` o `TECNICO` devuelve HTTP `403 Forbidden`.

## Reglas y proceso
1. **Filtrado de listado:** Construir consulta SQL parametrizada restringiendo primero por el alcance del rol (`autor_id = ?` para solicitante, `tecnico_asignado_id = ?` para técnico, sin restricción de propietario para coordinador) y aplicando condiciones adicionales si `estado` y/o `prioridad` están presentes.
2. **Inmutabilidad del historial:** El módulo de datos no expone ninguna operación `UPDATE` ni `DELETE` sobre `historial_eventos`, `soluciones` ni `cierres`. Toda operación rechazada hace `ROLLBACK` conservando intactos el estado y el historial.
3. **Cálculo del tablero del coordinador:**
   - Contar incidencias agrupadas por los 5 estados (`REGISTRADA`, `ASIGNADA`, `EN_ATENCION`, `PENDIENTE_VALIDACION`, `CERRADA`).
   - Contar incidencias agrupadas por las 3 prioridades (`CRITICA`, `ALTA`, `NORMAL`).
   - Obtener todas las incidencias donde `prioridad = 'CRITICA'` y `estado != 'CERRADA'` (incidencias críticas no cerradas).
   - Calcular porcentaje de cierre:
     - Si `total == 0`: `porcentaje_cierre = "0,0 %"` (valor numérico `0.0`).
     - Si `total > 0`: `valor = round((cerradas / total) * 100, 1)`, formateado con coma decimal y un dígito (`f"{valor:.1f}".replace(".", ",") + " %"`).
     - Si una incidencia `CERRADA` se reabre, pasa a `EN_ATENCION`, por lo que `cerradas` disminuye en 1, reduciendo el porcentaje de cierre mientras conserva el registro del cierre anterior en el historial.

## Salidas y cambios persistidos
- **Lectura sin efectos laterales:** Las consultas no alteran el estado ni agregan eventos.
- **Salida HTTP:** Renderizado HTML con tablas filtradas, línea de tiempo del historial y tarjetas/tablas del tablero del coordinador.

## Errores y efectos que deben evitarse
- **Fuga de información entre solicitantes o técnicos (HTTP 403):** Ocultar enlaces en la interfaz no basta; el servidor bloquea la lectura directa por ID (`/incidencias/<id>`) si el reporte no pertenece al solicitante o no está asignado al técnico.
- **División por cero en tablero:** Con base de datos vacía (`total = 0`), el tablero no debe fallar con `ZeroDivisionError`; debe mostrar exactamente `0,0 %`.

## Criterios de aceptación (Dado / Cuando / Entonces)
- **AC-S05-01 (Aislamiento de consulta por rol y filtros de estado/prioridad):** **Dadas** incidencias registradas por `S01` y `S02` con distintas prioridades y estados, **cuando** `S01` consulta el listado o filtra por estado y prioridad, **entonces** solo recibe sus propios reportes; **cuando** `T01` consulta, solo recibe los asignados a `T01`; y **cuando** `C01` consulta, visualiza todos los reportes que cumplen el filtro.
- **AC-S05-02 (Bloqueo en servidor ante lectura de reporte ajeno):** **Dada** una incidencia creada por `S01`, **cuando** el solicitante `S02` (o un técnico no asignado `T02`) intenta acceder a `GET /incidencias/<id>`, **entonces** el servidor responde HTTP 403 Forbidden.
- **AC-S05-03 (Integridad e inmutabilidad del historial ante operaciones exitosas y fallidas):** **Dada** una incidencia que recorre varios estados y sufre además un intento de transición inválida, **cuando** se consulta su historial, **entonces** contiene en orden cronológico cada evento exitoso con autor, fecha UTC, estado anterior, estado nuevo, soluciones, motivos, cierres y reaperturas, sin incluir rastros de la operación fallida ni permitir edición o borrado.
- **AC-S05-04 (Tablero del coordinador con cero registros muestra 0,0 %):** **Dada** la base de datos sin incidencias (`total = 0`), **cuando** el coordinador `C01` consulta el tablero, **entonces** el sistema muestra todas las cantidades en `0` y el porcentaje de cierre en `0,0 %`.
- **AC-S05-05 (Tablero con 1 cerrada de 4 muestra 25,0 % y reduce al reabrir):** **Dadas** 4 incidencias registradas donde 1 está en estado `CERRADA` y 2 son `CRITICA` no cerradas, **cuando** el coordinador `C01` consulta el tablero, **entonces** visualiza porcentaje de cierre `25,0 %` y las 2 críticas no cerradas; y **cuando** el solicitante dueño reabre la incidencia cerrada dentro de las 48h, **entonces** el porcentaje en el tablero se reduce a `0,0 %` y el historial conserva el cierre anterior.

## Diseño y tareas vinculadas a cada AC
- **Componente:** `app/services.py::listar_incidencias()`, `obtener_incidencia_para_usuario()`, `obtener_metricas_tablero()` y vistas en `app/routes.py`.
- **Tareas:**
  - `TASK-501` (Roberto Rueda): Implementar filtrado por rol, estado y prioridad en `listar_incidencias` y control de acceso en `obtener_incidencia_para_usuario` (AC-S05-01, AC-S05-02).
  - `TASK-502` (Roberto Rueda): Implementar `obtener_metricas_tablero` con formato `0,0 %` / `25,0 %` y vista `tablero.html` exclusiva para `COORDINADOR` (AC-S05-03, AC-S05-04, AC-S05-05).

## Pruebas y resultados esperados
- `test_08_filtros_visibilidad_por_rol_e_inmutabilidad_historial`: Verifica filtros por estado/prioridad, aislamiento entre `S01`, `S02`, `T01`, `C01` y conservación intacta del historial tras errores.
- `test_09_tablero_coordinador_vacio_25_porciento_y_reapertura`: Verifica tablero vacío (`0,0 %`), 1 cerrada de 4 (`25,0 %`), conteo de `CRITICA` no cerradas y reducción a `0,0 %` tras reabrir conservando el cierre anterior.

## Decisión de revisión / versión aprobada
- **Revisión v1.0 -> v1.1 (07/10/2026 por Osvaldo Navarro):** Se precisó en AC-S05-04 y AC-S05-05 que el formato del porcentaje debe incluir un decimal con coma (`0,0 %`, `25,0 %`) tal como lo exige literalmente el enunciado en RF05. **Decisión:** APROBADA v1.1 para implementación.
