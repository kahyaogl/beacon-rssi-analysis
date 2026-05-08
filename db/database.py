import sqlite3

conn = sqlite3.connect("veriler.db")
c = conn.cursor()



conn.commit()
conn.close()
def init_db():
    conn = sqlite3.connect("veriler.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS veriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            mac_address TEXT,
            gateway TEXT,
            rssi REAL,
            distance_reference REAL,
            distance_ml REAL,
            rssi_var REAL,
            durum TEXT,
            raw_rssi REAL,
            rssi_ema REAL,
            rssi_kf REAL,
            ml_algorithm TEXT
        )
    ''')

    # Backward-compatible schema migration for old column names.
    c.execute("PRAGMA table_info(veriler)")
    columns = [row[1] for row in c.fetchall()]
    if "distance_espresense" in columns and "distance_reference" not in columns:
        c.execute("ALTER TABLE veriler RENAME COLUMN distance_espresense TO distance_reference")
    if "rssiVar" in columns and "rssi_var" not in columns:
        c.execute("ALTER TABLE veriler RENAME COLUMN rssiVar TO rssi_var")
    if "res_ema" in columns and "rssi_ema" not in columns:
        c.execute("ALTER TABLE veriler RENAME COLUMN res_ema TO rssi_ema")

    c.execute("PRAGMA table_info(veriler)")
    columns = [row[1] for row in c.fetchall()]
    if "ml_algorithm" not in columns:
        c.execute("ALTER TABLE veriler ADD COLUMN ml_algorithm TEXT")
    if "rssi_kf" not in columns:
        c.execute("ALTER TABLE veriler ADD COLUMN rssi_kf REAL")
    conn.commit()
    conn.close()

def save_to_db(data):
    try:
        conn = sqlite3.connect("veriler.db")
        c = conn.cursor()

        c.execute('''
            INSERT INTO veriler (
                timestamp, mac_address, gateway, rssi,
                distance_reference,
                distance_ml,
                rssi_var, durum,
                raw_rssi, rssi_ema, rssi_kf, ml_algorithm
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data["timestamp"],
            data["mac_address"],
            data["gateway"],
            data["rssi"],
            data["distance_reference"],
            data["distance_ml"],
            data["rssi_var"],
            data["durum"],
            data["raw_rssi"],
            data["rssi_ema"],
            data["rssi_kf"],
            data.get("ml_algorithm")
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print("DB ERROR:", e)
        
