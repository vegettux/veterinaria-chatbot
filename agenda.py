import sqlite3
from datetime import datetime
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
DIAS_OPERATIVOS = [0, 1, 2, 3]

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            cliente_id INTEGER,
            nombre TEXT NOT NULL,
            especie TEXT NOT NULL,
            sexo TEXT,
            peso REAL,
            edad INTEGER,
            tiene_microchip INTEGER DEFAULT 0,
            tiene_vacuna_rabia INTEGER DEFAULT 0,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente_id INTEGER,
            mascota_id INTEGER,
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

def buscar_cliente_por_dni(dni: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM clientes WHERE dni = ?", (dni.upper(),))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "nombre": row[1], "dni": row[2],
                "telefono": row[3], "email": row[4], "direccion": row[5]}
    return None

def buscar_cliente_por_nombre(nombre: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM clientes WHERE nombre LIKE ?", (f"%{nombre}%",))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "nombre": row[1], "dni": row[2],
                "telefono": row[3], "email": row[4], "direccion": row[5]}
    return None

def registrar_cliente(nombre: str, dni: str, telefono: str,
                      email: str, direccion: str) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO clientes (nombre, dni, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, dni.upper(), telefono, email, direccion))
        cliente_id = c.lastrowid
        conn.commit()
        conn.close()
        return True, str(cliente_id)
    except sqlite3.IntegrityError:
        return False, "Ya existe un cliente con ese DNI."

def registrar_mascota(cliente_id: int, nombre: str, especie: str,
                      sexo: str, peso: float, edad: int,
                      microchip: bool, vacuna_rabia: bool) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO mascotas (cliente_id, nombre, especie, sexo, peso, edad,
                              tiene_microchip, tiene_vacuna_rabia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (cliente_id, nombre, especie, sexo, peso, edad,
          int(microchip), int(vacuna_rabia)))
    mascota_id = c.lastrowid
    conn.commit()
    conn.close()
    return mascota_id

def es_dia_operativo(fecha_str: str) -> tuple[bool, str]:
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        if fecha.weekday() not in DIAS_OPERATIVOS:
            dias = ["lunes","martes","miércoles","jueves",
                    "viernes","sábado","domingo"]
            return False, f"El {dias[fecha.weekday()]} no es día operativo. Las cirugías son de lunes a jueves."
        return True, ""
    except ValueError:
        return False, "Formato de fecha incorrecto."

def get_minutos_ocupados(fecha_str: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT SUM(minutos) FROM citas WHERE fecha = ?", (fecha_str,))
    resultado = c.fetchone()[0]
    conn.close()
    return resultado or 0

def get_perros_dia(fecha_str: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM citas c
                 JOIN mascotas m ON c.mascota_id = m.id
                 WHERE c.fecha = ? AND m.especie = 'perro'""", (fecha_str,))
    resultado = c.fetchone()[0]
    conn.close()
    return resultado or 0

def verificar_disponibilidad(fecha_str: str,
                              tipo_cirugia: str) -> tuple[bool, str]:
    operativo, msg = es_dia_operativo(fecha_str)
    if not operativo:
        return False, msg
    minutos = TIEMPOS_CIRUGIA.get(tipo_cirugia, 30)
    ocupados = get_minutos_ocupados(fecha_str)
    if ocupados + minutos > CAPACIDAD_DIARIA:
        return False, f"No hay disponibilidad. Solo quedan {CAPACIDAD_DIARIA - ocupados} min."
    if "perro" in tipo_cirugia or "perra" in tipo_cirugia:
        if get_perros_dia(fecha_str) >= MAX_PERROS_DIA:
            return False, "Ese día ya tiene 2 perros programados."
    return True, "Disponible"

def reservar_cita(fecha_str: str, cliente_id: int, mascota_id: int,
                  tipo_cirugia: str) -> tuple[bool, str]:
    disponible, msg = verificar_disponibilidad(fecha_str, tipo_cirugia)
    if not disponible:
        return False, msg
    minutos = TIEMPOS_CIRUGIA.get(tipo_cirugia, 30)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO citas (fecha, cliente_id, mascota_id, tipo_cirugia, minutos)
        VALUES (?, ?, ?, ?, ?)
    """, (fecha_str, cliente_id, mascota_id, tipo_cirugia, minutos))
    conn.commit()
    conn.close()
    return True, "Cita reservada correctamente."

def listar_citas(fecha_str: Optional[str] = None) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if fecha_str:
        c.execute("SELECT * FROM citas WHERE fecha = ? ORDER BY fecha",
                  (fecha_str,))
    else:
        c.execute("SELECT * FROM citas ORDER BY fecha")
    citas = c.fetchall()
    conn.close()
    return citas

init_db()