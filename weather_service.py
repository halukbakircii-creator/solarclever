from typing import Tuple
import pandas as pd
import requests

ENSEMBLE_API_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
SIGNIFICANT_RAIN_THRESHOLD_MM = 1.0


def fetch_weather_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Open-Meteo Ensemble servisinden ham yağış tahminini çeker."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
        "models": "gfs_seamless",
        "forecast_days": days,
    }
    response = requests.get(ENSEMBLE_API_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_ensemble_dataframe(raw_data: dict) -> pd.DataFrame:
    """Ham API verisini düzenli DataFrame tablosuna dönüştürür."""
    hourly_data = raw_data.get("hourly", {})
    timestamps = hourly_data.get("time", [])

    df = pd.DataFrame({"timestamp": pd.to_datetime(timestamps)})
    for key, values in hourly_data.items():
        if key.startswith("precipitation_member"):
            df[key] = values
    return df


def calculate_rain_probability(df_forecast: pd.DataFrame) -> float:
    """Tüm senaryolar içinde yağış eşiğini aşanların yüzdesini hesaplar."""
    member_cols = [c for c in df_forecast.columns if c.startswith("precipitation_member")]
    total_rain_per_member = df_forecast[member_cols].sum()
    probability = (total_rain_per_member > SIGNIFICANT_RAIN_THRESHOLD_MM).mean() * 100
    return round(float(probability), 1)


def get_rain_risk(lat: float, lon: float) -> Tuple[pd.DataFrame, float]:
    """Koordinata göre yağış riskini ve senaryoları döndürür."""
    raw = fetch_weather_forecast(lat, lon)
    df = parse_ensemble_dataframe(raw)
    prob = calculate_rain_probability(df)
    return df, prob