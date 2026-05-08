from collections import deque
import numpy as np

FEATURE_COLUMNS = ["rssi_kf", "rssi_ma", "rssi_std", "rssi_diff", "rssi_min", "rssi_max"]


class KalmanRSSIFilter:
    def __init__(self, process_noise=5, measurement_noise=0.3):
        self.process_noise = float(process_noise)
        self.measurement_noise = float(measurement_noise)
        self.estimate = None
        self.error_cov = 1.0

    def update(self, measurement):
        measurement = float(measurement)
        if self.estimate is None:#İlk ölçüm geldiğinde tahmin ve hata kovaryansı başlatılır
            self.estimate = measurement #İlk ölçüm tahmin olarak alınır
            return self.estimate

        pred_estimate = self.estimate
        pred_error_cov = self.error_cov + self.process_noise #Tahmin edilen hata kovaryansı, önceki hata kovaryansı ve süreç gürültüsünün toplamıdır
        kalman_gain = pred_error_cov / (pred_error_cov + self.measurement_noise) #Kalman kazancı, tahmin edilen hata kovaryansı ile ölçüm gürültüsü arasındaki orandır

        self.estimate = pred_estimate + kalman_gain * (measurement - pred_estimate) #Güncellenmiş tahmin, önceki tahmin ve ölçüm arasındaki farkın kalman kazancı ile çarpılmasıyla elde edilir
        self.error_cov = (1.0 - kalman_gain) * pred_error_cov #Güncellenmiş hata kovaryansı, tahmin edilen hata kovaryansı ve kalman kazancının çarpımının 1 eksiği ile çarpılmasıyla elde edilir
        return self.estimate#Güncellenmiş tahmin değeri döndürülür


def apply_kalman_series(values, process_noise=5, measurement_noise=0.3):#Verilen değerler listesine Kalman filtresi uygulanır, her değer için güncellenmiş tahminler döndürülür
    filt = KalmanRSSIFilter(process_noise=process_noise, measurement_noise=measurement_noise)
    return [filt.update(v) for v in values]


def build_feature_vector(filtered_window): #Kalman filtresi uygulanmış değerler listesi üzerinden özellik vektörü oluşturulur, bu vektör makine öğrenimi modeline girdi olarak verilir
    if not filtered_window: #boş liste gelirse hatalı durum oluşmaması için kontrol edilir
        raise ValueError("filtered_window cannot be empty")

    arr = np.array(filtered_window, dtype=float)
    rssi_kf = float(arr[-1])
    rssi_ma = float(np.mean(arr))
    rssi_std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    rssi_diff = float(arr[-1] - arr[-2]) if len(arr) > 1 else 0.0 #Son iki değerin farkı, tek değer varsa 0 olarak alınır
    rssi_min = float(np.min(arr)) 
    rssi_max = float(np.max(arr))
    return np.array([[rssi_kf, rssi_ma, rssi_std, rssi_diff, rssi_min, rssi_max]])


def update_window(window_map, key, value, maxlen=5):
    if key not in window_map:
        window_map[key] = deque(maxlen=maxlen)
    window_map[key].append(float(value))
    return list(window_map[key])
