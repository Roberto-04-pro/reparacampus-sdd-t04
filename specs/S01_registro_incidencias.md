# SPEC: S01 · Título: Registro de Incidencias y Cálculo Automático de Prioridad

- **Versión / autor / revisor / fecha:** v1.1 (Aprobada) / Autor: Osvaldo Navarro / Revisor: Juan Jiménez / Fecha: 06/10/2026
- **Requisito asociado:** RF01 (y cálculo inicial de prioridad de RF02)
- **Historia:** Como **solicitante**, quiero **registrar una incidencia de infraestructura indicando ubicación, categoría, descripción, impacto y riesgo para personas**, para **dejar constancia formal del daño con código único, estado inicial `REGISTRADA` y prioridad calculada automáticamente por el sistema**.

## Alcance y exclusiones
- **Incluye:** Validación en servidor de los cinco campos obligatorios, limpieza de espacios externos (`strip()`), generación automática de código único (`INC-XXXX`), asignación del autor desde la sesión activa, fecha/hora UTC, estado inicial `REGISTRADA`, cálculo determinista de prioridad (`CRITICA`, `ALTA`, `NORMAL`) y registro atómico del evento `CREACION` en el historial.
- **Excluye:** Adjuntos multimedia (fotos/videos), edición posterior del reporte creado, selección manual de la prioridad por parte del usuario o selección de autor mediante campo de formulario.

## Entradas: tipos, obligatoriedad y límites
Todos los campos son **obligatorios** y se procesan tras retirar espacios externos (`strip()`):
1. `ubicacion` (`string`, obligatorio): Debe pertenecer exactamente al catálogo `{'LAB-01', 'AULA-201', 'BIB-01'}`.
2. `categoria` (`string`, obligatorio): Debe pertenecer exactamente al catálogo `{'ELECTRICIDAD', 'HIDRAULICA', 'MOBILIARIO', 'TIC'}`.
3. `descripcion` (`string`, obligatorio): Longitud entre **20 y 500 caracteres** inclusive después de `strip()`. No se ejecuta como HTML ni scripts.
4. `impacto` (`string`, obligatorio): Valores permitidos `{'BAJO', 'ALTO'}`. Cualquier otro valor se rechaza.
5. `riesgo_personas` (`boolean` / `string` booleano estricto, obligatorio): Solo se aceptan valores booleanos explícitos (`True`/`False` o `'true'`/`'false'`). Valores vacíos, nulos o ambiguos se rechazan.

## Precondiciones y permisos
- El usuario debe tener sesión autenticada activa en el servidor.
- El rol del usuario en sesión debe ser exclusivamente `SOLICITANTE` (`S01` o `S02`). Si un `COORDINADOR` (`C01`) o `TECNICO` (`T01`, `T02`) intenta invocar el registro, el servidor rechaza la operación con código HTTP `403 Forbidden`.

## Reglas y proceso
1. Verificar sesión activa y rol `SOLICITANTE`.
2. Aplicar `.strip()` a los campos de texto recibidos.
3. Validar pertenencia de `ubicacion` y `categoria` a las listas permitidas.
4. Validar que `20 <= len(descripcion.strip()) <= 500`.
5. Validar que `impacto` sea `'BAJO'` o `'ALTO'` y que `riesgo_personas` sea booleano válido.
6. Calcular la prioridad según `RF02`:
   - Si `riesgo_personas == True` -> `prioridad = 'CRITICA'`
   - Si `riesgo_personas == False` e `impacto == 'ALTO'` -> `prioridad = 'ALTA'`
   - Si `riesgo_personas == False` e `impacto == 'BAJO'` -> `prioridad = 'NORMAL'`
7. En una única transacción SQLite:
   - Insertar la incidencia con estado `'REGISTRADA'`, `autor_id = session['user_id']`, `fecha_creacion = utc_now()` y `codigo` correlativo (`INC-0001`, `INC-0002`, ...).
   - Insertar en `historial_eventos` el evento `CREACION` con `estado_anterior = NULL`, `estado_nuevo = 'REGISTRADA'`, `autor_id`, `fecha_utc` y detalle.

## Salidas y cambios persistidos
- **Persistencia:** Nuevo registro en tabla `incidencias` y nuevo registro en tabla `historial_eventos` guardados atómicamente.
- **Salida HTTP:** Redirección al detalle de la incidencia creada (o respuesta `201 Created` / `200 OK` con confirmación visual del código generado, estado `REGISTRADA` y prioridad asignada).

## Errores y efectos que deben evitarse
- **Datos o límites inválidos (HTTP 400):** Si la descripción tiene 19 caracteres o 501 caracteres (tras `strip()`), o si `ubicacion`, `categoria`, `impacto` o `riesgo_personas` tienen valores fuera de catálogo, se rechaza la solicitud sin insertar filas en `incidencias` ni en `historial_eventos`.
- **Permisos insuficientes (HTTP 403):** Coordinador o técnico no pueden crear incidencias.
- **Inyección HTML/XSS:** Textos con etiquetas como `<script>alert(1)</script>` se almacenan como texto plano y se escapan al renderizar.

## Criterios de aceptación (Dado / Cuando / Entonces)
- **AC-S01-01 (Funcionamiento normal y cálculo de prioridad CRITICA):** **Dado** un solicitante autenticado (`S01`), **cuando** envía un reporte con ubicación `LAB-01`, categoría `ELECTRICIDAD`, descripción de 35 caracteres `"Cortocircuito en toma corriente sur"`, impacto `BAJO` y `riesgo_personas = true`, **entonces** el sistema crea la incidencia con código único, autor `S01`, estado `REGISTRADA`, prioridad `CRITICA` y registra el evento `CREACION` en el historial con fecha UTC.
- **AC-S01-02 (Cálculo de prioridad ALTA y NORMAL sin riesgo):** **Dado** un solicitante autenticado (`S01`), **cuando** registra una incidencia válida con `riesgo_personas = false` e impacto `ALTO`, **entonces** el sistema le asigna prioridad `ALTA`; y **cuando** registra otra con `riesgo_personas = false` e impacto `BAJO`, **entonces** le asigna prioridad `NORMAL`.
- **AC-S01-03 (Límites de longitud de descripción: 19, 20 y 500 caracteres tras strip):** **Dado** un solicitante autenticado (`S01`), **cuando** envía una descripción que tras retirar espacios externos tiene 19 caracteres (`"   Fuga de agua en lab   "` -> 19 chars) o 501 caracteres, **entonces** el servidor rechaza la operación con HTTP 400 sin crear registros; pero **cuando** tiene exactamente 20 caracteres o 500 caracteres tras `strip()`, **entonces** acepta y persiste la incidencia.
- **AC-S01-04 (Datos inválidos en impacto, riesgo, ubicación o categoría):** **Dado** un solicitante autenticado (`S01`), **cuando** envía un impacto `'MEDIO'`, un riesgo `'talvez'`, una ubicación `'CAFETERIA'` o una categoría `'PINTURA'`, **entonces** el servidor rechaza la solicitud con HTTP 400 y conserva la base de datos sin cambios.
- **AC-S01-05 (Restricción de permisos por rol):** **Dado** un usuario autenticado con rol `COORDINADOR` (`C01`) o `TECNICO` (`T01`), **cuando** intenta enviar una petición `POST /incidencias/nueva`, **entonces** el servidor responde HTTP 403 Forbidden y no crea ninguna incidencia.
- **AC-S01-06 (Neutralización de HTML/scripts en descripción):** **Dado** un solicitante autenticado (`S02`), **cuando** registra una descripción válida que contiene `<script>alert('xss')</script> Daño en proyector del aula`, **entonces** el sistema guarda el texto sin ejecutarlo y en las vistas HTML aparece escapado (`&lt;script&gt;...`).

## Diseño y tareas vinculadas a cada AC
- **Componente:** `app/services.py::crear_incidencia()` y `app/routes.py::nueva_incidencia()`.
- **Tareas:**
  - `TASK-101` (Osvaldo Navarro): Implementar `calcular_prioridad(impacto, riesgo_personas)` y validadores de dominio en `app/services.py` (AC-S01-01, AC-S01-02, AC-S01-03, AC-S01-04).
  - `TASK-102` (Osvaldo Navarro): Implementar inserción transaccional en `incidencias` e `historial_eventos` y ruta protegida por rol `SOLICITANTE` (AC-S01-01, AC-S01-05, AC-S01-06).

## Pruebas y resultados esperados
- `test_01_registro_valido_y_prioridades`: Verifica creación con prioridad `CRITICA` (`riesgo=true`), `ALTA` (`riesgo=false, impacto=ALTO`) y `NORMAL` (`riesgo=false, impacto=BAJO`), más longitud exacta de 20 caracteres.
- `test_02_registro_limites_y_valores_invalidos`: Verifica rechazo HTTP 400 con descripción de 19 caracteres, 501 caracteres, impacto inválido y riesgo inválido, comprobando 0 filas creadas.
- `test_10_seguridad_xss_y_persistencia_reinicio`: Verifica que etiquetas `<script>` se escapen correctamente.

## Decisión de revisión / versión aprobada
- **Revisión v1.0 -> v1.1 (06/10/2026 por Juan Jiménez):** En la versión v1.0 no se especificaba explícitamente que el conteo de 20 a 500 caracteres debía realizarse después de `.strip()`. Se ajustó AC-S01-03 para exigir validación post-`strip()`. **Decisión:** APROBADA v1.1 para implementación.
