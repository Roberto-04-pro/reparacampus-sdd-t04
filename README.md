# ReparaCampus · Gestión de Incidencias de Infraestructura (SDD + IA)

**Universidad Simón Bolívar · Programa de Ingeniería de Sistemas · Ingeniería de Software I**  
**Grupo:** `T04` (`1_12_5906_T04_2026_2`)  
**Docente:** Adriana María Iglesias Solano  
**Equipo:** **InfraCore**  
- **Osvaldo Navarro** (Código: `2024114082`)  
- **Juan Jiménez** (Código: `2024114105`)  
- **Roberto Rueda** (Código: `2024114139`)  

## 1. Descripción del Proyecto
Prototipo web desarrollado bajo la metodología **Spec-Driven Development (SDD) + IA** para organizar las incidencias de infraestructura de la Universidad Simón Bolívar (Caso **ReparaCampus**). Implementa en servidor las cinco funcionalidades (`RF01` a `RF05`) vinculadas a las especificaciones `S01` a `S05` ubicadas en `specs/`.

## 2. Versiones Exactas y Dependencias
- **Python:** `3.11.2`
- **Flask:** `3.0.3`
- **Werkzeug:** `3.0.3` (Hash de contraseñas `pbkdf2:sha256:600000`)
- **Jinja2:** `3.1.6` (Auto-escaping HTML activo contra XSS)
- **SQLite:** `3.40.1` (`sqlite3` estándar con `PRAGMA foreign_keys = ON` y transacciones atómicas)
- **pytest:** `8.3.3`

## 3. Estructura del Repositorio
```text
reparacampus/
├── specs/
│   ├── 00_contexto_preguntas_cliente.md
│   ├── S01_registro_incidencias.md
│   ├── S02_priorizacion_asignacion.md
│   ├── S03_atencion_solucion.md
│   ├── S04_validacion_reapertura.md
│   └── S05_consulta_historial_tablero.md
├── app/
│   ├── __init__.py          # Application Factory (create_app)
│   ├── db.py                # Conexión SQLite, esquema y seed de cuentas
│   ├── schema.sql           # Esquema relacional (usuarios, incidencias, asignaciones, soluciones, cierres, historial_eventos)
│   ├── services.py          # Reglas de negocio, permisos, prioridades y reloj UTC
│   ├── routes.py            # Controladores HTTP y manejo de sesión
│   ├── static/style.css     # Estilos institucionales
│   └── templates/           # Plantillas Jinja2 (login, incidencias, nueva, detalle, tablero, error)
├── tests/
│   └── test_reparacampus.py # 13 pruebas automatizadas (10 funcionales + 3 de integración SQLite real)
├── seed.py                  # Script de carga de las 5 cuentas ficticias y 4 incidencias semilla
├── run.py                   # Punto de entrada del servidor Flask
├── requirements.txt         # Dependencias con versiones exactas
└── README.md                # Guía de reproducción y verificación
```

## 4. Instalación y Ejecución desde una Copia Limpia
```bash
# 1. Clonar el repositorio y ubicarse en la versión de entrega
git clone https://github.com/equipo-infracore-usb/reparacampus-sdd-t04.git
cd reparacampus-sdd-t04
git checkout release-examen

# 2. Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Inicializar la base de datos SQLite con el seed ficticio
python3 seed.py

# 4. Iniciar el servidor web en http://127.0.0.1:5000
python3 run.py
```

## 5. Cuentas Ficticias de Prueba (Seed)
| Código / Usuario | Rol en Servidor | Nombre Ficticio | Contraseña | Estado |
| :--- | :--- | :--- | :--- | :--- |
| `S01` | `SOLICITANTE` | Dra. Ana María Gómez (Solicitante 1) | `ClaveSegura123!` | Activo (`1`) |
| `S02` | `SOLICITANTE` | Ing. Carlos Andrés Pérez (Solicitante 2) | `ClaveSegura123!` | Activo (`1`) |
| `C01` | `COORDINADOR` | Ing. Laura Sofía Martínez (Coordinadora) | `CoordSegura123!` | Activo (`1`) |
| `T01` | `TECNICO` | Téc. Miguel Ángel Torres (Técnico 1) | `TecSegura123!` | Activo (`1`) |
| `T02` | `TECNICO` | Téc. Jorge Luis Ramírez (Técnico 2) | `TecSegura123!` | Activo (`1`) |

## 6. Ejecución de las Pruebas Automatizadas (pytest)
Todas las pruebas utilizan una base de datos SQLite temporal e independiente (`tmp_path`) sin alterar `reparacampus.db`:
```bash
pytest -v
```

## 7. Limitaciones Conocidas de la Versión v1.0 (Conformes al Alcance del Caso)
- No se permite reasignar una incidencia una vez pasa al estado `ASIGNADA` (regla inmutable del enunciado).
- No se incluyen archivos adjuntos, notificaciones por correo ni integración de IA dentro del producto final.
- No hay restricción por especialidad del técnico en esta versión.
