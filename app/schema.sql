PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('SOLICITANTE', 'COORDINADOR', 'TECNICO')),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    autor_id TEXT NOT NULL REFERENCES usuarios(id),
    ubicacion TEXT NOT NULL CHECK (ubicacion IN ('LAB-01', 'AULA-201', 'BIB-01')),
    categoria TEXT NOT NULL CHECK (categoria IN ('ELECTRICIDAD', 'HIDRAULICA', 'MOBILIARIO', 'TIC')),
    descripcion TEXT NOT NULL,
    impacto TEXT NOT NULL CHECK (impacto IN ('BAJO', 'ALTO')),
    riesgo_personas INTEGER NOT NULL CHECK (riesgo_personas IN (0, 1)),
    prioridad TEXT NOT NULL CHECK (prioridad IN ('CRITICA', 'ALTA', 'NORMAL')),
    estado TEXT NOT NULL CHECK (estado IN ('REGISTRADA', 'ASIGNADA', 'EN_ATENCION', 'PENDIENTE_VALIDACION', 'CERRADA')),
    tecnico_asignado_id TEXT REFERENCES usuarios(id),
    solucion_actual TEXT,
    fecha_creacion_utc TEXT NOT NULL,
    fecha_ultimo_cierre_utc TEXT
);

CREATE TABLE IF NOT EXISTS asignaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL UNIQUE REFERENCES incidencias(id),
    coordinador_id TEXT NOT NULL REFERENCES usuarios(id),
    tecnico_id TEXT NOT NULL REFERENCES usuarios(id),
    fecha_asignacion_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS soluciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL REFERENCES incidencias(id),
    tecnico_id TEXT NOT NULL REFERENCES usuarios(id),
    texto_solucion TEXT NOT NULL,
    fecha_registro_utc TEXT NOT NULL,
    estado_revision TEXT NOT NULL DEFAULT 'PROPUESTA'
);

CREATE TABLE IF NOT EXISTS cierres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL REFERENCES incidencias(id),
    solicitante_id TEXT NOT NULL REFERENCES usuarios(id),
    fecha_cierre_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historial_eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia_id INTEGER NOT NULL REFERENCES incidencias(id),
    autor_id TEXT NOT NULL REFERENCES usuarios(id),
    accion TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    detalle TEXT,
    solucion_propuesta TEXT,
    motivo TEXT,
    fecha_utc TEXT NOT NULL
);
