"""
Plot the results of bench/run.py for one or more interpreters (CPython, PyPy):

- one panel per benchmark: time against size, colour = interpreter, solid line with circles =
  verified reference, dashed line with squares = library; failures are marked with a cross
- the slowdown of each reference against its library, per interpreter, at the largest size both
  sides completed

    uv run python bench/plot.py                         # every bench/out/*/results.json
    uv run python bench/plot.py bench/out/pypy/results.json -o pypy.png
"""
import argparse
import glob
import json
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench", "out")

# categorical slots 1, 2, 3 of the default palette (light theme), in fixed order per interpreter
ENV_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
# and a marker per interpreter for the slowdown summary, so identity never rests on colour alone
ENV_MARKERS = ["o", "s", "D"]
# and a line width per interpreter for the benchmark panels, where line style and marker already
# distinguish reference and library
ENV_WIDTHS = [2.4, 1.1, 0.6]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SIDES = (("reference", "-", "o", "verified reference"), ("library", "--", "s", None))
ORDER = {"cpython": 0, "pypy": 1}


def env_label(results):
    name = {"cpython": "CPython", "pypy": "PyPy"}.get(results.get("interpreter"), "Python")
    version = results.get("implementation_version") or results.get("python", "")
    return f"{name} {version}".strip()


def times(bench, side):
    """size -> median seconds for one side; and the sizes where it failed."""
    ok = {r["size"]: r["seconds"] for r in bench["rows"] if r["side"] == side and r["status"] == "ok"}
    failed = [r for r in bench["rows"] if r["side"] == side and r["status"] == "failed"]
    return ok, failed


def ratio_label(v):
    return f"{v:,.0f}x" if v >= 10 else f"{v:.1f}x"


def dot_panel(ax, rows, groups, title, xlabel):
    """
    Dumbbell plot on a log axis: rows = labels, groups = [(label, color, marker, values)], one per
    interpreter. The dots of a row sit on one line, joined by a thin grey bar; the smallest value's
    label goes to its left, every other label to the right of its dot.
    """
    all_values = [v for *_, values in groups for v in values if v is not None]
    for y in range(len(rows)):
        row = [values[y] for *_, values in groups if values[y] is not None]
        if len(row) > 1:
            ax.plot([min(row), max(row)], [y, y], color=GRID, linewidth=3, zorder=2,
                    solid_capstyle="round")
    for label, color, marker, values in groups:
        ys = [y for y, v in enumerate(values) if v is not None]
        vs = [v for v in values if v is not None]
        ax.scatter(vs, ys, s=40, zorder=3, label=label, color=color, marker=marker)
        for v, y in zip(vs, ys):
            row = [vals[y] for *_, vals in groups if vals[y] is not None]
            left = len(row) > 1 and v == min(row)
            ax.annotate(ratio_label(v), (v, y), textcoords="offset points",
                        xytext=(-7, 0) if left else (7, 0), ha="right" if left else "left",
                        va="center", color=INK, fontsize=8)
    ax.axvline(1, color=INK_2, linewidth=1)
    ax.set_xscale("log")
    lo = min(all_values + [1]) / 2
    hi = max(all_values + [1]) * 3
    ax.set_xlim(lo, hi)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    ax.grid(axis="y", visible=False)
    ax.set_title(title, loc="left", fontsize=10, fontweight="bold", color=INK)
    ax.set_xlabel(xlabel)
    if len(groups) > 1:   # above the panel, on the title line: dots can sit anywhere inside
        ax.legend(frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1, 1),
                  ncol=len(groups), borderaxespad=0.2)


def plot(all_results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    })
    envs = [(env_label(r), ENV_COLORS[i % len(ENV_COLORS)], r) for i, r in enumerate(all_results)]
    names = []
    for _, _, r in envs:
        names += [b["name"] for b in r["benchmarks"] if b["name"] not in names]
    by_env = [{b["name"]: b for b in r["benchmarks"]} for _, _, r in envs]

    cols = 3
    bench_rows = (len(names) + cols - 1) // cols
    fig = plt.figure(figsize=(12, 3.3 * bench_rows + 2.6), layout="constrained")
    grid = fig.add_gridspec(bench_rows + 1, cols, height_ratios=[3.3] * bench_rows + [2.6])

    for i, name in enumerate(names):
        ax = fig.add_subplot(grid[i // cols, i % cols])
        lib_name, label = None, None
        for e, ((env, color, _), benches) in enumerate(zip(envs, by_env)):
            b = benches.get(name)
            if b is None:
                continue
            lib_name, label = b["lib_name"], b["label"]
            for side, style, marker, _ in SIDES:
                ok, failed = times(b, side)
                xs = sorted(ok)
                ys = [ok[x] for x in xs]
                ax.plot(xs, ys, color=color, linestyle=style, marker=marker, markersize=4.5,
                        linewidth=ENV_WIDTHS[e % len(ENV_WIDTHS)],
                        markerfacecolor=color if side == "reference" else SURFACE)
                for r in failed:
                    y = ys[-1] if ys else 1e-3
                    ax.plot([r["size"]], [y], marker="x", markersize=9, markeredgewidth=2, color=color)
                    ax.annotate(r["reason"], (r["size"], y), textcoords="offset points", xytext=(0, 8),
                                ha="center", color=INK_2, fontsize=8)
        ax.set_xscale("linear" if label and label.startswith("n (") else "log")
        ax.set_yscale("log")
        ax.set_title(name, loc="left", fontsize=10, fontweight="bold", color=INK)
        ax.set_xlabel(label or "")
        ax.set_ylabel("median time (s)")
        handles = [Line2D([], [], color=INK_2, linestyle="-", marker="o", label="verified reference"),
                   Line2D([], [], color=INK_2, linestyle="--", marker="s", markerfacecolor=SURFACE,
                          label=lib_name)]
        handles += [Line2D([], [], color=color, linewidth=ENV_WIDTHS[e % len(ENV_WIDTHS)], label=env)
                    for e, (env, color, _) in enumerate(envs)]
        ax.legend(handles=handles, frameon=False, fontsize=7.5, loc="upper left")

    # slowdown of the reference against the library, per interpreter
    groups = []
    for (env, color, _), benches in zip(envs, by_env):
        values = []
        for name in names:
            b = benches.get(name)
            if b is None:
                values.append(None)
                continue
            ref, _ = times(b, "reference")
            lib, _ = times(b, "library")
            common = sorted(set(ref) & set(lib))
            values.append(ref[common[-1]] / lib[common[-1]] if common else None)
        groups.append((env, color, ENV_MARKERS[len(groups) % len(ENV_MARKERS)], values))
    dot_panel(fig.add_subplot(grid[bench_rows, :]), names, groups,
              "Slowdown of the verified reference against the library "
              "(largest size both completed)", "reference time / library time (log scale)")

    fig.suptitle("Generated verified references vs Python libraries: "
                 + ", ".join(env for env, _, _ in envs),
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150)
    print(f"wrote {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", nargs="*",
                   help="results files written by run.py (default: every bench/out/*/results.json)")
    p.add_argument("-o", "--output", default=os.path.join(OUT, "benchmark.png"),
                   help="image to write (default bench/out/benchmark.png)")
    args = p.parse_args()
    paths = args.results or sorted(glob.glob(os.path.join(OUT, "*", "results.json")))
    if not paths:
        p.error("no results found; run bench/run.py first")
    all_results = []
    for path in paths:
        with open(path) as f:
            all_results.append(json.load(f))
    all_results.sort(key=lambda r: ORDER.get(r.get("interpreter"), len(ORDER)))
    plot(all_results, args.output)


if __name__ == "__main__":
    main()
