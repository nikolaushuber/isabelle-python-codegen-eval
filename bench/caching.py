"""
Benchmark the impact of caching in the generated code: every harness is exported twice, with and
without `python_cache`, and bench/run.py is run against both.

`python_cache` (on by default in the code generator) memoises values and instances without
dictionary arguments with @functools.cache. `python_tail_calls`, which prints self tail calls as
loops, is on in both builds: it is not an optimisation but what keeps deep recursion under
Python's recursion limit, so it is part of the translation being measured, not a variable.

| variant    | python_cache | python_tail_calls |
|------------|--------------|-------------------|
| `no_cache` | false        | true              |
| `cache`    | true         | true              |

Steps (default: all three):

    uv run python bench/caching.py build     # 2 Isabelle builds, ~1 min each
    uv run python bench/caching.py run       # bench/run.py per variant, under this interpreter
    uv run python bench/caching.py report    # tables and plots from the results

Output:

    bench/out/caching/generated/<variant>/<folder>/   generated code of each variant
    bench/out/caching/<interpreter>/<variant>/results.json
    bench/out/caching/<interpreter>/summary.md        speedup with 95 % intervals, every size
    bench/out/caching/<interpreter>/caching.tex       the speedups as a booktabs tabular
    bench/out/caching/<interpreter>/caching.png       speedup per benchmark at its largest size
    bench/out/caching/<interpreter>/caching-sizes.png median time of both variants against size
                                                      (both plots also as .pdf; need matplotlib)

`build` leaves */generated/ as it found it. Arguments after `--` go to bench/run.py, e.g.
`bench/caching.py run -- --quick --only smith`. Under PyPy, build once with CPython and then
`make bench-caching-pypy`; `report` reads every interpreter's results.
"""
import argparse
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bench", "out", "caching")
GENERATED = os.path.join(OUT, "generated")
INTERPRETER = platform.python_implementation().lower()

# palette and helpers shared with the main benchmark plot (bench/plot.py imports matplotlib only
# inside its plot function, so this works under PyPy too)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot as benchplot  # noqa: E402

# variant -> python_cache; python_tail_calls is on in both
VARIANTS = {"no_cache": False, "cache": True}
BOOTSTRAP = 2000


def folders():
    """The harness folders listed in ROOTS."""
    with open(os.path.join(ROOT, "ROOTS")) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


# ---- build ----

def build(variants):
    isabelle = os.environ.get("ISABELLE", "isabelle")
    names = folders()
    saved = tempfile.mkdtemp(prefix="generated-")
    # keep the current */generated/, so the tests still see what they saw before
    for d in names:
        src = os.path.join(ROOT, d, "generated")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(saved, d))
    try:
        for v in variants:
            cache = "true" if VARIANTS[v] else "false"
            cmd = [isabelle, "build", "-c", "-D", ".",
                   "-o", f"python_cache={cache}", "-o", "python_tail_calls=true"]
            print(f"== build {v}: {' '.join(cmd)}", flush=True)
            subprocess.run(cmd, cwd=ROOT, check=True)
            dest = os.path.join(GENERATED, v)
            shutil.rmtree(dest, ignore_errors=True)
            for d in names:
                shutil.copytree(os.path.join(ROOT, d, "generated"), os.path.join(dest, d))
    finally:
        for d in names:
            dst = os.path.join(ROOT, d, "generated")
            if os.path.isdir(os.path.join(saved, d)):
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(os.path.join(saved, d), dst)
        shutil.rmtree(saved, ignore_errors=True)


# ---- run ----

def run(variants, run_args):
    for v in variants:
        gen = os.path.join(GENERATED, v)
        if not os.path.isdir(gen):
            sys.exit(f"{gen} missing: run `bench/caching.py build` first")
        cmd = [sys.executable, os.path.join(ROOT, "bench", "run.py"), "--generated", gen,
               "--out", os.path.join(OUT, INTERPRETER, v), "--label", v, *run_args]
        print(f"== run {v}", flush=True)
        # one process per variant: the variants' modules share their names
        subprocess.run(cmd, cwd=ROOT, check=True)


# ---- report ----

def load_results(interp_dir):
    """variant -> {benchmark name -> benchmark}, for the variants that have results."""
    out = {}
    for v in VARIANTS:
        path = os.path.join(interp_dir, v, "results.json")
        if os.path.exists(path):
            with open(path) as f:
                out[v] = {b["name"]: b for b in json.load(f)["benchmarks"]}
    return out


def reference_ok(bench):
    """size -> the reference's row, for the sizes it completed."""
    return {r["size"]: r for r in bench["rows"] if r["side"] == "reference" and r["status"] == "ok"}


def speedup_ci(without, with_, rng):
    """
    median(without) / median(with_), and a 95 % bootstrap interval: both runs' timings are
    resampled with replacement and the ratio of medians recomputed BOOTSTRAP times.
    """
    med = statistics.median
    ratios = sorted(med(rng.choices(without, k=len(without))) / med(rng.choices(with_, k=len(with_)))
                    for _ in range(BOOTSTRAP))
    return med(without) / med(with_), ratios[int(0.025 * BOOTSTRAP)], ratios[int(0.975 * BOOTSTRAP) - 1]


def comparisons(results):
    """Per benchmark, per size both variants completed: times and speedup with its interval."""
    rng = random.Random(0)
    out = []
    for name, nc in results["no_cache"].items():
        if name not in results["cache"]:
            continue
        a, b = reference_ok(nc), reference_ok(results["cache"][name])
        rows = [{"size": s, "no_cache": a[s]["seconds"], "cache": b[s]["seconds"],
                 "speedup": speedup_ci(a[s]["times"], b[s]["times"], rng)}
                for s in sorted(set(a) & set(b))]
        if rows:
            out.append({"name": name, "label": nc["label"], "rows": rows})
    return out


def fmt_ms(seconds):
    ms = seconds * 1000
    return f"{ms:,.0f}" if ms >= 100 else f"{ms:.3g}"


def fmt_x(x):
    return f"{x:,.0f}x" if x >= 100 else f"{x:.2f}x"


def fmt_ci(lo, hi):
    return f"[{lo:.2f}, {hi:.2f}]" if hi < 100 else f"[{lo:,.0f}, {hi:,.0f}]"


def size_text(size, label):
    return f"{size}×{size}" if label.startswith("n (") else f"{size:,} {label}"


def summary(comps):
    lines = [
        "Speedup of the verified references from `python_cache`: median time without caching "
        "divided by median time with it, both built with `python_tail_calls`. In brackets: 95 % "
        f"bootstrap interval ({BOOTSTRAP} resamples of the 15 timed runs). The interval only "
        "covers the scatter within one measurement, not drift between the two runs.",
        "",
        "## At the largest size",
        "",
        "| benchmark | size | without (ms) | with (ms) | speedup |",
        "|---|---|---:|---:|---:|",
    ]
    for c in comps:
        r = c["rows"][-1]
        x, lo, hi = r["speedup"]
        lines.append(f"| {c['name']} | {size_text(r['size'], c['label'])} | {fmt_ms(r['no_cache'])} | "
                     f"{fmt_ms(r['cache'])} | {fmt_x(x)} {fmt_ci(lo, hi)} |")
    lines += ["", "## Every size", ""]
    for c in comps:
        lines += [f"### {c['name']}", "", f"| {c['label']} | without (ms) | with (ms) | speedup |",
                  "|---:|---:|---:|---:|"]
        for r in c["rows"]:
            x, lo, hi = r["speedup"]
            lines.append(f"| {r['size']} | {fmt_ms(r['no_cache'])} | {fmt_ms(r['cache'])} | "
                         f"{fmt_x(x)} {fmt_ci(lo, hi)} |")
        lines.append("")
    return "\n".join(lines)


def latex_table(comps):
    """The largest sizes as a booktabs tabular, without a table environment (as bench/calls.py)."""
    def num(s):
        return s.replace(",", "{,}")
    lines = [r"\begin{tabular}{@{}lrrrr@{}}",
             r"  \toprule",
             r"  & & \multicolumn{2}{c}{Time (ms)} & \\",
             r"  \cmidrule(lr){3-4}",
             r"  Benchmark & Size & no cache & cache & Speedup \\",
             r"  \midrule"]
    for c in comps:
        r = c["rows"][-1]
        n = r["size"]
        size = f"${n}\\times{n}$" if c["label"].startswith("n (") else num(f"{n:,}")
        x, lo, hi = r["speedup"]
        # no backslashes inside the f-string expressions: PyPy is Python 3.11
        name = c["name"].replace("_", r"\_")
        speedup = num(fmt_x(x)).replace("x", r"$\times$")
        ci = fmt_ci(lo, hi).replace(", ", ",~")
        lines.append(f"  {name} & {size} & {num(fmt_ms(r['no_cache']))} & "
                     f"{num(fmt_ms(r['cache']))} & {speedup} {{\\scriptsize {ci}}} \\\\")
    lines += [r"  \bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": benchplot.GRID, "axes.labelcolor": benchplot.INK_2,
        "text.color": benchplot.INK, "xtick.color": benchplot.INK_2, "ytick.color": benchplot.INK_2,
        "axes.facecolor": benchplot.SURFACE, "figure.facecolor": benchplot.SURFACE,
        "axes.grid": True, "grid.color": benchplot.GRID, "grid.linewidth": 0.6,
    })
    return plt


def save(fig, path):
    fig.savefig(path, dpi=150)
    fig.savefig(os.path.splitext(path)[0] + ".pdf")
    print(f"wrote {path} (and .pdf)")


def plot_speedups(comps, title, path):
    """One row per benchmark: the speedup at its largest size, with its interval, on a log axis."""
    plt = setup_matplotlib()
    from matplotlib.ticker import FuncFormatter
    fig, ax = plt.subplots(figsize=(7.5, 0.5 * len(comps) + 1.4), layout="constrained")
    color = benchplot.ENV_COLORS[0]
    for y, c in enumerate(comps):
        x, lo, hi = c["rows"][-1]["speedup"]
        ax.errorbar([x], [y], xerr=[[x - lo], [hi - x]], fmt="o", color=color, markersize=6,
                    elinewidth=1.4, capsize=3, zorder=3)
        ax.annotate(fmt_x(x), (hi, y), textcoords="offset points", xytext=(7, 0), va="center",
                    fontsize=8.5, color=benchplot.INK)
    values = [v for c in comps for v in c["rows"][-1]["speedup"]] + [1]
    ax.axvline(1, color=benchplot.INK_2, linewidth=1)
    ax.set_xscale("log")
    ax.set_xlim(min(values) / 1.3, max(values) * 3)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}x"))
    ax.set_yticks(range(len(comps)), [c["name"] for c in comps])
    ax.set_ylim(len(comps) - 0.5, -0.5)
    ax.tick_params(axis="y", length=0)
    for tick in ax.get_yticklabels():
        tick.set_va("bottom")
    for y, c in enumerate(comps):   # the size each row was measured at, under its label
        ax.annotate(benchplot.size_label(c["rows"][-1]["size"], c["label"]), (0, y),
                    xycoords=("axes fraction", "data"), textcoords="offset points",
                    xytext=(-3.5, -1), ha="right", va="top", color=benchplot.INK_3,
                    fontsize=7.5, annotation_clip=False)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("time without caching / time with (log scale, 95 % interval)")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    save(fig, path)
    plt.close(fig)


# variant -> line style, marker fill
VARIANT_STYLE = {"no_cache": ("--", "none"), "cache": ("-", None)}


def plot_sizes(results, title, path):
    """Median time of both variants against size, one panel per benchmark."""
    plt = setup_matplotlib()
    from matplotlib.lines import Line2D
    names = [n for n in results["no_cache"] if n in results.get("cache", {})]
    cols = 3
    nrows = (len(names) + cols - 1) // cols
    fig, axes = plt.subplots(nrows, cols, figsize=(12, 3.3 * nrows + 0.4), layout="constrained",
                             squeeze=False)
    color = benchplot.ENV_COLORS[0]
    for ax, name in zip(axes.flat, names):
        label = results["cache"][name]["label"]
        matrix = label.startswith("n (")
        for v, (style, fill) in VARIANT_STYLE.items():
            b = results[v][name]
            ok, failed = benchplot.times(b, "reference")
            xs = sorted(x for x in ok if not (matrix and x < benchplot.MIN_MATRIX_N))
            ys = [ok[x] for x in xs]
            ax.plot(xs, ys, color=color, linestyle=style, marker="o", markersize=4, linewidth=1.4,
                    markerfacecolor=fill or color)
            band = benchplot.spread(b, "reference")
            bx = [x for x in xs if x in band]
            if bx:
                ax.fill_between(bx, [band[x][0] for x in bx], [band[x][1] for x in bx],
                                color=color, alpha=0.15, linewidth=0)
            for r in failed:
                ax.plot([r["size"]], [ys[-1] if ys else 1e-3], marker="x", markersize=8,
                        markeredgewidth=2, color=color)
        ax.set_xscale("linear" if matrix else "log")
        ax.set_yscale("log")
        ax.set_title(name, loc="left", fontsize=10, fontweight="bold")
        ax.set_xlabel(label)
        ax.set_ylabel("median time (s)")
    for ax in list(axes.flat)[len(names):]:
        ax.set_visible(False)
    handles = [Line2D([], [], color=color, linestyle=s, marker="o", markersize=4,
                      markerfacecolor=f or color, label=v.replace("_", " "))
               for v, (s, f) in VARIANT_STYLE.items()]
    fig.legend(handles=handles, loc="outside upper right", ncols=2, frameon=False, fontsize=8,
               title="band: interquartile range", title_fontsize=8)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    save(fig, path)
    plt.close(fig)


def report():
    if not os.path.isdir(OUT):
        sys.exit(f"{OUT} missing: run `bench/caching.py run` first")
    for interp in sorted(os.listdir(OUT)):
        d = os.path.join(OUT, interp)
        if interp == "generated" or not os.path.isdir(d):
            continue
        results = load_results(d)
        if set(results) != set(VARIANTS):
            print(f"{d}: needs results for both {' and '.join(VARIANTS)}, skipped")
            continue
        comps = comparisons(results)
        md, tex = os.path.join(d, "summary.md"), os.path.join(d, "caching.tex")
        with open(md, "w") as f:
            f.write(f"# Impact of caching: {interp}\n\n" + summary(comps))
        with open(tex, "w") as f:
            f.write(latex_table(comps))
        print(f"wrote {md}, {tex}")
        try:
            plot_speedups(comps, f"Speedup from caching ({interp}, largest size)",
                          os.path.join(d, "caching.png"))
            plot_sizes(results, f"Verified references with and without caching ({interp})",
                       os.path.join(d, "caching-sizes.png"))
        except ImportError:
            print("  matplotlib not installed (PyPy environment?): no plots; "
                  "run `bench/caching.py report` with CPython")


def main():
    argv = sys.argv[1:]
    run_args = []
    if "--" in argv:
        i = argv.index("--")
        argv, run_args = argv[:i], argv[i + 1:]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("steps", nargs="*", help="build, run and/or report (default: all three)")
    p.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS),
                   help="variants to build or run (default: both)")
    args = p.parse_args(argv)
    steps = args.steps or ["build", "run", "report"]
    if unknown := set(steps) - {"build", "run", "report"}:
        p.error(f"unknown steps: {', '.join(sorted(unknown))}")
    if "build" in steps:
        build(args.variants)
    if "run" in steps:
        run(args.variants, run_args)
    if "report" in steps:
        report()


if __name__ == "__main__":
    main()
