import pytest
from decision_engine import CleaningEconomics, calculate_cleaning_roi
from benchmark_engine import generate_benchmark_dataset, calculate_validation_metrics


def test_decision_engine_logic():
    # Yüksek yağış ihtimali olduğunda karar BEKLE olmalı
    econ = CleaningEconomics(washing_cost_usd=1500.0, current_soiling_ratio=0.05)
    result = calculate_cleaning_roi(rain_probability_pct=80.0, days_until_rain=2, economics=econ)
    assert result["should_wash"] is False
    assert result["expected_net_gain_usd"] < 0


def test_benchmark_metrics():
    # Sentetik benchmark verisinin metrik hesaplaması kontrolü
    df = generate_benchmark_dataset(days=30)
    metrics = calculate_validation_metrics(df)
    assert 0.0 <= metrics.r_squared <= 1.0
    assert metrics.rmse >= 0.0