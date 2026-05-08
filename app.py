import sqlite3 # For database operations
import db.database as db #
import mqtt_client
import processor
import joblib
from filters.kalman_distance import apply_kalman_series, build_feature_vector
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO
import os
app = Flask(__name__)#web uygulaması için Flask framework'ünü kullanıyoruz

socketio = SocketIO( #Flask-SocketIO ile gerçek zamanlı iletişim için SocketIO nesnesi oluşturuyoruz
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)




if os.path.exists("beacon_distance_model.pkl"): #Eğer model dosyası varsa yükle, yoksa None olarak bırak
    model = joblib.load("beacon_distance_model.pkl")
else:
    model = None



@app.route('/') #Ana sayfa rotası, index.html dosyasını render eder
def index():
    return render_template('index.html')


@app.route('/api/veriler') #Verileri JSON formatında döndüren API rotası
def get_veriler():
    conn = sqlite3.connect("veriler.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT id, timestamp, mac_address, gateway, rssi,
               distance_reference, distance_ml,
               rssi_var, durum, raw_rssi, rssi_ema, rssi_kf, ml_algorithm
        FROM veriler
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(r) for r in reversed(rows)])



@app.route("/predict", methods=["POST"]) #Makine öğrenimi tahmini için API rotası, POST isteği bekler
def predict():
    data = request.json

    rssi_history = data.get("rssi_history")
    if isinstance(rssi_history, list) and len(rssi_history) > 0:#Eğer rssi_history listesi varsa, son 5 değeri al ve float'a çevir, yoksa tek bir rssi değeri kullan
        recent = [float(v) for v in rssi_history[-5:]]
    else:
        recent = [float(data["rssi"])]
    filtered = apply_kalman_series(recent)
    feature_vector = build_feature_vector(filtered)

    pred = float(model.predict(feature_vector)[0])

    return jsonify({
        "distance_ml": pred
    })



if __name__ == '__main__': #Uygulama başlatıldığında veritabanını başlat, MQTT istemcisini başlat ve işlemciyi başlat, ardından Flask uygulamasını çalıştır
    db.init_db()
    mqtt_client.start()
    processor.start(socketio)

    socketio.run(app, debug=True)