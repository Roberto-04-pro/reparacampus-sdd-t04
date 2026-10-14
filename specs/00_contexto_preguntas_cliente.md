# Contexto del Caso ReparaCampus, Preguntas al Cliente y Supuestos

**Universidad Simón Bolívar · Ingeniería de Sistemas · Ingeniería de Software I (Grupo T04)**  
**Equipo:** InfraCore (Osvaldo Navarro, Juan Jiménez, Roberto Rueda)  
**Docente:** Adriana María Iglesias Solano  
**Fecha de levantamiento:** 05/10/2026  

## 1. Necesidad, Actores y Alcance
La Coordinación de Mantenimiento de la Universidad Simón Bolívar enfrenta desorganización en la gestión de daños de infraestructura física y tecnológica: los reportes ingresan por canales informales (mensajes sueltos), se atienden por otros medios sin trazabilidad y en ocasiones se dan por cerrados sin confirmar con el solicitante si el daño quedó efectivamente resuelto.

**ReparaCampus** es un prototipo web con lógica en servidor (Python + Flask) y persistencia transaccional (SQLite) que centraliza el ciclo de vida completo de una incidencia: registro con cálculo automático de prioridad, asignación controlada a técnicos activos, atención y registro de solución, validación o reapertura por parte del solicitante dueño dentro de una ventana de 48 horas UTC, e historial inmutable con tablero de control para el coordinador.

### Actores y Permisos en Servidor
| Actor | Cuentas Ficticias | Responsabilidades y Permisos Verificados en Servidor |
| :--- | :--- | :--- |
| **Solicitante** | `S01` (Dra. Ana Gómez), `S02` (Ing. Carlos Pérez) | Registra nuevas incidencias (`RF01`), consulta únicamente sus propios reportes (`RF05`) y confirma, rechaza o reabre (<= 48 h UTC) la solución de los reportes de los cuales es dueño (`RF04`). |
| **Coordinador** | `C01` (Ing. Laura Martínez) | Consulta la totalidad de las incidencias con filtros, visualiza el tablero de indicadores (`RF05`) y asigna incidencias en estado `REGISTRADA` a un técnico activo (`RF02`). No confirma ni reabre en nombre del solicitante. |
| **Técnico** | `T01` (Téc. Miguel Torres), `T02` (Téc. Jorge Ramírez) | Consulta únicamente las incidencias asignadas a su cuenta (`RF05`), inicia la atención (`ASIGNADA` -> `EN_ATENCION`) y registra la solución técnica (`EN_ATENCION` -> `PENDIENTE_VALIDACION`) (`RF03`). |

## 2. Tres Preguntas Útiles al Cliente y Supuestos Pendientes
> *Nota metodológica SDD:* Una respuesta generada por IA no constituye una decisión del cliente. Las siguientes preguntas se formularon para la Coordinación de Mantenimiento y se documentan junto con los supuestos operativos adoptados para el prototipo dentro de las reglas del enunciado.

1. **Pregunta 1 (Gestión de ausencias o incapacidad sobrevenida de un técnico asignado):**  
   *¿Qué procedimiento operativo debe seguir la Coordinación si un técnico con una incidencia en estado `ASIGNADA` o `EN_ATENCION` sufre una incapacidad médica o retiro laboral, dado que en la versión actual no se permite reasignar incidencias ya asignadas?*  
   - **Estado:** Pendiente de decisión del cliente para versión v2.0.  
   - **Supuesto adoptado en el prototipo (v1.0):** Se respeta estrictamente la regla inmutable del caso: *no existe reasignación de una incidencia ya `ASIGNADA`* ni en estados posteriores. Cualquier intento de reasignación en servidor se rechaza con HTTP 400/409 conservando estado e historial.

2. **Pregunta 2 (Límite en el número de ciclos de rechazo o reapertura por incidencia):**  
   *¿Existe un número máximo de veces que un solicitante puede rechazar una propuesta de solución o reabrir una incidencia dentro de las 48 horas posteriores a cada cierre antes de escalar el caso a una revisión presencial conjunta?*  
   - **Estado:** Pendiente de validación con la Coordinación de Mantenimiento.  
   - **Supuesto adoptado en el prototipo (v1.0):** Mientras se cumplan las reglas de negocio (estado `PENDIENTE_VALIDACION` para rechazo, o estado `CERRADA` con `tiempo_transcurrido_utc <= 48 horas` para reapertura, y motivo de 10 a 300 caracteres tras `strip()`), el sistema permite múltiples iteraciones conservando en la base de datos absolutamente todas las soluciones, motivos y cierres anteriores sin sobrescribir el historial.

3. **Pregunta 3 (Detección de reportes duplicados sobre la misma ubicación y categoría):**  
   *Cuando dos solicitantes distintos (p. ej. `S01` y `S02`) reportan el mismo daño físico en `LAB-01` y categoría `ELECTRICIDAD` con pocos minutos de diferencia, ¿debe el sistema permitir ambos registros independientes o advertir al segundo solicitante?*  
   - **Estado:** Pendiente de definición con el cliente.  
   - **Supuesto adoptado en el prototipo (v1.0):** Debido a la regla de privacidad que impide a un solicitante leer reportes de otros solicitantes (`RF05`), cada reporte válido genera su propio código secuencial (`INC-0001`, `INC-0002`, etc.) de forma independiente. 
