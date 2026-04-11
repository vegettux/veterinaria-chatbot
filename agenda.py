import sqlite3
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "agenda.db"

TIEMPOS_CIRUGIA = {
    "gato_macho": 12,
    "gata_hembra": 15,
    "perro_macho": 30,
    "perra_0_10": 45,
    "perra_10_20": 50,
    "perra_20_30": 60,
    "perra_30_40": 60,
    "perra_40_mas": 70,
}

CAPACIDAD_DIARIA = 240
MAX_PERROS_DIA = 2
DIAS_OPERATIVOS = [0, 1, 2, 3]  # lunes a jueves


# =========================
# DB
# =========================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            dni TEXT UNIQUE,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS mascotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            especie TEXT NOT NULL,
            sexo TEXT NOT NULL,
            peso REAL DEFAULT 0,
            edad INTEGER DEFAULT 0,
            tiene_microchip INTEGER DEFAULT 0,
            tiene_vacuna_rabia INTEGER DEFAULT 0,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente_id INTEGER NOT NULL,
            mascota_id INTEGER NOT NULL,
            tipo_cirugia TEXT NOT NULL,
            minutos INTEGER NOT NULL,
            estado TEXT DEFAULT 'confirmada',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (mascota_id) REFERENCES mascotas(id)
        )
    """)

    conn.commit()
    conn.close()


# =========================
# CLIENTES
# =========================

def buscar_cliente_por_dni(dni: str) -> Optional[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, nombre, dni, telefono, email, direccion FROM clientes WHERE UPPER(dni) = ?",
        (dni.strip().upper(),)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def buscar_cliente_por_nombre(nombre: str) -> Optional[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, nombre, dni, telefono, email, direccion FROM clientes WHERE LOWER(nombre) LIKE ? LIMIT 1",
        (f"%{nombre.strip().lower()}%",)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def registrar_cliente(nombre: str, dni: str, telefono: str, email: str, direccion: str) -> tuple[bool, str]:
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO clientes (nombre, dni, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?)
        """, (
            nombre.strip(),
            dni.strip().upper(),
            telefono.strip(),
            email.strip(),
            direccion.strip(),
        ))
        cliente_id = c.lastrowid
        conn.commit()
        conn.close()
        return True, str(cliente_id)
    except sqlite3.IntegrityError:
        return False, "Ya existe un cliente con ese DNI."


# =========================
# MASCOTAS
# =========================

def listar_mascotas_cliente(cliente_id: int) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, cliente_id, nombre, especie, sexo, peso, edad, tiene_microchip, tiene_vacuna_rabia
        FROM mascotas
        WHERE cliente_id = ?
        ORDER BY nombre
    """, (cliente_id,))
    rows = c.fetchall()
    conn.close()

    mascotas = []
    for row in rows:
        mascotas.append({
            "id": row["id"],
            "cliente_id": row["cliente_id"],
            "nombre": row["nombre"],
            "especie": row["especie"],
            "sexo": row["sexo"],
            "peso": row["peso"],
            "edad": row["edad"],
            "tiene_microchip": bool(row["tiene_microchip"]),
            "tiene_vacuna_rabia": bool(row["tiene_vacuna_rabia"]),
        })
    return mascotas


def buscar_mascota_cliente_por_nombre(cliente_id: int, nombre: str) -> Optional[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, cliente_id, nombre, especie, sexo, peso, edad, tiene_microchip, tiene_vacuna_rabia
        FROM mascotas
        WHERE cliente_id = ? AND LOWER(nombre) = ?
        LIMIT 1
    """, (cliente_id, nombre.strip().lower()))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "cliente_id": row["cliente_id"],
        "nombre": row["nombre"],
        "especie": row["especie"],
        "sexo": row["sexo"],
        "peso": row["peso"],
        "edad": row["edad"],
        "tiene_microchip": bool(row["tiene_microchip"]),
        "tiene_vacuna_rabia": bool(row["tiene_vacuna_rabia"]),
    }


def registrar_mascota(
    cliente_id: int,
    nombre: str,
    especie: str,
    sexo: str,
    peso: float,
    edad: int,
    microchip: bool,
    vacuna_rabia: bool
) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO mascotas (
            cliente_id, nombre, especie, sexo, peso, edad, tiene_microchip, tiene_vacuna_rabia
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        nombre.strip().lower(),
        especie.strip().lower(),
        sexo.strip().lower(),
        float(peso),
        int(edad),
        int(microchip),
        int(vacuna_rabia),
    ))
    mascota_id = c.lastrowid
    conn.commit()
    conn.close()
    return mascota_id


# =========================
# CITAS Y REGLAS
# =========================

def existe_cita_mascota(fecha_str: str, mascota_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*)
        FROM citas
        WHERE fecha = ? AND mascota_id = ? AND estado = 'confirmada'
    """, (fecha_str, mascota_id))
    total = c.fetchone()[0]
    conn.close()
    return total > 0


def obtener_cita_confirmada_por_mascota(mascota_id: int) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT fecha
        FROM citas
        WHERE mascota_id = ? AND estado = 'confirmada'
        ORDER BY fecha DESC
        LIMIT 1
    """, (mascota_id,))
    row = c.fetchone()
    conn.close()
    return row["fecha"] if row else None


def obtener_todas_citas_confirmadas_por_mascota(mascota_id: int) -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT fecha
        FROM citas
        WHERE mascota_id = ? AND estado = 'confirmada'
        ORDER BY fecha
    """, (mascota_id,))
    rows = c.fetchall()
    conn.close()
    return [row["fecha"] for row in rows]


def es_dia_operativo(fecha_str: str) -> tuple[bool, str]:
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "Formato de fecha incorrecto."

    if fecha.weekday() not in DIAS_OPERATIVOS:
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        return False, f"El {dias[fecha.weekday()]} no es día operativo. Las cirugías son de lunes a jueves."

    return True, ""


def get_minutos_ocupados(fecha_str: str, conn: Optional[sqlite3.Connection] = None) -> int:
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(minutos), 0) AS total FROM citas WHERE fecha = ? AND estado = 'confirmada'", (fecha_str,))
    total = c.fetchone()["total"]

    if close_after:
        conn.close()

    return total or 0


def get_perros_dia(fecha_str: str, conn: Optional[sqlite3.Connection] = None) -> int:
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True

    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) AS total
        FROM citas c
        JOIN mascotas m ON c.mascota_id = m.id
        WHERE c.fecha = ? AND c.estado = 'confirmada' AND m.especie = 'perro'
    """, (fecha_str,))
    total = c.fetchone()["total"]

    if close_after:
        conn.close()

    return total or 0


def cliente_tiene_citas_en_fecha(fecha_str: str, cliente_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) AS total
        FROM citas
        WHERE fecha = ? AND cliente_id = ? AND estado = 'confirmada'
    """, (fecha_str, cliente_id))
    total = c.fetchone()["total"]
    conn.close()
    return total or 0


def verificar_disponibilidad(fecha_str: str, tipo_cirugia: str) -> tuple[bool, str]:
    operativo, msg = es_dia_operativo(fecha_str)
    if not operativo:
        return False, msg

    minutos = TIEMPOS_CIRUGIA.get(tipo_cirugia, 30)
    ocupados = get_minutos_ocupados(fecha_str)

    if ocupados + minutos > CAPACIDAD_DIARIA:
        restantes = CAPACIDAD_DIARIA - ocupados
        return False, f"No hay disponibilidad. Solo quedan {restantes} min."

    if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
        perros = get_perros_dia(fecha_str)
        if perros >= MAX_PERROS_DIA:
            return False, "Ese día ya tiene 2 perros programados."

    return True, "Disponible"


def reservar_cita(fecha_str: str, cliente_id: int, mascota_id: int, tipo_cirugia: str) -> tuple[bool, str]:
    """
    Reserva más segura:
    - abre transacción
    - vuelve a verificar dentro de la misma
    - inserta solo si sigue habiendo hueco
    """
    operativo, msg = es_dia_operativo(fecha_str)
    if not operativo:
        return False, msg

    minutos = TIEMPOS_CIRUGIA.get(tipo_cirugia, 30)

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()

        c.execute("""
            SELECT COUNT(*) AS total
            FROM citas
            WHERE fecha = ? AND mascota_id = ? AND estado = 'confirmada'
        """, (fecha_str, mascota_id))
        if c.fetchone()["total"] > 0:
            conn.rollback()
            return False, "La mascota ya tiene una cita confirmada en esa fecha."

        ocupados = get_minutos_ocupados(fecha_str, conn=conn)
        if ocupados + minutos > CAPACIDAD_DIARIA:
            conn.rollback()
            restantes = CAPACIDAD_DIARIA - ocupados
            return False, f"No hay disponibilidad. Solo quedan {restantes} min."

        if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
            perros = get_perros_dia(fecha_str, conn=conn)
            if perros >= MAX_PERROS_DIA:
                conn.rollback()
                return False, "Ese día ya tiene 2 perros programados."

        c.execute("""
            INSERT INTO citas (fecha, cliente_id, mascota_id, tipo_cirugia, minutos, estado)
            VALUES (?, ?, ?, ?, ?, 'confirmada')
        """, (fecha_str, cliente_id, mascota_id, tipo_cirugia, minutos))

        conn.commit()
        return True, "Cita reservada correctamente."

    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Error de base de datos: {str(e)}"
    finally:
        conn.close()


def listar_citas(fecha_str: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()

    if fecha_str:
        c.execute("SELECT * FROM citas WHERE fecha = ? ORDER BY fecha", (fecha_str,))
    else:
        c.execute("SELECT * FROM citas ORDER BY fecha")

    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# =========================
# DISPONIBILIDAD REAL
# =========================

def fecha_es_reservable(fecha: datetime.date) -> bool:
    return fecha.weekday() in DIAS_OPERATIVOS


def get_fechas_disponibles_reales(tipo_cirugia: str, limite: int = 5) -> list[dict]:
    """
    Devuelve próximas fechas realmente disponibles según:
    - días operativos
    - minutos consumidos
    - límite de perros
    """
    resultados = []
    hoy = datetime.now().date()
    dia = hoy

    while len(resultados) < limite:
        dia += timedelta(days=1)

        if not fecha_es_reservable(dia):
            continue

        fecha_str = dia.strftime("%Y-%m-%d")
        disponible, _ = verificar_disponibilidad(fecha_str, tipo_cirugia)

        if disponible:
            resultados.append({
                "fecha": fecha_str,
                "texto": formatear_fecha_visual(dia),
                "tipo_cirugia": tipo_cirugia,
            })

    return resultados


def formatear_fecha_visual(fecha: datetime.date) -> str:
    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{dias_semana[fecha.weekday()]} {fecha.day} de {meses[fecha.month - 1]} de {fecha.year}"

def contar_citas_por_dia(fecha: str):
    import sqlite3
    conn = sqlite3.connect("agenda.db")
    c = conn.cursor()

    c.execute("""
        SELECT tipo_cirugia FROM citas
        WHERE fecha = ? AND estado = 'confirmada'
    """, (fecha,))
    
    resultados = c.fetchall()
    conn.close()

    total = len(resultados)
    hembras = sum(1 for r in resultados if "hembra" in r[0])
    grandes = sum(1 for r in resultados if "30" in r[0] or "40" in r[0])

    return total, hembras, grandes


def registrar_cambio_cita(cliente_id, mascota_id, fecha_antigua, fecha_nueva):
    import sqlite3
    conn = sqlite3.connect("agenda.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS cambios_cita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            mascota_id INTEGER,
            fecha_antigua TEXT,
            fecha_nueva TEXT,
            fecha_cambio TEXT
        )
    """)

    from datetime import datetime
    c.execute("""
        INSERT INTO cambios_cita 
        (cliente_id, mascota_id, fecha_antigua, fecha_nueva, fecha_cambio)
        VALUES (?, ?, ?, ?, ?)
    """, (cliente_id, mascota_id, fecha_antigua, fecha_nueva, datetime.now().isoformat()))

    conn.commit()
    conn.close()

init_db()


