"""Load and analyse the UCI household electric power consumption data."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler


MEASUREMENTS = [
    "Global_active_power",
    "Global_reactive_power",
    "Voltage",
    "Global_intensity",
    "Sub_metering_1",
    "Sub_metering_2",
    "Sub_metering_3",
]

# Avoid adding Total_Wh or the residual to the same model as their components.
CLUSTER_FEATURES = [
    "Global_active_power",
    "Global_reactive_power",
    "Voltage",
    "Sub_metering_1",
    "Sub_metering_2",
    "Sub_metering_3",
]


def load_power_data(path: str | Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Read one-minute observations, remove incomplete rows, and derive Wh values.

    Dropping incomplete minutes is explicit: filling across time gaps would invent
    readings. Aggregated energy therefore covers observed, complete minutes only.
    """
    raw = pd.read_csv(path, sep=";", na_values="?", low_memory=False)
    required = {"Date", "Time", *MEASUREMENTS}
    missing_columns = required.difference(raw.columns)
    if missing_columns:
        raise ValueError(f"Missing dataset columns: {sorted(missing_columns)}")

    timestamps = pd.to_datetime(
        raw["Date"] + " " + raw["Time"],
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )
    readings = raw[MEASUREMENTS].apply(pd.to_numeric, errors="coerce")
    readings.index = pd.DatetimeIndex(timestamps, name="timestamp")
    original_count = len(readings)
    readings = readings.loc[~readings.index.isna()].dropna(subset=MEASUREMENTS)
    readings = readings.sort_index()
    if readings.empty:
        raise ValueError("No complete observations were found in the dataset")

    readings["Total_Wh"] = readings["Global_active_power"] * 1000 / 60
    readings["Other_Wh"] = readings["Total_Wh"] - readings[
        ["Sub_metering_1", "Sub_metering_2", "Sub_metering_3"]
    ].sum(axis=1)
    stats = {
        "raw_rows": original_count,
        "complete_rows": len(readings),
        "negative_residual_rows": int((readings["Other_Wh"] < 0).sum()),
    }
    return readings, stats


def monthly_energy(readings: pd.DataFrame) -> pd.DataFrame:
    """Sum measured one-minute Wh into monthly kWh and report coverage."""
    energy_columns = [
        "Sub_metering_1", "Sub_metering_2", "Sub_metering_3", "Other_Wh", "Total_Wh"
    ]
    monthly = readings[energy_columns].resample("MS").sum() / 1000
    monthly = monthly.rename(columns={
        "Sub_metering_1": "Sub_metering_1_kWh",
        "Sub_metering_2": "Sub_metering_2_kWh",
        "Sub_metering_3": "Sub_metering_3_kWh",
        "Other_Wh": "Other_kWh",
        "Total_Wh": "Total_kWh",
    })
    monthly["observed_minutes"] = readings["Total_Wh"].resample("MS").count()
    monthly["calendar_minutes"] = monthly.index.days_in_month * 24 * 60
    monthly["coverage"] = monthly["observed_minutes"] / monthly["calendar_minutes"]
    return monthly


def cluster_sample(
    readings: pd.DataFrame, sample_size: int = 5000, random_state: int = 42
) -> tuple[pd.DataFrame, np.ndarray]:
    """Select reproducible observations and scale only the chosen model features."""
    if sample_size < 2:
        raise ValueError("sample_size must be at least 2")
    sample = readings.sample(n=min(sample_size, len(readings)), random_state=random_state).sort_index()
    scaled = StandardScaler().fit_transform(sample[CLUSTER_FEATURES])
    return sample, scaled


def compare_clusters(
    scaled: np.ndarray, n_clusters: int = 5, dbscan_eps: float = 1.5
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Fit three algorithms on identical inputs and score non-noise clusters."""
    if len(scaled) < n_clusters:
        raise ValueError("Need at least n_clusters observations")
    models = {
        "K-Means": KMeans(n_clusters=n_clusters, n_init=10, random_state=42),
        "Hierarchical": AgglomerativeClustering(n_clusters=n_clusters, linkage="ward"),
        "DBSCAN": DBSCAN(eps=dbscan_eps, min_samples=10),
    }
    results = []
    labels_by_model = {}
    for name, model in models.items():
        labels = model.fit_predict(scaled)
        labels_by_model[name] = labels
        included = labels != -1
        evaluated = labels[included]
        cluster_count = len(np.unique(evaluated))
        valid = 2 <= cluster_count < len(evaluated)
        results.append({
            "model": name,
            "clusters": cluster_count,
            "noise_fraction": float(np.mean(~included)),
            "silhouette": silhouette_score(
                scaled[included], evaluated, sample_size=min(1000, len(evaluated)), random_state=42
            ) if valid else np.nan,
            "davies_bouldin": davies_bouldin_score(scaled[included], evaluated) if valid else np.nan,
        })
    return pd.DataFrame(results).set_index("model"), labels_by_model
