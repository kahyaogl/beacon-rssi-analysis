import sqlite3
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from filters.kalman_distance import FEATURE_COLUMNS, apply_kalman_series

COLUMN_RSSI_INPUT = "raw_rssi"
COLUMN_DISTANCE_REFERENCE = "distance_reference"
COLUMN_RSSI_KF = "rssi_kf"


def load_and_clean_data():
    conn = sqlite3.connect("veriler.db")
    df = pd.read_sql_query(
        """
        SELECT id, timestamp, mac_address, gateway, raw_rssi, distance_reference, ml_algorithm
        FROM veriler
        WHERE ml_algorithm = 'KALMAN_ONLY'
        ORDER BY id ASC
        """,
        conn,
    )
    conn.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df[COLUMN_RSSI_INPUT] = pd.to_numeric(df[COLUMN_RSSI_INPUT], errors="coerce")
    df[COLUMN_DISTANCE_REFERENCE] = pd.to_numeric(df[COLUMN_DISTANCE_REFERENCE], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["timestamp", "gateway", COLUMN_RSSI_INPUT, COLUMN_DISTANCE_REFERENCE])
    df = df[(df[COLUMN_DISTANCE_REFERENCE] > 0) & (df[COLUMN_RSSI_INPUT] < -20) & (df[COLUMN_RSSI_INPUT] > -95)]
    df = df.drop_duplicates(subset=["timestamp", "gateway"], keep="last")
    df = df.sort_values(["gateway", "timestamp"])

    print(f"Rows before clean: {before}")
    print(f"Rows after clean : {len(df)}")
    return df


def build_features(df):
    # Kalman filter is applied per gateway, then rolling features are built on filtered RSSI.
    df[COLUMN_RSSI_KF] = df.groupby("gateway")[COLUMN_RSSI_INPUT].transform(
        lambda s: pd.Series(apply_kalman_series(s.tolist()), index=s.index)
    )
    df["rssi_ma"] = df.groupby("gateway")[COLUMN_RSSI_KF].transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["rssi_std"] = df.groupby("gateway")[COLUMN_RSSI_KF].transform(lambda s: s.rolling(5, min_periods=1).std().fillna(0))
    df["rssi_diff"] = df.groupby("gateway")[COLUMN_RSSI_KF].transform(lambda s: s.diff().fillna(0))
    df["rssi_min"] = df.groupby("gateway")[COLUMN_RSSI_KF].transform(lambda s: s.rolling(5, min_periods=1).min())
    df["rssi_max"] = df.groupby("gateway")[COLUMN_RSSI_KF].transform(lambda s: s.rolling(5, min_periods=1).max())
    return df


def time_split(df, train_ratio=0.8):
    split_index = int(len(df) * train_ratio)
    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()
    return train_df, test_df


def train_and_evaluate():
    df = load_and_clean_data()
    df = build_features(df)
    df = df.sort_values("timestamp")

    train_df, test_df = time_split(df, train_ratio=0.8)
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[COLUMN_DISTANCE_REFERENCE]
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[COLUMN_DISTANCE_REFERENCE]

    model = RandomForestRegressor(
        n_estimators=900,
        max_depth=30,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    baseline_pred = np.full_like(y_test.values, fill_value=float(np.mean(y_train)))
    baseline_mae = mean_absolute_error(y_test, baseline_pred)

    print(f"Train rows: {len(train_df)}")
    print(f"Test rows : {len(test_df)}")
    print(f"MAE       : {mae:.6f}")
    print(f"Baseline  : {baseline_mae:.6f}")

    joblib.dump(model, "beacon_distance_model.pkl")
    print("Model kaydedildi")


if __name__ == "__main__":
    train_and_evaluate()