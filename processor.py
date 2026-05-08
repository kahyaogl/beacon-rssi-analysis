import os
from utils.queue_manager import data_queue
import joblib
from db.database import save_to_db
import json
import threading
from queue import Queue
from datetime import datetime, timezone
from filters.kalman_distance import KalmanRSSIFilter, build_feature_vector, update_window

# =========================
# GLOBALS
# =========================
kalman_map = {}
rssi_kf_window_map = {}
sample_count_map = {}
db_queue = Queue()

A_REF = -53.5
N_VAL = 2.8
ML_ALGORITHM = "RandomForestRegressor+Kalman"
WARMUP_SAMPLE_COUNT = 20
ENABLE_LIVE_ML = False

# ✅ MODEL LOAD (optional in Kalman-only mode)
if os.path.exists("beacon_distance_model.pkl"):
    model = joblib.load("beacon_distance_model.pkl")
else:
    model = None


# =========================
# DB WORKER
# =========================
def db_worker():
    while True:
        clean_data = db_queue.get()
        try:
            save_to_db(clean_data)
        except Exception as e:
            print(f"[processor] DB yazma hatasi: {e}")
        finally:
            db_queue.task_done()


# =========================
# MAIN PROCESS
# =========================
def process(socketio):
    while True:
        topic, payload = data_queue.get()

        try:
            data = json.loads(payload)

            gateway = topic.split("/")[-1]
            raw_rssi = float(data.get("rssi", 0))
            rssi_var = float(data.get("rssi_var", data.get("rssiVar", 0)))

            if gateway not in kalman_map:
                kalman_map[gateway] = KalmanRSSIFilter()
            rssi_kf = kalman_map[gateway].update(raw_rssi)#Gateway'e özel Kalman filtresi uygulaması
            filtered_window = update_window(rssi_kf_window_map, gateway, rssi_kf, maxlen=5)#Gateway'e özel Kalman filtresi çıktıları için kaydırmalı pencere güncellemesi
            sample_count_map[gateway] = sample_count_map.get(gateway, 0) + 1 #Gateway'e özel örnek sayısı takibi

            # =========================
            # CLASSIC DISTANCE
            # =========================
            distance_kf = 10 ** ((A_REF - rssi_kf) / (10 * N_VAL))
            X = build_feature_vector(filtered_window) # ml için input

            # ✅ KALMAN-ONLY COLLECTION MODE (no live ML prediction)
            is_ml_ready = ENABLE_LIVE_ML and (sample_count_map[gateway] >= WARMUP_SAMPLE_COUNT) #ML tahminlerinin başlaması için yeterli örnek sayısına ulaşıldı mı kontrolü
            distance_ml = float(model.predict(X)[0]) if (is_ml_ready and model is not None) else None#ML tahmini, model hazır ve yeterli örnek varsa yapılır, aksi halde None olarak bırakılır

            # =========================
            # DURUM
            # =========================
            durum = "TEMİZ VERİ" if rssi_var <= 15 else "YÜKSEK VARYANS"

            # =========================
            # CLEAN DATA
            # =========================
            clean_data = {
                "timestamp": data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                "mac_address": data.get("mac"),
                "gateway": gateway,
                "rssi": raw_rssi,
                "rssi_ema": rssi_kf,
                "rssi_kf": rssi_kf,

                "distance_reference": data.get("distance", 0),
                "distance_ml": distance_ml,
                "distance_ema": distance_kf,

                "rssi_var": rssi_var,
                "durum": durum,
                "raw_rssi": raw_rssi,
                "ml_algorithm": ML_ALGORITHM if is_ml_ready else "KALMAN_ONLY",
                "ml_ready": is_ml_ready,
                "sample_count": sample_count_map[gateway],
            }

            # =========================
            # SOCKET (REALTIME)
            # =========================
            socketio.emit("rssi_update", clean_data)

            # =========================
            # DB WRITE
            # =========================
            db_queue.put(clean_data)

        except Exception as e:
            print(f"[processor] paket isleme hatasi topic={topic}: {e}")


# =========================
# START
# =========================
def start(socketio):
    db_t = threading.Thread(target=db_worker)
    db_t.daemon = True
    db_t.start()

    t = threading.Thread(target=process, args=(socketio,))
    t.daemon = True
    t.start()