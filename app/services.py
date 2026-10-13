from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from werkzeug.security import check_password_hash
from app.db import get_db

UBICACIONES_PERMITIDAS = ("LAB-01", "AULA-201", "BIB-01")
CATEGORIAS_PERMITIDAS = ("ELECTRICIDAD", "HIDRAULICA", "MOBILIARIO", "TIC")
IMPACTOS_PERMITIDOS = ("BAJO", "ALTO")
ESTADOS_PERMITIDOS = (
    "REGISTRADA",
    "ASIGNADA",
    "EN_ATENCION",
    "PENDIENTE_VALIDACION",
    "CERRADA",
)
PRIORIDADES_PERMITIDAS = ("CRITICA", "ALTA", "NORMAL")

class ReglaNegocioError(Exception):
    def __init__(self, mensaje: str, codigo_http: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_http = codigo_http

class PermisoDenegadoError(ReglaNegocioError):
    def __init__(self, mensaje: str = "No tiene permisos para ejecutar esta operación."):
        super().__init__(mensaje, codigo_http=403)

class RecursoNoEncontradoError(ReglaNegocioError):
    def __init__(self, mensaje: str = "La incidencia solicitada no existe."):
        super().__init__(mensaje, codigo_http=404)

def get_utc_now() -> datetime:
    """Devuelve la fecha y hora actual en UTC. Puede ser reemplazada en pruebas (monkeypatch) para verificar la ventana de 48h."""
    return datetime.now(timezone.utc)

def format_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_utc(iso_str: str) -> datetime:
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def autenticar_usuario(username: str, password: str) -> Optional[Dict[str, Any]]:
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    uname = username.strip().upper()
    db = get_db()
    row = db.execute(
        "SELECT id, username, nombre, password_hash, rol, activo FROM usuarios WHERE UPPER(username) = ? OR UPPER(id) = ?",
        (uname, uname),
    ).fetchone()
    if not row or row["activo"] != 1:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return dict(row)

def obtener_usuario_por_id(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    db = get_db()
    row = db.execute(
        "SELECT id, username, nombre, rol, activo FROM usuarios WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None

def listar_tecnicos_activos() -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT id, username, nombre FROM usuarios WHERE rol = 'TECNICO' AND activo = 1 ORDER BY id ASC"
    ).fetchall()
    return [dict(r) for r in rows]

def parsear_riesgo_booleano(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        limpio = valor.strip().lower()
        if limpio == "true":
            return True
        if limpio == "false":
            return False
    raise ReglaNegocioError("El campo 'riesgo para personas' es obligatorio y debe ser un booleano válido (true o false).", 400)

def calcular_prioridad(impacto: str, riesgo_personas: bool) -> str:
    """RF02: Con riesgo para personas -> CRITICA; sin riesgo y ALTO -> ALTA; sin riesgo y BAJO -> NORMAL."""
    if riesgo_personas:
        return "CRITICA"
    if impacto == "ALTO":
        return "ALTA"
    return "NORMAL"

def crear_incidencia(
    usuario_actual: Dict[str, Any],
    ubicacion: Any,
    categoria: Any,
    descripcion: Any,
    impacto: Any,
    riesgo_personas: Any,
) -> Dict[str, Any]:
    """RF01 y RF02: Registra incidencia por un solicitante y calcula su prioridad."""
    if not usuario_actual or usuario_actual.get("rol") != "SOLICITANTE":
        raise PermisoDenegadoError("Solo un solicitante autenticado puede registrar incidencias.")

    ubic_str =ubicacion.strip() if isinstance(ubicacion, str) else ""
    cat_str = categoria.strip() if isinstance(categoria, str) else ""
    desc_str = descripcion.strip() if isinstance(descripcion, str) else ""
    imp_str = impacto.strip() if isinstance(impacto, str) else ""

    if ubic_str not in UBICACIONES_PERMITIDAS:
        raise ReglaNegocioError(f"Ubicación inválida. Valores permitidos: {', '.join(UBICACIONES_PERMITIDAS)}.", 400)
    if cat_str not in CATEGORIAS_PERMITIDAS:
        raise ReglaNegocioError(f"Categoría inválida. Valores permitidos: {', '.join(CATEGORIAS_PERMITIDAS)}.", 400)
    if imp_str not in IMPACTOS_PERMITIDOS:
        raise ReglaNegocioError("Impacto inválido. Valores permitidos: BAJO o ALTO.", 400)

    riesgo_bool = parsear_riesgo_booleano(riesgo_personas)

    if len(desc_str) < 20 or len(desc_str) > 500:
        raise ReglaNegocioError(
            f"La descripción debe tener entre 20 y 500 caracteres tras retirar espacios externos (actual: {len(desc_str)}).",
            400,
        )

    prioridad = calcular_prioridad(imp_str, riesgo_bool)
    ahora_utc = format_utc(get_utc_now())
    db = get_db()

    with db:
        row_seq = db.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM incidencias").fetchone()
        next_num = row_seq["next_id"]
        codigo = f"INC-{next_num:04d}"

        cur = db.execute(
            """INSERT INTO incidencias (
                codigo, autor_id, ubicacion, categoria, descripcion,
                impacto, riesgo_personas, prioridad, estado, fecha_creacion_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REGISTRADA', ?)""",
            (
                codigo,
                usuario_actual["id"],
                ubic_str,
                cat_str,
                desc_str,
                imp_str,
                1 if riesgo_bool else 0,
                prioridad,
                ahora_utc,
            ),
        )
        inc_id = cur.lastrowid
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, fecha_utc
            ) VALUES (?, ?, 'CREACION', NULL, 'REGISTRADA', ?, ?)""",
            (
                inc_id,
                usuario_actual["id"],
                f"Incidencia registrada en {ubic_str} ({cat_str}) con impacto {imp_str}, riesgo={'Sí' if riesgo_bool else 'No'} y prioridad {prioridad}.",
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(inc_id)

def asignar_tecnico(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
    tecnico_id: Any,
) -> Dict[str, Any]:
    """RF02: Solo el coordinador asigna una incidencia REGISTRADA a un técnico activo y la pasa a ASIGNADA."""
    if not usuario_actual or usuario_actual.get("rol") != "COORDINADOR":
        raise PermisoDenegadoError("Solo el coordinador puede asignar un técnico a una incidencia.")

    inc = obtener_incidencia_interna(incidencia_id)
    if inc["estado"] != "REGISTRADA":
        raise ReglaNegocioError(
            f"No se puede asignar ni reasignar una incidencia en estado {inc['estado']}. Solo se permite desde REGISTRADA.",
            400,
        )

    tec_id_str = tecnico_id.strip() if isinstance(tecnico_id, str) else ""
    if not tec_id_str:
        raise ReglaNegocioError("Debe indicar un técnico activo válido.", 400)

    db = get_db()
    tec_row = db.execute(
        "SELECT id, nombre, rol, activo FROM usuarios WHERE id = ?",
        (tec_id_str,),
    ).fetchone()
    if not tec_row or tec_row["rol"] != "TECNICO" or tec_row["activo"] != 1:
        raise ReglaNegocioError("El técnico seleccionado no existe, no tiene rol TECNICO o no está activo.", 400)

    ahora_utc = format_utc(get_utc_now())
    with db:
        db.execute(
            "UPDATE incidencias SET estado = 'ASIGNADA', tecnico_asignado_id = ? WHERE id = ?",
            (tec_row["id"], incidencia_id),
        )
        db.execute(
            "INSERT INTO asignaciones (incidencia_id, coordinador_id, tecnico_id, fecha_asignacion_utc) VALUES (?, ?, ?, ?)",
            (incidencia_id, usuario_actual["id"], tec_row["id"], ahora_utc),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, fecha_utc
            ) VALUES (?, ?, 'ASIGNACION', 'REGISTRADA', 'ASIGNADA', ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                f"Asignada al técnico activo {tec_row['id']} ({tec_row['nombre']}).",
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def iniciar_atencion(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
) -> Dict[str, Any]:
    """RF03: Solo el técnico asignado pasa ASIGNADA a EN_ATENCION."""
    inc = obtener_incidencia_interna(incidencia_id)
    if (
        not usuario_actual
        or usuario_actual.get("rol") != "TECNICO"
        or inc["tecnico_asignado_id"] != usuario_actual.get("id")
    ):
        raise PermisoDenegadoError("Solo el técnico asignado a esta incidencia puede iniciar su atención.")

    if inc["estado"] != "ASIGNADA":
        raise ReglaNegocioError(
            f"Transición no permitida: para iniciar atención la incidencia debe estar en ASIGNADA (estado actual: {inc['estado']}).",
            400,
        )

    ahora_utc = format_utc(get_utc_now())
    db = get_db()
    with db:
        db.execute(
            "UPDATE incidencias SET estado = 'EN_ATENCION' WHERE id = ?",
            (incidencia_id,),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, fecha_utc
            ) VALUES (?, ?, 'INICIO_ATENCION', 'ASIGNADA', 'EN_ATENCION', ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                f"El técnico {usuario_actual['id']} inició la atención en sitio.",
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def registrar_solucion(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
    solucion: Any,
) -> Dict[str, Any]:
    """RF03: Desde EN_ATENCION el técnico asignado registra una solución de 20 a 800 caracteres y pasa a PENDIENTE_VALIDACION."""
    inc = obtener_incidencia_interna(incidencia_id)
    if (
        not usuario_actual
        or usuario_actual.get("rol") != "TECNICO"
        or inc["tecnico_asignado_id"] != usuario_actual.get("id")
    ):
        raise PermisoDenegadoError("Solo el técnico asignado puede registrar una solución para esta incidencia.")

    if inc["estado"] != "EN_ATENCION":
        raise ReglaNegocioError(
            f"No se puede registrar solución desde el estado {inc['estado']}; primero debe estar en EN_ATENCION.",
            400,
        )

    sol_str = solucion.strip() if isinstance(solucion, str) else ""
    if len(sol_str) < 20 or len(sol_str) > 800:
        raise ReglaNegocioError(
            f"La solución debe tener entre 20 y 800 caracteres tras retirar espacios externos (actual: {len(sol_str)}).",
            400,
        )

    ahora_utc = format_utc(get_utc_now())
    db = get_db()
    with db:
        db.execute(
            "UPDATE incidencias SET estado = 'PENDIENTE_VALIDACION', solucion_actual = ? WHERE id = ?",
            (sol_str, incidencia_id),
        )
        db.execute(
            "INSERT INTO soluciones (incidencia_id, tecnico_id, texto_solucion, fecha_registro_utc, estado_revision) VALUES (?, ?, ?, ?, 'PENDIENTE_VALIDACION')",
            (incidencia_id, usuario_actual["id"], sol_str, ahora_utc),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, solucion_propuesta, fecha_utc
            ) VALUES (?, ?, 'REGISTRO_SOLUCION', 'EN_ATENCION', 'PENDIENTE_VALIDACION', ?, ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                "Solución técnica registrada y enviada a validación del solicitante.",
                sol_str,
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def confirmar_solucion(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
) -> Dict[str, Any]:
    """RF04: Solo el solicitante dueño confirma una solución PENDIENTE_VALIDACION y pasa a CERRADA."""
    inc = obtener_incidencia_interna(incidencia_id)
    if (
        not usuario_actual
        or usuario_actual.get("rol") != "SOLICITANTE"
        or inc["autor_id"] != usuario_actual.get("id")
    ):
        raise PermisoDenegadoError("Solo el solicitante dueño del reporte puede confirmar la solución.")

    if inc["estado"] != "PENDIENTE_VALIDACION":
        raise ReglaNegocioError(
            f"Solo se puede confirmar una incidencia en estado PENDIENTE_VALIDACION (estado actual: {inc['estado']}).",
            400,
        )

    ahora_utc = format_utc(get_utc_now())
    db = get_db()
    with db:
        db.execute(
            "UPDATE incidencias SET estado = 'CERRADA', fecha_ultimo_cierre_utc = ? WHERE id = ?",
            (ahora_utc, incidencia_id),
        )
        db.execute(
            "UPDATE soluciones SET estado_revision = 'CONFIRMADA' WHERE id = (SELECT MAX(id) FROM soluciones WHERE incidencia_id = ?)",
            (incidencia_id,),
        )
        db.execute(
            "INSERT INTO cierres (incidencia_id, solicitante_id, fecha_cierre_utc) VALUES (?, ?, ?)",
            (incidencia_id, usuario_actual["id"], ahora_utc),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, solucion_propuesta, fecha_utc
            ) VALUES (?, ?, 'CIERRE', 'PENDIENTE_VALIDACION', 'CERRADA', ?, ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                "El solicitante dueño confirmó la solución y cerró la incidencia.",
                inc["solucion_actual"],
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def rechazar_solucion(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
    motivo: Any,
) -> Dict[str, Any]:
    """RF04: El solicitante dueño rechaza PENDIENTE_VALIDACION con motivo de 10 a 300 chars; vuelve a EN_ATENCION con el mismo técnico y conserva solución anterior."""
    inc = obtener_incidencia_interna(incidencia_id)
    if (
        not usuario_actual
        or usuario_actual.get("rol") != "SOLICITANTE"
        or inc["autor_id"] != usuario_actual.get("id")
    ):
        raise PermisoDenegadoError("Solo el solicitante dueño del reporte puede rechazar la solución.")

    if inc["estado"] != "PENDIENTE_VALIDACION":
        raise ReglaNegocioError(
            f"Solo se puede rechazar una solución cuando la incidencia está en PENDIENTE_VALIDACION (estado actual: {inc['estado']}).",
            400,
        )

    motivo_str = motivo.strip() if isinstance(motivo, str) else ""
    if len(motivo_str) < 10 or len(motivo_str) > 300:
        raise ReglaNegocioError(
            f"El motivo de rechazo debe tener entre 10 y 300 caracteres tras retirar espacios externos (actual: {len(motivo_str)}).",
            400,
        )

    ahora_utc = format_utc(get_utc_now())
    db = get_db()
    with db:
        # Conserva el mismo tecnico_asignado_id y la solucion_actual anterior
        db.execute(
            "UPDATE incidencias SET estado = 'EN_ATENCION' WHERE id = ?",
            (incidencia_id,),
        )
        db.execute(
            "UPDATE soluciones SET estado_revision = 'RECHAZADA' WHERE id = (SELECT MAX(id) FROM soluciones WHERE incidencia_id = ?)",
            (incidencia_id,),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, solucion_propuesta, motivo, fecha_utc
            ) VALUES (?, ?, 'RECHAZO_SOLUCION', 'PENDIENTE_VALIDACION', 'EN_ATENCION', ?, ?, ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                f"Solución rechazada por el solicitante dueño. Conserva técnico {inc['tecnico_asignado_id']}.",
                inc["solucion_actual"],
                motivo_str,
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def reabrir_incidencia(
    usuario_actual: Dict[str, Any],
    incidencia_id: int,
    motivo: Any,
) -> Dict[str, Any]:
    """RF04: Una incidencia CERRADA puede reabrirse por su dueño dentro de las 48h siguientes al último cierre UTC, con motivo 10..300 chars."""
    inc = obtener_incidencia_interna(incidencia_id)
    if (
        not usuario_actual
        or usuario_actual.get("rol") != "SOLICITANTE"
        or inc["autor_id"] != usuario_actual.get("id")
    ):
        raise PermisoDenegadoError("Solo el solicitante dueño del reporte puede reabrir la incidencia.")

    if inc["estado"] != "CERRADA" or not inc["fecha_ultimo_cierre_utc"]:
        raise ReglaNegocioError(
            f"Solo se puede reabrir una incidencia en estado CERRADA (estado actual: {inc['estado']}).",
            400,
        )

    motivo_str = motivo.strip() if isinstance(motivo, str) else ""
    if len(motivo_str) < 10 or len(motivo_str) > 300:
        raise ReglaNegocioError(
            f"El motivo de reapertura debe tener entre 10 y 300 caracteres tras retirar espacios externos (actual: {len(motivo_str)}).",
            400,
        )

    dt_ahora = get_utc_now()
    dt_cierre = parse_utc(inc["fecha_ultimo_cierre_utc"])
    segundos_transcurridos = (dt_ahora - dt_cierre).total_seconds()

    if segundos_transcurridos < 0 or segundos_transcurridos > 48 * 3600:
        raise ReglaNegocioError(
            "Plazo de reapertura vencido: han transcurrido más de 48 horas UTC desde el último cierre.",
            400,
        )

    ahora_utc = format_utc(dt_ahora)
    db = get_db()
    with db:
        # Vuelve a EN_ATENCION con el mismo técnico y conserva todos los cierres y soluciones anteriores
        db.execute(
            "UPDATE incidencias SET estado = 'EN_ATENCION' WHERE id = ?",
            (incidencia_id,),
        )
        db.execute(
            """INSERT INTO historial_eventos (
                incidencia_id, autor_id, accion, estado_anterior, estado_nuevo, detalle, solucion_propuesta, motivo, fecha_utc
            ) VALUES (?, ?, 'REAPERTURA', 'CERRADA', 'EN_ATENCION', ?, ?, ?, ?)""",
            (
                incidencia_id,
                usuario_actual["id"],
                f"Incidencia reabierta dentro de las 48h UTC con el mismo técnico {inc['tecnico_asignado_id']}.",
                inc["solucion_actual"],
                motivo_str,
                ahora_utc,
            ),
        )

    return obtener_incidencia_interna(incidencia_id)

def obtener_incidencia_interna(incidencia_id: int) -> Dict[str, Any]:
    db = get_db()
    row = db.execute(
        """SELECT i.*,
                  u_aut.nombre AS autor_nombre,
                  u_tec.nombre AS tecnico_nombre
           FROM incidencias i
           JOIN usuarios u_aut ON u_aut.id = i.autor_id
           LEFT JOIN usuarios u_tec ON u_tec.id = i.tecnico_asignado_id
           WHERE i.id = ?""",
        (incidencia_id,),
    ).fetchone()
    if not row:
        raise RecursoNoEncontradoError()
    inc = dict(row)
    inc["riesgo_personas"] = bool(inc["riesgo_personas"])

    eventos = db.execute(
        """SELECT h.*, u.nombre AS autor_nombre, u.rol AS autor_rol
           FROM historial_eventos h
           JOIN usuarios u ON u.id = h.autor_id
           WHERE h.incidencia_id = ?
           ORDER BY h.id ASC""",
        (incidencia_id,),
    ).fetchall()
    inc["historial"] = [dict(e) for e in eventos]

    soluciones = db.execute(
        """SELECT s.*, u.nombre AS tecnico_nombre
           FROM soluciones s
           JOIN usuarios u ON u.id = s.tecnico_id
           WHERE s.incidencia_id = ?
           ORDER BY s.id ASC""",
        (incidencia_id,),
    ).fetchall()
    inc["soluciones"] = [dict(s) for s in soluciones]

    cierres = db.execute(
        """SELECT c.*, u.nombre AS solicitante_nombre
           FROM cierres c
           JOIN usuarios u ON u.id = c.solicitante_id
           WHERE c.incidencia_id = ?
           ORDER BY c.id ASC""",
        (incidencia_id,),
    ).fetchall()
    inc["cierres"] = [dict(c) for c in cierres]
    return inc

def obtener_incidencia_para_usuario(usuario_actual: Dict[str, Any], incidencia_id: int) -> Dict[str, Any]:
    """RF05: Comprueba permisos de lectura sobre la incidencia antes de devolverla."""
    if not usuario_actual:
        raise PermisoDenegadoError("Sesión no iniciada.")
    inc = obtener_incidencia_interna(incidencia_id)
    rol = usuario_actual["rol"]
    uid = usuario_actual["id"]
    if rol == "SOLICITANTE" and inc["autor_id"] != uid:
        raise PermisoDenegadoError("Un solicitante solo puede consultar sus propias incidencias.")
    if rol == "TECNICO" and inc["tecnico_asignado_id"] != uid:
        raise PermisoDenegadoError("Un técnico solo puede consultar las incidencias asignadas a su cuenta.")
    return inc

def listar_incidencias(
    usuario_actual: Dict[str, Any],
    filtro_estado: Optional[str] = None,
    filtro_prioridad: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """RF05: Lista incidencias según permisos del actor en sesión con filtros opcionales por estado y prioridad."""
    if not usuario_actual:
        raise PermisoDenegadoError("Sesión no iniciada.")

    condiciones = []
    params: List[Any] = []
    rol = usuario_actual["rol"]
    uid = usuario_actual["id"]

    if rol == "SOLICITANTE":
        condiciones.append("i.autor_id = ?")
        params.append(uid)
    elif rol == "TECNICO":
        condiciones.append("i.tecnico_asignado_id = ?")
        params.append(uid)
    elif rol != "COORDINADOR":
        raise PermisoDenegadoError("Rol desconocido.")

    if filtro_estado and filtro_estado.strip():
        est = filtro_estado.strip()
        if est not in ESTADOS_PERMITIDOS:
            raise ReglaNegocioError(f"Filtro de estado inválido: {est}", 400)
        condiciones.append("i.estado = ?")
        params.append(est)

    if filtro_prioridad and filtro_prioridad.strip():
        prio = filtro_prioridad.strip()
        if prio not in PRIORIDADES_PERMITIDAS:
            raise ReglaNegocioError(f"Filtro de prioridad inválido: {prio}", 400)
        condiciones.append("i.prioridad = ?")
        params.append(prio)

    where_sql = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    db = get_db()
    rows = db.execute(
        f"""SELECT i.*,
                   u_aut.nombre AS autor_nombre,
                   u_tec.nombre AS tecnico_nombre
            FROM incidencias i
            JOIN usuarios u_aut ON u_aut.id = i.autor_id
            LEFT JOIN usuarios u_tec ON u_tec.id = i.tecnico_asignado_id
            {where_sql}
            ORDER BY i.id DESC""",
        tuple(params),
    ).fetchall()
    resultado = []
    for r in rows:
        d = dict(r)
        d["riesgo_personas"] = bool(d["riesgo_personas"])
        resultado.append(d)
    return resultado

def obtener_metricas_tablero(usuario_actual: Dict[str, Any]) -> Dict[str, Any]:
    """RF05: Tablero del coordinador con cantidades por estado y prioridad, CRITICA no cerradas y porcentaje de cierre."""
    if not usuario_actual or usuario_actual.get("rol") != "COORDINADOR":
        raise PermisoDenegadoError("Solo el coordinador puede acceder al tablero de control.")

    db = get_db()
    por_estado = {est: 0 for est in ESTADOS_PERMITIDOS}
    for row in db.execute("SELECT estado, COUNT(*) AS cnt FROM incidencias GROUP BY estado").fetchall():
        por_estado[row["estado"]] = row["cnt"]

    por_prioridad = {prio: 0 for prio in PRIORIDADES_PERMITIDAS}
    for row in db.execute("SELECT prioridad, COUNT(*) AS cnt FROM incidencias GROUP BY prioridad").fetchall():
        por_prioridad[row["prioridad"]] = row["cnt"]

    total = sum(por_estado.values())
    cerradas = por_estado["CERRADA"]
    if total == 0:
        porcentaje_num = 0.0
        porcentaje_str = "0,0 %"
    else:
        porcentaje_num = round((cerradas / total) * 100.0, 1)
        porcentaje_str = f"{porcentaje_num:.1f}".replace(".", ",") + " %"

    criticas_no_cerradas_rows = db.execute(
        """SELECT i.*, u_aut.nombre AS autor_nombre, u_tec.nombre AS tecnico_nombre
           FROM incidencias i
           JOIN usuarios u_aut ON u_aut.id = i.autor_id
           LEFT JOIN usuarios u_tec ON u_tec.id = i.tecnico_asignado_id
           WHERE i.prioridad = 'CRITICA' AND i.estado != 'CERRADA'
           ORDER BY i.id ASC"""
    ).fetchall()
    criticas_no_cerradas = [dict(r) for r in criticas_no_cerradas_rows]

    return {
        "total": total,
        "cerradas": cerradas,
        "por_estado": por_estado,
        "por_prioridad": por_prioridad,
        "criticas_no_cerradas_cantidad": len(criticas_no_cerradas),
        "criticas_no_cerradas": criticas_no_cerradas,
        "porcentaje_cierre_num": porcentaje_num,
        "porcentaje_cierre": porcentaje_str,
    }
