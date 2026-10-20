"""
Plot the results of bench/run.py: time against size for each benchmark (verified reference vs
library, failures marked with a cross), plus the slowdown of each reference at the largest size
both sides completed.

    uv run python bench/plot.py                          # bench/out/results.json -> benchmark.png
    uv run python bench/plot.py results.json -o out.png
"""
import argparse
import json
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench", "out")

REF_COLOR, LIB_COLOR = "#2a78d6", "#eb6834"         # categorical slots 1 and 2 (light theme)
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def plot(results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    })
    benches = results["benchmarks"]
    cols = 3
    rows = (len(benches) + cols - 1) // cols + 1                       # + summary row
    fig = plt.figure(figsize=(12, 3.3 * rows), layout="constrained")
    grid = fig.add_gridspec(rows, cols)
    slowdowns = []

    for i, b in enumerate(benches):
        ax = fig.add_subplot(grid[i // cols, i % cols])
        series = {}
        for side, color, marker, label in (("reference", REF_COLOR, "o", "verified reference"),
                                           ("library", LIB_COLOR, "s", b["lib_name"])):
            ok = [r for r in b["rows"] if r["side"] == side and r["status"] == "ok"]
            xs, ys = [r["size"] for r in ok], [r["seconds"] for r in ok]
            series[side] = dict(zip(xs, ys))
            ax.plot(xs, ys, color=color, marker=marker, markersize=5, linewidth=2, label=label)
            for r in b["rows"]:
                if r["side"] == side and r["status"] == "failed":
                    y = ys[-1] if ys else 1e-3
                    ax.plot([r["size"]], [y], marker="x", markersize=9, markeredgewidth=2, color=color)
                    ax.annotate(r["reason"], (r["size"], y), textcoords="offset points", xytext=(0, 8),
                                ha="center", color=INK_2, fontsize=8)
        ax.set_xscale("log" if b["label"] != "n (n x n matrix)" else "linear")
        ax.set_yscale("log")
        ax.set_title(b["name"], loc="left", fontsize=10, fontweight="bold", color=INK)
        ax.set_xlabel(b["label"])
        ax.set_ylabel("median time (s)")
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        common = sorted(set(series["reference"]) & set(series["library"]))
        if common:
            n = common[-1]
            slowdowns.append((b["name"], n, series["reference"][n] / series["library"][n]))

    ax = fig.add_subplot(grid[rows - 1, :])
    names = [f"{name}  (size {n})" for name, n, _ in slowdowns]
    values = [s for _, _, s in slowdowns]
    # dots, not bars: on a log axis a bar's length depends on an arbitrary baseline
    ax.scatter(values, names, color=REF_COLOR, s=40, zorder=3)
    for y, v in enumerate(values):
        ax.annotate(f"{v:,.0f}x" if v >= 10 else f"{v:.1f}x", (v, y),
                    textcoords="offset points", xytext=(7, 0), va="center", color=INK, fontsize=8)
    ax.axvline(1, color=INK_2, linewidth=1)
    ax.annotate("same speed", (1, len(values) - 0.5), textcoords="offset points", xytext=(4, 0),
                color=INK_2, fontsize=8, va="center")
    ax.set_xscale("log")
    ax.set_xlim(0.5, max(values + [1]) * 3)
    ax.set_ylim(len(values) - 0.4, -0.6)
    ax.grid(axis="y", visible=False)
    ax.set_title("Slowdown of the verified reference at the largest size both sides completed",
                 loc="left", fontsize=10, fontweight="bold", color=INK)
    ax.set_xlabel("reference time / library time (log scale)")
    fig.suptitle("Generated verified references vs Python libraries", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150)
    print(f"wrote {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", nargs="?", default=os.path.join(OUT, "results.json"),
                   help="results file written by run.py (default bench/out/results.json)")
    p.add_argument("-o", "--output", help="image to write (default: benchmark.png next to the results)")
    args = p.parse_args()
    with open(args.results) as f:
        results = json.load(f)
    plot(results, args.output or os.path.join(os.path.dirname(os.path.abspath(args.results)), "benchmark.png"))


if __name__ == "__main__":
    main()
