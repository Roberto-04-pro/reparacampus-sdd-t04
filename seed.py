"""Script de inicialización y carga de datos ficticios (seed) para ReparaCampus."""
import os
from app import create_app
from app.db import get_db, init_db
from app.services import (
    asignar_tecnico,
    confirmar_solucion,
    crear_incidencia,
    iniciar_atencion,
    obtener_usuario_por_id,
    rechazar_solucion,
    registrar_solucion,
)

def ejecutar_seed(db_path: str = None):
    config = {}
    if db_path:
        config["DATABASE"] = db_path
    app = create_app(config)
    with app.app_context():
        db = get_db()
        db.executescript("""
            DELETE FROM historial_eventos;
            DELETE FROM cierres;
            DELETE FROM soluciones;
            DELETE FROM asignaciones;
            DELETE FROM incidencias;
        """)
        init_db(seed_users=True)

        s01 = obtener_usuario_por_id("S01")
        s02 = obtener_usuario_por_id("S02")
        c01 = obtener_usuario_por_id("C01")
        t01 = obtener_usuario_por_id("T01")
        t02 = obtener_usuario_por_id("T02")

        # 1. INC-0001: CRITICA en LAB-01 (En atención tras un rechazo previo de solución)
        inc1 = crear_incidencia(
            s01,
            ubicacion="LAB-01",
            categoria="ELECTRICIDAD",
            descripcion="Cortocircuito en tablero secundario con chispas cerca de mesón de trabajo.",
            impacto="ALTO",
            riesgo_personas=True,
        )
        asignar_tecnico(c01, inc1["id"], "T01")
        iniciar_atencion(t01, inc1["id"])
        registrar_solucion(t01, inc1["id"], "Se ajustaron bornes flojos del interruptor termomagnético secundario.")
        rechazar_solucion(s01, inc1["id"], "El interruptor vuelve a dispararse al encender los equipos del laboratorio.")

        # 2. INC-0002: ALTA en AULA-201 (En estado PENDIENTE_VALIDACION)
        inc2 = crear_incidencia(
            s01,
            ubicacion="AULA-201",
            categoria="TIC",
            descripcion="Punto de red principal del videoproyector sin conectividad hacia el switch de piso.",
            impacto="ALTO",
            riesgo_personas=False,
        )
        asignar_tecnico(c01, inc2["id"], "T02")
        iniciar_atencion(t02, inc2["id"])
        registrar_solucion(t02, inc2["id"], "Se recertificó el cable UTP Cat6 y se reemplazó el jack RJ45 de pared dañado.")

        # 3. INC-0003: NORMAL en BIB-01 (En estado CERRADA)
        inc3 = crear_incidencia(
            s02,
            ubicacion="BIB-01",
            categoria="MOBILIARIO",
            descripcion="Mesa de lectura grupal #4 presenta desnivel severo por soporte metálico suelto.",
            impacto="BAJO",
            riesgo_personas=False,
        )
        asignar_tecnico(c01, inc3["id"], "T01")
        iniciar_atencion(t01, inc3["id"])
        registrar_solucion(t01, inc3["id"], "Se instalaron cuatro pernos de anclaje nuevos y niveladores antideslizantes.")
        confirmar_solucion(s02, inc3["id"])

        # 4. INC-0004: CRITICA en BIB-01 (En estado REGISTRADA para demostración de asignación)
        crear_incidencia(
            s02,
            ubicacion="BIB-01",
            categoria="HIDRAULICA",
            descripcion="Filtración de agua constante en techo de pasillo principal con piso resbaloso.",
            impacto="ALTO",
            riesgo_personas=True,
        )
        print("Seed completado exitosamente: 5 cuentas ficticias y 4 incidencias de demostración creadas (25,0 % cierre).")

if __name__ == "__main__":
    ejecutar_seed()
