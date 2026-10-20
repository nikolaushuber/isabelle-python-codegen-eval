"""
Plot the results of bench/run.py for one or more interpreters (CPython, PyPy):

- one panel per benchmark: time against size; colour and marker = interpreter (CPython dots,
  PyPy squares), line type = side (solid = verified reference, dashed = library), shaded band =
  fastest to slowest repeat; failures are marked with a cross
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
# and a marker per interpreter, so identity never rests on colour alone
ENV_MARKERS = {"cpython": "o", "pypy": "s"}
OTHER_MARKER = "D"
INK, INK_2, INK_3, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
# line type per side
SIDES = (("reference", "-"), ("library", "--"))
ORDER = {"cpython": 0, "pypy": 1}
# matrix panels start here: a 1x1 matrix takes ~10 us, mostly call overhead and noise
MIN_MATRIX_N = 2


def env_label(results):
    name = {"cpython": "CPython", "pypy": "PyPy"}.get(results.get("interpreter"), "Python")
    version = results.get("implementation_version") or results.get("python", "")
    return f"{name} {version}".strip()


def times(bench, side):
    """size -> median seconds for one side; and the sizes where it failed."""
    ok = {r["size"]: r["seconds"] for r in bench["rows"] if r["side"] == side and r["status"] == "ok"}
    failed = [r for r in bench["rows"] if r["side"] == side and r["status"] == "failed"]
    return ok, failed


def spread(bench, side):
    """size -> (fastest, slowest) repeat for one side, where run.py recorded them."""
    return {r["size"]: (r["min_seconds"], r["max_seconds"]) for r in bench["rows"]
            if r["side"] == side and r["status"] == "ok" and "min_seconds" in r}


def ratio_label(v):
    return f"{v:,.0f}x" if v >= 10 else f"{v:.1f}x"


def size_label(size, label):
    """The size a slowdown was measured at, e.g. '30k keys' or '8x8'."""
    if label.startswith("n ("):
        return f"{size}x{size}"
    n = f"{size // 1000}k" if size >= 1000 and size % 1000 == 0 else f"{size:,}"
    return f"{n} {label}"


def dot_panel(ax, rows, groups, title, xlabel, notes=None):
    """
    Dumbbell plot on a log axis: rows = labels, groups = [(label, color, marker, values)], one per
    interpreter. The dots of a row sit on one line, joined by a thin grey bar; the smallest value's
    label goes to its left, every other label to the right of its dot. notes = optional small grey
    text under each row label.
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
    lo = min(all_values + [1]) / 1.3   # just left of the 1x line
    hi = max(all_values + [1]) * 3
    ax.set_xlim(lo, hi)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_ylim(len(rows) - 0.4, -0.6)
    if notes:   # label just above the row's line, note just below it, both right-aligned at the tick
        ax.tick_params(axis="y", length=0)
        for tick in ax.get_yticklabels():
            tick.set_va("bottom")
        for y, note in enumerate(notes):
            if note:
                ax.annotate(note, (0, y), xycoords=("axes fraction", "data"),
                            textcoords="offset points", xytext=(-3.5, -1), ha="right", va="top",
                            color=INK_3, fontsize=7.5, annotation_clip=False)
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
    from matplotlib.legend_handler import HandlerTuple
    from matplotlib.patches import Patch

    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "axes.facecolor": SURFACE,
        "figure.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    })
    envs = [(env_label(r), ENV_COLORS[i % len(ENV_COLORS)],
             ENV_MARKERS.get(r.get("interpreter"), OTHER_MARKER), r)
            for i, r in enumerate(all_results)]
    names = []
    for *_, r in envs:
        names += [b["name"] for b in r["benchmarks"] if b["name"] not in names]
    by_env = [{b["name"]: b for b in r["benchmarks"]} for *_, r in envs]

    cols = 3
    bench_rows = (len(names) + cols - 1) // cols
    fig = plt.figure(figsize=(12, 3.3 * bench_rows + 2.6), layout="constrained")
    grid = fig.add_gridspec(bench_rows + 1, cols, height_ratios=[3.3] * bench_rows + [2.6])

    for i, name in enumerate(names):
        ax = fig.add_subplot(grid[i // cols, i % cols])
        lib_name, label = None, None
        for (env, color, marker, _), benches in zip(envs, by_env):
            b = benches.get(name)
            if b is None:
                continue
            lib_name, label = b["lib_name"], b["label"]
            for side, style in SIDES:
                ok, failed = times(b, side)
                matrix = b["label"].startswith("n (")
                xs = sorted(x for x in ok if not (matrix and x < MIN_MATRIX_N))
                ys = [ok[x] for x in xs]
                ax.plot(xs, ys, color=color, linestyle=style, marker=marker, markersize=4.5,
                        linewidth=1.4)
                band = spread(b, side)
                bx = [x for x in xs if x in band]
                if bx:   # fastest to slowest repeat
                    ax.fill_between(bx, [band[x][0] for x in bx], [band[x][1] for x in bx],
                                    color=color, alpha=0.15, linewidth=0)
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
        handles = [Line2D([], [], color=INK_2, linestyle="-", label="verified reference"),
                   Line2D([], [], color=INK_2, linestyle="--", label=lib_name)]
        ax.legend(handles=handles, frameon=False, fontsize=7.5, loc="upper left")

    # slowdown of the reference against the library, per interpreter
    groups = []
    compared = {name: [] for name in names}   # size labels each row's ratios were taken at
    for (env, color, marker, _), benches in zip(envs, by_env):
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
            if common and (s := size_label(common[-1], b["label"])) not in compared[name]:
                compared[name].append(s)
        groups.append((env, color, marker, values))
    notes = [f"({' / '.join(compared[name])})" if compared[name] else None for name in names]
    dot_panel(fig.add_subplot(grid[bench_rows, :]), names, groups,
              "Slowdown of the verified reference against the library "
              "(largest size both completed)", "reference time / library time (log scale)", notes)

    fig.suptitle("Generated verified references vs Python libraries",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    # one legend for every panel, at the right end of the title line: interpreters and the band
    handles = [Line2D([], [], color=color, linestyle="none", marker=marker, label=env)
               for env, color, marker, _ in envs]
    # the band swatch is split into one part per interpreter colour
    handles.append(tuple(Patch(color=color, alpha=0.15, linewidth=0) for _, color, _, _ in envs))
    labels = [env for env, *_ in envs] + ["fastest to slowest repeat"]
    fig.legend(handles, labels, handler_map={tuple: HandlerTuple(ndivide=None, pad=0)},
               frameon=False, fontsize=9, ncol=len(handles),
               loc="upper right", bbox_to_anchor=(0.995, 0.997), borderaxespad=0)
    fig.savefig(path, dpi=150)
    print(f"wrote {path}")
    pdf = os.path.splitext(path)[0] + ".pdf"   # vector copy, for papers and slides
    if pdf != path:
        fig.savefig(pdf)
        print(f"wrote {pdf}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", nargs="*",
                   help="results files written by run.py (default: every bench/out/*/results.json)")
    p.add_argument("-o", "--output", default=os.path.join(OUT, "benchmark.png"),
                   help="image to write, plus a .pdf next to it (default bench/out/benchmark.png)")
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
