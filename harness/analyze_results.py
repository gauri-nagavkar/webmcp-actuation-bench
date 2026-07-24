"""
Analyze harness/results/trials.jsonl and produce a summary table + chart.

Usage:
    python harness/analyze_results.py
"""
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

RESULTS_PATH = Path(__file__).parent / "results" / "trials.jsonl"
OUT_DIR = Path(__file__).parent / "results"


def load_results():
    rows = []
    with open(RESULTS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def main():
    df = load_results()
    if df.empty:
        print("No results found. Run scripted_reference_trial.py or run_benchmark.py first.")
        return

    print(f"Loaded {len(df)} trial rows from {RESULTS_PATH}\n")

    scripted = df[df["provider"] == "scripted_reference"]
    llm = df[df["provider"] != "scripted_reference"]

    if not scripted.empty:
        print("=== Scripted reference (mechanical floor, NOT LLM-driven) ===")
        print(scripted[["variant", "steps_taken", "success", "elapsed_seconds"]].to_string(index=False))
        print()

    if not llm.empty:
        print("=== LLM-driven agent trials ===")
        summary = llm.groupby("variant").agg(
            trials=("trial_id", "count"),
            success_rate=("success", "mean"),
            avg_steps=("steps_taken", "mean"),
            avg_tokens=("total_tokens", "mean"),
            avg_seconds=("elapsed_seconds", "mean"),
        )
        print(summary.to_string())
        print()

        # Chart: success rate + avg steps side by side
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        summary["success_rate"].plot(kind="bar", ax=axes[0], color=["#d93025", "#188038"])
        axes[0].set_title("Task success rate")
        axes[0].set_ylim(0, 1)
        axes[0].set_ylabel("Success rate")

        summary["avg_steps"].plot(kind="bar", ax=axes[1], color=["#d93025", "#188038"])
        axes[1].set_title("Avg. steps/tool-calls to complete")
        axes[1].set_ylabel("Steps")

        plt.tight_layout()
        chart_path = OUT_DIR / "llm_benchmark_chart.png"
        plt.savefig(chart_path, dpi=150)
        print(f"Chart saved to {chart_path}")
    else:
        print("No LLM-driven trials yet -- run harness/run_benchmark.py with an API key set to generate them.")

    # Always produce the scripted-reference chart too (mechanical floor),
    # since that's real data available without any API key.
    if not scripted.empty:
        fig, ax = plt.subplots(figsize=(5, 4))
        scripted.set_index("variant")["steps_taken"].plot(kind="bar", ax=ax, color=["#d93025", "#188038"])
        ax.set_title("Mechanical action count to complete task\n(scripted, perfect-knowledge floor)")
        ax.set_ylabel("Discrete actions / tool calls")
        plt.tight_layout()
        chart_path = OUT_DIR / "scripted_reference_chart.png"
        plt.savefig(chart_path, dpi=150)
        print(f"Chart saved to {chart_path}")


if __name__ == "__main__":
    main()
