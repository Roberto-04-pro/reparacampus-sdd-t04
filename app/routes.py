from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from app.db import CUENTAS_FICTICIAS
from app.services import (
    CATEGORIAS_PERMITIDAS,
    ESTADOS_PERMITIDOS,
    IMPACTOS_PERMITIDOS,
    PRIORIDADES_PERMITIDAS,
    UBICACIONES_PERMITIDAS,
    PermisoDenegadoError,
    RecursoNoEncontradoError,
    ReglaNegocioError,
    asignar_tecnico,
    autenticar_usuario,
    confirmar_solucion,
    crear_incidencia,
    iniciar_atencion,
    listar_incidencias,
    listar_tecnicos_activos,
    obtener_incidencia_para_usuario,
    obtener_metricas_tablero,
    obtener_usuario_por_id,
    reabrir_incidencia,
    rechazar_solucion,
    registrar_solucion,
)

bp = Blueprint("main", __name__)

def usuario_en_sesion():
    uid = session.get("user_id")
    if not uid:
        return None
    return obtener_usuario_por_id(uid)

@bp.route("/", methods=["GET"])
def index():
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    return redirect(url_for("main.listado_incidencias"))

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = autenticar_usuario(username, password)
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["rol"] = user["rol"]
            session["nombre"] = user["nombre"]
            flash(f"Bienvenido(a), {user['nombre']} [{user['rol']}].", "success")
            return redirect(url_for("main.listado_incidencias"))
        flash("Credenciales inválidas o cuenta inactiva.", "error")
        return render_template("login.html", cuentas=CUENTAS_FICTICIAS), 401
    return render_template("login.html", cuentas=CUENTAS_FICTICIAS)

@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("main.login"))

@bp.route("/incidencias", methods=["GET"])
def listado_incidencias():
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    filtro_estado = request.args.get("estado", "").strip()
    filtro_prioridad = request.args.get("prioridad", "").strip()
    try:
        incidencias = listar_incidencias(
            user,
            filtro_estado=filtro_estado or None,
            filtro_prioridad=filtro_prioridad or None,
        )
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return render_template(
            "incidencias.html",
            user=user,
            incidencias=[],
            estados=ESTADOS_PERMITIDOS,
            prioridades=PRIORIDADES_PERMITIDAS,
            filtro_estado=filtro_estado,
            filtro_prioridad=filtro_prioridad,
        ), e.codigo_http

    return render_template(
        "incidencias.html",
        user=user,
        incidencias=incidencias,
        estados=ESTADOS_PERMITIDOS,
        prioridades=PRIORIDADES_PERMITIDAS,
        filtro_estado=filtro_estado,
        filtro_prioridad=filtro_prioridad,
    )

@bp.route("/incidencias/nueva", methods=["GET", "POST"])
def nueva_incidencia():
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    if user["rol"] != "SOLICITANTE":
        abort(403, "Solo los solicitantes pueden registrar incidencias.")

    if request.method == "POST":
        ubicacion = request.form.get("ubicacion", "")
        categoria = request.form.get("categoria", "")
        descripcion = request.form.get("descripcion", "")
        impacto = request.form.get("impacto", "")
        riesgo_personas = request.form.get("riesgo_personas", "")
        try:
            inc = crear_incidencia(
                user,
                ubicacion=ubicacion,
                categoria=categoria,
                descripcion=descripcion,
                impacto=impacto,
                riesgo_personas=riesgo_personas,
            )
            flash(f"Incidencia {inc['codigo']} registrada exitosamente con prioridad {inc['prioridad']}.", "success")
            return redirect(url_for("main.detalle_incidencia", incidencia_id=inc["id"]))
        except ReglaNegocioError as e:
            flash(e.mensaje, "error")
            return render_template(
                "nueva_incidencia.html",
                user=user,
                ubicaciones=UBICACIONES_PERMITIDAS,
                categorias=CATEGORIAS_PERMITIDAS,
                impactos=IMPACTOS_PERMITIDOS,
                form_data=request.form,
            ), e.codigo_http

    return render_template(
        "nueva_incidencia.html",
        user=user,
        ubicaciones=UBICACIONES_PERMITIDAS,
        categorias=CATEGORIAS_PERMITIDAS,
        impactos=IMPACTOS_PERMITIDOS,
        form_data={},
    )

@bp.route("/incidencias/<int:incidencia_id>", methods=["GET"])
def detalle_incidencia(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    try:
        inc = obtener_incidencia_para_usuario(user, incidencia_id)
    except (PermisoDenegadoError, RecursoNoEncontradoError, ReglaNegocioError) as e:
        abort(e.codigo_http, e.mensaje)

    tecnicos = listar_tecnicos_activos() if user["rol"] == "COORDINADOR" else []
    return render_template(
        "detalle_incidencia.html",
        user=user,
        inc=inc,
        tecnicos=tecnicos,
    )

@bp.route("/incidencias/<int:incidencia_id>/asignar", methods=["POST"])
def ruta_asignar(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    tecnico_id = request.form.get("tecnico_id", "")
    try:
        inc = asignar_tecnico(user, incidencia_id, tecnico_id)
        flash(f"Incidencia {inc['codigo']} asignada a {inc['tecnico_asignado_id']}.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/incidencias/<int:incidencia_id>/iniciar", methods=["POST"])
def ruta_iniciar(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    try:
        inc = iniciar_atencion(user, incidencia_id)
        flash(f"Atención iniciada para {inc['codigo']}. Estado: EN_ATENCION.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/incidencias/<int:incidencia_id>/solucion", methods=["POST"])
def ruta_solucion(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    solucion = request.form.get("solucion", "")
    try:
        inc = registrar_solucion(user, incidencia_id, solucion)
        flash(f"Solución registrada para {inc['codigo']}. Estado: PENDIENTE_VALIDACION.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/incidencias/<int:incidencia_id>/confirmar", methods=["POST"])
def ruta_confirmar(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    try:
        inc = confirmar_solucion(user, incidencia_id)
        flash(f"Solución confirmada. La incidencia {inc['codigo']} ha pasado a CERRADA.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/incidencias/<int:incidencia_id>/rechazar", methods=["POST"])
def ruta_rechazar(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    motivo = request.form.get("motivo", "")
    try:
        inc = rechazar_solucion(user, incidencia_id, motivo)
        flash(f"Solución rechazada. La incidencia {inc['codigo']} volvió a EN_ATENCION con el técnico {inc['tecnico_asignado_id']}.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/incidencias/<int:incidencia_id>/reabrir", methods=["POST"])
def ruta_reabrir(incidencia_id: int):
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    motivo = request.form.get("motivo", "")
    try:
        inc = reabrir_incidencia(user, incidencia_id, motivo)
        flash(f"Incidencia {inc['codigo']} reabierta exitosamente. Vuelve a EN_ATENCION con {inc['tecnico_asignado_id']}.", "success")
        return redirect(url_for("main.detalle_incidencia", incidencia_id=incidencia_id))
    except ReglaNegocioError as e:
        flash(e.mensaje, "error")
        return Response_or_render_error(user, incidencia_id, e)

@bp.route("/tablero", methods=["GET"])
def ruta_tablero():
    user = usuario_en_sesion()
    if not user:
        return redirect(url_for("main.login"))
    try:
        metricas = obtener_metricas_tablero(user)
    except ReglaNegocioError as e:
        abort(e.codigo_http, e.mensaje)
    return render_template("tablero.html", user=user, metricas=metricas)

def Response_or_render_error(user, incidencia_id: int, error: ReglaNegocioError):
    if error.codigo_http in (403, 404):
        abort(error.codigo_http, error.mensaje)
    try:
        inc = obtener_incidencia_para_usuario(user, incidencia_id)
        tecnicos = listar_tecnicos_activos() if user["rol"] == "COORDINADOR" else []
        return render_template(
            "detalle_incidencia.html",
            user=user,
            inc=inc,
            tecnicos=tecnicos,
            error_mensaje=error.mensaje,
        ), error.codigo_http
    except ReglaNegocioError:
        abort(error.codigo_http, error.mensaje)
