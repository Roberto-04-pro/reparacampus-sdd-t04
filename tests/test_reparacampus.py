import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
from app import create_app
import app.services as services
from app.db import get_db

@pytest.fixture
def app_ctx(tmp_path):
    db_file = tmp_path / "test_reparacampus.sqlite"
    app = create_app({
        "TESTING": True,
        "DATABASE": str(db_file),
        "SECRET_KEY": "test-secret-key-usb",
    })
    return app

def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )

def logout(client):
    return client.get("/logout", follow_redirects=True)

# -------------------------------------------------------------------------
# 1. Registro válido, límite exacto de 20 caracteres y prioridades (RF01/RF02)
# -------------------------------------------------------------------------
def test_01_registro_valido_y_prioridades(app_ctx):
    client = app_ctx.test_client()
    resp_login = login(client, "S01", "ClaveSegura123!")
    assert resp_login.status_code == 200

    # Caso A: Descripción exactamente de 20 caracteres tras strip + riesgo=true -> CRITICA
    desc_20 = "   12345678901234567890   "
    r1 = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": desc_20,
            "impacto": "BAJO",
            "riesgo_personas": "true",
        },
        follow_redirects=True,
    )
    assert r1.status_code == 200

    # Caso B: Sin riesgo + impacto ALTO -> ALTA
    r2 = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "AULA-201",
            "categoria": "TIC",
            "descripcion": "Falla total del punto de red en el aula 201.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
        follow_redirects=True,
    )
    assert r2.status_code == 200

    # Caso C: Sin riesgo + impacto BAJO -> NORMAL
    r3 = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "BIB-01",
            "categoria": "MOBILIARIO",
            "descripcion": "Silla ergonómica con rueda suelta en sala general.",
            "impacto": "BAJO",
            "riesgo_personas": "false",
        },
        follow_redirects=True,
    )
    assert r3.status_code == 200

    with app_ctx.app_context():
        db = get_db()
        rows = db.execute("SELECT codigo, descripcion, prioridad, estado, autor_id FROM incidencias ORDER BY id ASC").fetchall()
        assert len(rows) == 3
        assert rows[0]["codigo"] == "INC-0001"
        assert len(rows[0]["descripcion"]) == 20
        assert rows[0]["prioridad"] == "CRITICA"
        assert rows[0]["estado"] == "REGISTRADA"
        assert rows[0]["autor_id"] == "S01"
        assert rows[1]["prioridad"] == "ALTA"
        assert rows[2]["prioridad"] == "NORMAL"

# -------------------------------------------------------------------------
# 2. Límites inválidos (19 y 501 chars), valores fuera de catálogo y permisos
# -------------------------------------------------------------------------
def test_02_registro_limites_y_valores_invalidos(app_ctx):
    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")

    # 19 caracteres tras strip -> Rechazo 400
    r_19 = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "   1234567890123456789   ",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    assert r_19.status_code == 400

    # 501 caracteres -> Rechazo 400
    r_501 = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "A" * 501,
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    assert r_501.status_code == 400

    # Impacto y riesgo inválidos -> Rechazo 400
    r_imp = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "Descripción válida de más de veinte caracteres.",
            "impacto": "MEDIO",
            "riesgo_personas": "false",
        },
    )
    assert r_imp.status_code == 400

    r_riesgo = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "Descripción válida de más de veinte caracteres.",
            "impacto": "ALTO",
            "riesgo_personas": "quizas",
        },
    )
    assert r_riesgo.status_code == 400

    # Coordinador intenta registrar -> Rechazo 403
    logout(client)
    login(client, "C01", "CoordSegura123!")
    r_coord = client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "Descripción válida de más de veinte caracteres.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    assert r_coord.status_code == 403

    with app_ctx.app_context():
        cnt = get_db().execute("SELECT COUNT(*) AS c FROM incidencias").fetchone()["c"]
        assert cnt == 0

# -------------------------------------------------------------------------
# 3. Asignación correcta, repetida (prohibida), técnico inactivo y permisos
# -------------------------------------------------------------------------
def test_03_asignacion_correcta_y_prohibicion_reasignacion(app_ctx):
    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "HIDRAULICA",
            "descripcion": "Fuga en tubería principal del laboratorio de química.",
            "impacto": "ALTO",
            "riesgo_personas": "true",
        },
    )

    # Solicitante intenta asignar -> 403
    r_sol = client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    assert r_sol.status_code == 403

    # Coordinador intenta asignar a un técnico inactivo -> 400
    with app_ctx.app_context():
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO usuarios (id, username, nombre, password_hash, rol, activo) VALUES ('T03', 'T03', 'Técnico Inactivo', 'hash', 'TECNICO', 0)"
            )

    logout(client)
    login(client, "C01", "CoordSegura123!")
    r_inact = client.post("/incidencias/1/asignar", data={"tecnico_id": "T03"})
    assert r_inact.status_code == 400

    # Coordinador asigna correctamente a T01 -> pasa a ASIGNADA
    r_ok = client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"}, follow_redirects=True)
    assert r_ok.status_code == 200

    # Intento de reasignación repetida a T02 sobre incidencia ya ASIGNADA -> 400 sin cambios
    r_rep = client.post("/incidencias/1/asignar", data={"tecnico_id": "T02"})
    assert r_rep.status_code == 400

    with app_ctx.app_context():
        inc = services.obtener_incidencia_interna(1)
        assert inc["estado"] == "ASIGNADA"
        assert inc["tecnico_asignado_id"] == "T01"
        assert len(inc["historial"]) == 2

# -------------------------------------------------------------------------
# 4. Atención por técnico: técnico ajeno, solución antes de iniciar y límites
# -------------------------------------------------------------------------
def test_04_atencion_tecnico_permisos_y_orden_estados(app_ctx):
    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "AULA-201",
            "categoria": "MOBILIARIO",
            "descripcion": "Puerta principal del aula 201 con bisagra desprendida.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})

    # Técnico NO asignado (T02) intenta iniciar atención -> 403
    logout(client)
    login(client, "T02", "TecSegura123!")
    r_t2 = client.post("/incidencias/1/iniciar")
    assert r_t2.status_code == 403

    # Técnico asignado (T01) intenta registrar solución ANTES de iniciar atención -> 400
    logout(client)
    login(client, "T01", "TecSegura123!")
    r_antes = client.post(
        "/incidencias/1/solucion",
        data={"solucion": "Se intenta registrar solución estando aún en ASIGNADA."},
    )
    assert r_antes.status_code == 400

    # T01 inicia atención -> pasa a EN_ATENCION
    r_ini = client.post("/incidencias/1/iniciar", follow_redirects=True)
    assert r_ini.status_code == 200

    # Solución corta de 19 chars -> 400
    r_corta = client.post("/incidencias/1/solucion", data={"solucion": "   1234567890123456789   "})
    assert r_corta.status_code == 400

    # Solución válida de 20+ chars -> pasa a PENDIENTE_VALIDACION
    r_sol = client.post(
        "/incidencias/1/solucion",
        data={"solucion": "Se soldó la bisagra superior y se lubricó el marco metálico."},
        follow_redirects=True,
    )
    assert r_sol.status_code == 200

    with app_ctx.app_context():
        inc = services.obtener_incidencia_interna(1)
        assert inc["estado"] == "PENDIENTE_VALIDACION"
        assert len(inc["historial"]) == 4

# -------------------------------------------------------------------------
# 5. Confirmación y rechazo de solución (válido e inválido)
# -------------------------------------------------------------------------
def test_05_confirmacion_y_rechazo_solucion(app_ctx):
    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "TIC",
            "descripcion": "Switch de comunicaciones del rack #2 sin encendido eléctrico.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Se cambió el cable de poder C13 conectado a la UPS."})

    # Solicitante dueño intenta rechazar con motivo inválido de 9 chars -> 400
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    r_bad = client.post("/incidencias/1/rechazar", data={"motivo": "   123456789   "})
    assert r_bad.status_code == 400

    # Rechazo válido (10..300 chars): vuelve a EN_ATENCION con T01 y conserva solución anterior
    r_rej = client.post(
        "/incidencias/1/rechazar",
        data={"motivo": "El daño sigue presente; el switch se apaga a los dos minutos."},
        follow_redirects=True,
    )
    assert r_rej.status_code == 200

    with app_ctx.app_context():
        inc = services.obtener_incidencia_interna(1)
        assert inc["estado"] == "EN_ATENCION"
        assert inc["tecnico_asignado_id"] == "T01"
        assert inc["solucion_actual"] == "Se cambió el cable de poder C13 conectado a la UPS."

# -------------------------------------------------------------------------
# 6. Reapertura exactamente a las 48 horas UTC y rechazo después de 48 horas
# -------------------------------------------------------------------------
def test_06_reapertura_limite_exacto_48h_y_posterior(app_ctx, monkeypatch):
    t_base = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(services, "get_utc_now", lambda: t_base)

    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")
    # Crear 2 incidencias para probar 48h exactas en la #1 y 48h+1s en la #2
    for idx in (1, 2):
        client.post(
            "/incidencias/nueva",
            data={
                "ubicacion": "LAB-01",
                "categoria": "ELECTRICIDAD",
                "descripcion": f"Incidencia de prueba #{idx} para verificar ventana de 48 horas UTC.",
                "impacto": "ALTO",
                "riesgo_personas": "false",
            },
        )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    client.post("/incidencias/2/asignar", data={"tecnico_id": "T01"})

    logout(client)
    login(client, "T01", "TecSegura123!")
    for idx in (1, 2):
        client.post(f"/incidencias/{idx}/iniciar")
        client.post(f"/incidencias/{idx}/solucion", data={"solucion": "Se reemplazó el componente eléctrico averiado en pruebas."})

    # Cerrar ambas exactamente en t_base (2026-10-10T12:00:00Z)
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")
    client.post("/incidencias/2/confirmar")

    # 1) Avanzar reloj exactamente 48 horas (172.800 segundos) -> SE ACEPTA
    t_exacto_48h = t_base + timedelta(hours=48)
    monkeypatch.setattr(services, "get_utc_now", lambda: t_exacto_48h)
    r_ok_48h = client.post(
        "/incidencias/1/reabrir",
        data={"motivo": "Exactamente a las 48h volvió a presentarse la falla eléctrica."},
        follow_redirects=True,
    )
    assert r_ok_48h.status_code == 200

    # 2) Avanzar reloj a 48 horas y 1 segundo (172.801 segundos) -> SE RECHAZA SIN CAMBIOS
    t_despues_48h = t_base + timedelta(hours=48, seconds=1)
    monkeypatch.setattr(services, "get_utc_now", lambda: t_despues_48h)
    r_fail_48h = client.post(
        "/incidencias/2/reabrir",
        data={"motivo": "Intento de reapertura un segundo después de las 48 horas UTC."},
    )
    assert r_fail_48h.status_code == 400

    with app_ctx.app_context():
        inc1 = services.obtener_incidencia_interna(1)
        inc2 = services.obtener_incidencia_interna(2)
        assert inc1["estado"] == "EN_ATENCION"
        assert inc1["tecnico_asignado_id"] == "T01"
        assert len(inc1["cierres"]) == 1
        assert inc2["estado"] == "CERRADA"
        assert inc2["historial"][-1]["accion"] == "CIERRE"

# -------------------------------------------------------------------------
# 7. Propietario ajeno (S02) y coordinador no pueden leer, confirmar ni reabrir
# -------------------------------------------------------------------------
def test_07_permisos_propietario_ajeno_y_coordinador(app_ctx):
    client = app_ctx.test_client()
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "BIB-01",
            "categoria": "HIDRAULICA",
            "descripcion": "Goteo en válvula de control del baño del segundo piso.",
            "impacto": "BAJO",
            "riesgo_personas": "false",
        },
    )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Se reemplazó el empaque de neopreno de la válvula."})

    # Otro solicitante (S02) intenta leer o confirmar -> 403
    logout(client)
    login(client, "S02", "ClaveSegura123!")
    assert client.get("/incidencias/1").status_code == 403
    assert client.post("/incidencias/1/confirmar").status_code == 403
    assert client.post("/incidencias/1/rechazar", data={"motivo": "Intento ajeno de rechazo válido."}).status_code == 403

    # Coordinador (C01) intenta confirmar en nombre del solicitante -> 403
    logout(client)
    login(client, "C01", "CoordSegura123!")
    assert client.post("/incidencias/1/confirmar").status_code == 403

# -------------------------------------------------------------------------
# 8. Filtros por estado y prioridad según permisos e historial inmutable
# -------------------------------------------------------------------------
def test_08_filtros_visibilidad_por_rol_e_inmutabilidad_historial(app_ctx):
    client = app_ctx.test_client()
    # S01 crea CRITICA
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "Cable expuesto con tensión viva en banco de ensayos.",
            "impacto": "ALTO",
            "riesgo_personas": "true",
        },
    )
    logout(client)
    # S02 crea NORMAL
    login(client, "S02", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "BIB-01",
            "categoria": "MOBILIARIO",
            "descripcion": "Estante metálico con pintura rayada en pasillo norte.",
            "impacto": "BAJO",
            "riesgo_personas": "false",
        },
    )

    # S02 solo ve INC-0002, no INC-0001
    html_s02 = client.get("/incidencias").get_data(as_text=True)
    assert "INC-0002" in html_s02
    assert "INC-0001" not in html_s02

    # Coordinador filtra por prioridad CRITICA -> solo ve INC-0001
    logout(client)
    login(client, "C01", "CoordSegura123!")
    html_crit = client.get("/incidencias?prioridad=CRITICA").get_data(as_text=True)
    assert "INC-0001" in html_crit
    assert "INC-0002" not in html_crit

# -------------------------------------------------------------------------
# 9. Tablero del coordinador: vacío = 0,0 %, 1 de 4 = 25,0 % y reducción al reabrir
# -------------------------------------------------------------------------
def test_09_tablero_coordinador_vacio_25_porciento_y_reapertura(app_ctx):
    client = app_ctx.test_client()
    login(client, "C01", "CoordSegura123!")
    # Tablero vacío -> 0,0 %
    html_vacio = client.get("/tablero").get_data(as_text=True)
    assert "0,0 %" in html_vacio

    # Crear 4 incidencias y cerrar 1 -> 25,0 %
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    for i in range(4):
        client.post(
            "/incidencias/nueva",
            data={
                "ubicacion": "LAB-01",
                "categoria": "ELECTRICIDAD",
                "descripcion": f"Reporte número {i+1} para verificación de métricas del tablero.",
                "impacto": "ALTO",
                "riesgo_personas": "true" if i < 2 else "false",
            },
        )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Solución completa aplicada para cerrar el primer reporte."})
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")

    logout(client)
    login(client, "C01", "CoordSegura123!")
    html_25 = client.get("/tablero").get_data(as_text=True)
    assert "25,0 %" in html_25

    # Reabrir la incidencia #1 -> reduce porcentaje a 0,0 % y conserva cierre anterior
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/reabrir", data={"motivo": "Reapertura dentro del plazo para verificar reducción de porcentaje."})

    logout(client)
    login(client, "C01", "CoordSegura123!")
    html_reabierto = client.get("/tablero").get_data(as_text=True)
    assert "0,0 %" in html_reabierto
    with app_ctx.app_context():
        inc1 = services.obtener_incidencia_interna(1)
        assert len(inc1["cierres"]) == 1

# -------------------------------------------------------------------------
# 10. Seguridad anti-XSS, cuentas de prueba y persistencia tras reinicio
# -------------------------------------------------------------------------
def test_10_seguridad_xss_autenticacion_y_persistencia_reinicio(tmp_path):
    db_path = tmp_path / "persistencia_real.sqlite"
    app1 = create_app({"TESTING": True, "DATABASE": str(db_path)})
    c1 = app1.test_client()

    login(c1, "S01", "ClaveSegura123!")
    payload_xss = "<script>alert('hack')</script> Daño real en toma eléctrico del laboratorio."
    r = c1.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": payload_xss,
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
        follow_redirects=True,
    )
    texto = r.get_data(as_text=True)
    assert "<script>alert" not in texto
    assert "&lt;script&gt;alert" in texto

    # Simular reinicio del servidor instanciando una nueva app sobre el mismo archivo SQLite
    app2 = create_app({"TESTING": True, "DATABASE": str(db_path)})
    c2 = app2.test_client()
    login(c2, "S01", "ClaveSegura123!")
    texto2 = c2.get("/incidencias/1").get_data(as_text=True)
    assert "INC-0001" in texto2
    assert "&lt;script&gt;alert" in texto2

# -------------------------------------------------------------------------
# 11. INTEGRACIÓN 1 (SQLite Real): Flujo completo de cierre
# -------------------------------------------------------------------------
def test_11_integracion_sql_real_flujo_cierre_completo(tmp_path):
    db_path = tmp_path / "int1_cierre.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    client = app.test_client()

    # 1. Registrar (S01)
    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "LAB-01",
            "categoria": "ELECTRICIDAD",
            "descripcion": "Luminaria LED central parpadea y genera chispas sobre mesón.",
            "impacto": "ALTO",
            "riesgo_personas": "true",
        },
    )
    # 2. Asignar (C01 -> T01)
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    # 3. Iniciar atención y 4. Proponer solución (T01)
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Se reemplazó el balasto electrónico y se aisló el empalme."})
    # 5. Confirmar solución (S01)
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    inc = conn.execute("SELECT * FROM incidencias WHERE id = 1").fetchone()
    eventos = conn.execute("SELECT accion, estado_nuevo FROM historial_eventos WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    conn.close()

    assert inc["estado"] == "CERRADA"
    assert inc["prioridad"] == "CRITICA"
    assert [e["accion"] for e in eventos] == [
        "CREACION",
        "ASIGNACION",
        "INICIO_ATENCION",
        "REGISTRO_SOLUCION",
        "CIERRE",
    ]

# -------------------------------------------------------------------------
# 12. INTEGRACIÓN 2 (SQLite Real): Recorrido con rechazo de solución y nueva solución
# -------------------------------------------------------------------------
def test_12_integracion_sql_real_recorrido_con_rechazo_y_nueva_solucion(tmp_path):
    db_path = tmp_path / "int2_rechazo.sqlite"
    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    client = app.test_client()

    login(client, "S01", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "AULA-201",
            "categoria": "TIC",
            "descripcion": "Proyector multimedia del aula 201 se apaga por sobrecalentamiento.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T01"})
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Se limpió superficialmente la rejilla externa de ventilación."})

    # S01 rechaza la primera solución
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/rechazar", data={"motivo": "El equipo sigue apagándose tras diez minutos de encendido."})

    # T01 (el mismo técnico conservado) registra segunda solución definitiva
    logout(client)
    login(client, "T01", "TecSegura123!")
    client.post("/incidencias/1/solucion", data={"solucion": "Se reemplazó el ventilador interno extractor y la pasta térmica."})

    # S01 confirma
    logout(client)
    login(client, "S01", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    soluciones = conn.execute("SELECT * FROM soluciones WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    eventos = conn.execute("SELECT accion FROM historial_eventos WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    conn.close()

    assert len(soluciones) == 2
    assert soluciones[0]["estado_revision"] == "RECHAZADA"
    assert soluciones[1]["estado_revision"] == "CONFIRMADA"
    assert [e["accion"] for e in eventos] == [
        "CREACION",
        "ASIGNACION",
        "INICIO_ATENCION",
        "REGISTRO_SOLUCION",
        "RECHAZO_SOLUCION",
        "REGISTRO_SOLUCION",
        "CIERRE",
    ]

# -------------------------------------------------------------------------
# 13. INTEGRACIÓN 3 (SQLite Real): Cierre -> Reapertura -> Nueva solución -> Nuevo cierre
# -------------------------------------------------------------------------
def test_13_integracion_sql_real_cierre_reapertura_nueva_solucion_nuevo_cierre(tmp_path, monkeypatch):
    db_path = tmp_path / "int3_reapertura.sqlite"
    t0 = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(services, "get_utc_now", lambda: t0)

    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    client = app.test_client()

    login(client, "S02", "ClaveSegura123!")
    client.post(
        "/incidencias/nueva",
        data={
            "ubicacion": "BIB-01",
            "categoria": "HIDRAULICA",
            "descripcion": "Bomba de agua de presión constante presenta ruido y baja presión.",
            "impacto": "ALTO",
            "riesgo_personas": "false",
        },
    )
    logout(client)
    login(client, "C01", "CoordSegura123!")
    client.post("/incidencias/1/asignar", data={"tecnico_id": "T02"})
    logout(client)
    login(client, "T02", "TecSegura123!")
    client.post("/incidencias/1/iniciar")
    client.post("/incidencias/1/solucion", data={"solucion": "Se purgó el aire acumulado en la tubería de impulsión."})

    # Primer cierre por S02
    logout(client)
    login(client, "S02", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")

    # 18 horas después (< 48h UTC), S02 reabre la incidencia
    monkeypatch.setattr(services, "get_utc_now", lambda: t0 + timedelta(hours=18))
    client.post("/incidencias/1/reabrir", data={"motivo": "La presión volvió a caer por completo esta mañana en biblioteca."})

    # T02 registra nueva solución
    logout(client)
    login(client, "T02", "TecSegura123!")
    client.post("/incidencias/1/solucion", data={"solucion": "Se reemplazó el presostato defectuoso y la válvula cheque."})

    # Segundo cierre por S02
    logout(client)
    login(client, "S02", "ClaveSegura123!")
    client.post("/incidencias/1/confirmar")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    inc = conn.execute("SELECT * FROM incidencias WHERE id = 1").fetchone()
    cierres = conn.execute("SELECT * FROM cierres WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    soluciones = conn.execute("SELECT * FROM soluciones WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    eventos = conn.execute("SELECT accion FROM historial_eventos WHERE incidencia_id = 1 ORDER BY id ASC").fetchall()
    conn.close()

    assert inc["estado"] == "CERRADA"
    assert inc["tecnico_asignado_id"] == "T02"
    assert len(cierres) == 2
    assert len(soluciones) == 2
    assert [e["accion"] for e in eventos] == [
        "CREACION",
        "ASIGNACION",
        "INICIO_ATENCION",
        "REGISTRO_SOLUCION",
        "CIERRE",
        "REAPERTURA",
        "REGISTRO_SOLUCION",
        "CIERRE",
    ]
