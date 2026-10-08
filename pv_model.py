import pandas as pd
import pvlib
from pvlib import location
from pvlib import irradiance


def simulate_clear_sky_production(
    latitude: float,
    longitude: float,
    surface_tilt: float = 30.0,
    surface_azimuth: float = 180.0,
    peak_power_kw: float = 1000.0,  # 1 MWp Santral
    days: int = 1,
) -> pd.DataFrame:
    """
    Belirtilen koordinat ve panel açısı için havanın tamamen berrak olduğu 
    durumdaki saatlik ideal üretim profilini (Clear-Sky) simüle eder.
    """
    site = location.Location(latitude, longitude, tz="UTC")
    
    # Bugünün saatlik zaman dilimi
    times = pd.date_range(
        start=pd.Timestamp.now(tz="UTC").floor("D"),
        periods=24 * days,
        freq="h",
        tz="UTC"
    )

    # 1. Güneş pozisyonu hesapla (Solar Zenith & Azimuth)
    solar_position = site.get_solarposition(times)

    # 2. Berrak gökyüzü ışınım modeli (Ineichen modeli)
    clearsky = site.get_clearsky(times)

    # 3. Panel yüzeyine düşen efektif ışınımı (POA Irradiance) hesapla
    poa_irradiance = irradiance.get_total_irradiance(
        surface_tilt=surface_tilt,
        surface_azimuth=surface_azimuth,
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
        dni=clearsky["dni"],
        ghi=clearsky["ghi"],
        dhi=clearsky["dhi"],
    )

    # 4. Basit fotovoltaik güç dönüşümü (1000 W/m2 STC kabulü)
    # Temiz panel üretim tahmini (kW cinsinden)
    clean_power_kw = (poa_irradiance["poa_global"] / 1000.0) * peak_power_kw

    df_result = pd.DataFrame({
        "timestamp": times,
        "poa_global_wm2": poa_irradiance["poa_global"].round(1),
        "clean_power_kw": clean_power_kw.round(1),
    })

    return df_result


if __name__ == "__main__":
    # Test: Karapınar 1 MW Santral simülasyonu
    LAT, LON = 37.71, 33.55
    df_sim = simulate_clear_sky_production(LAT, LON)
    
    print("\n--- İdeal Temiz Üretim Simülasyonu (Örnek İlk 6 Saat) ---")
    print(df_sim[df_sim["clean_power_kw"] > 0].head(6).to_string(index=False))