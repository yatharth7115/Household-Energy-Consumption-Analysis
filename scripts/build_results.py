"""Regenerate result tables and figures from the local UCI dataset."""

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.energy_analysis import CLUSTER_FEATURES, cluster_sample, compare_clusters, load_power_data, monthly_energy


def save_monthly_figure(monthly, destination: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, layout="constrained")
    axes[0].plot(monthly.index, monthly["Total_kWh"], color="#1263a6", linewidth=2)
    axes[0].set_title("Observed household electricity by month")
    axes[0].set_ylabel("Energy (kWh)")
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].plot(monthly.index, monthly["coverage"] * 100, color="#ce6b19", linewidth=2)
    axes[1].set_ylabel("Complete minutes (%)")
    axes[1].set_xlabel("Month")
    axes[1].set_ylim(0, 105)
    axes[1].grid(axis="y", alpha=0.25)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def save_cluster_figure(scaled: np.ndarray, labels_by_model: dict, destination: Path) -> None:
    projection = PCA(n_components=2).fit_transform(scaled)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), layout="constrained")
    palette = plt.get_cmap("tab10")
    for ax, (name, labels) in zip(axes, labels_by_model.items()):
        for cluster in np.unique(labels):
            selected = labels == cluster
            color = "#777777" if cluster == -1 else palette(int(cluster) % 10)
            label = "Noise" if cluster == -1 else f"Cluster {cluster}"
            ax.scatter(projection[selected, 0], projection[selected, 1], s=5, alpha=0.55, c=[color], label=label)
        ax.set_title(name)
        ax.set_xlabel("PC 1")
        ax.set_ylabel("PC 2")
        ax.legend(markerscale=2, fontsize=7, loc="best")
    fig.suptitle("Clustering on six scaled features (PCA shown only for display)")
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def build_results(data_path: Path, output_dir: Path) -> None:
    readings, counts = load_power_data(data_path)
    monthly = monthly_energy(readings)
    sample, scaled = cluster_sample(readings, sample_size=5000, random_state=42)
    scores, labels_by_model = compare_clusters(scaled, n_clusters=5, dbscan_eps=1.5)

    output_dir.mkdir(parents=True, exist_ok=True)
    figures = output_dir / "figures"
    figures.mkdir(exist_ok=True)
    monthly.to_csv(output_dir / "monthly_energy.csv", index_label="month", float_format="%.6f")
    scores.to_csv(output_dir / "clustering_scores.csv", float_format="%.6f")

    profile = sample[CLUSTER_FEATURES].copy()
    profile["cluster"] = labels_by_model["K-Means"]
    means = profile.groupby("cluster").mean()
    means.insert(0, "sample_minutes", profile.groupby("cluster").size())
    means.insert(1, "sample_fraction", means["sample_minutes"] / len(sample))
    means.to_csv(output_dir / "kmeans_profile.csv", float_format="%.6f")

    summary = {
        **counts,
        "first_timestamp": readings.index.min().isoformat(),
        "last_timestamp": readings.index.max().isoformat(),
        "calendar_months": len(monthly),
        "total_observed_kwh": round(float(monthly["Total_kWh"].sum()), 6),
        "sample_size": len(sample),
        "random_state": 42,
        "kmeans_and_hierarchical_clusters": 5,
        "dbscan_eps": 1.5,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    save_monthly_figure(monthly, figures / "monthly_energy.png")
    save_cluster_figure(scaled, labels_by_model, figures / "cluster_comparison.png")
    print(f"Wrote result tables and figures to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("ENERGY_DATA_PATH", ROOT / "data" / "household_power_consumption.txt")))
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    if not args.data.is_file():
        parser.error(f"Dataset missing: {args.data}. Run python scripts/download_data.py first.")
    build_results(args.data, args.output)
