"""
Benchmark the code generator's `python_cache` option, which memoises values and instances without
dictionary arguments with @functools.cache (on by default). Every harness is built twice, without
(`no_cache`) and with (`cache`) the option, both with python_tail_calls=true, and bench/run.py is
run against each build.

    uv run python bench/caching.py build     # one Isabelle build per variant, ~1 min each
    uv run python bench/caching.py run       # bench/run.py per variant, under this interpreter
    uv run python bench/caching.py report    # summary.md and caching.tex from the results

With no step given, all three run. Output:

    bench/out/caching/generated/<variant>/<folder>/   generated code of each variant
    bench/out/caching/<interpreter>/<variant>/results.json
    bench/out/caching/<interpreter>/summary.md        speedups with 95 % intervals, every size
    bench/out/caching/<interpreter>/caching.tex       the largest sizes as a booktabs tabular

`build` leaves */generated/ as it found it. Arguments after `--` go to bench/run.py, e.g.
`bench/caching.py run -- --quick --only smith`. Under PyPy, build once with CPython and then
`make bench-caching-pypy`; `report` reads every interpreter's results.
"""
import argparse
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile

from common import INTERPRETER, ROOT, is_matrix
from common import OUT as BENCH_OUT

OUT = os.path.join(BENCH_OUT, "caching")
GENERATED = os.path.join(OUT, "generated")
VARIANTS = {"no_cache": "false", "cache": "true"}   # variant -> value of python_cache
BOOTSTRAP = 2000


def folders():
    """The harness folders listed in ROOTS."""
    with open(os.path.join(ROOT, "ROOTS")) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


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
            cmd = [isabelle, "build", "-c", "-D", ".", "-o", "python_tail_calls=true",
                   "-o", f"python_cache={VARIANTS[v]}"]
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
    """Per benchmark, per size both variants completed: both median times and the speedup."""
    rng = random.Random(0)
    out = []
    for name, base in results["no_cache"].items():
        if name not in results["cache"]:
            continue
        nc, c = reference_ok(base), reference_ok(results["cache"][name])
        rows = [{"size": s, "no_cache": nc[s]["seconds"], "cache": c[s]["seconds"],
                 "speedup": speedup_ci(nc[s]["times"], c[s]["times"], rng)}
                for s in sorted(set(nc) & set(c))]
        if rows:
            out.append({"name": name, "label": base["label"], "matrix": is_matrix(base["label"]),
                        "rows": rows})
    return out


def fmt_ms(seconds):
    ms = seconds * 1000
    return f"{ms:,.0f}" if ms >= 100 else f"{ms:.3g}"


def fmt_x(x):
    return f"{x:,.0f}x" if x >= 100 else f"{x:.2f}x"


def fmt_ci(lo, hi):
    return f"[{lo:.2f}, {hi:.2f}]" if hi < 100 else f"[{lo:,.0f}, {hi:,.0f}]"


HEAD = "| no cache (ms) | cache (ms) | speedup |"
RULE = "|---:|---:|---:|"


def cells(r):
    x, lo, hi = r["speedup"]
    return f"{fmt_ms(r['no_cache'])} | {fmt_ms(r['cache'])} | {fmt_x(x)} {fmt_ci(lo, hi)} |"


def summary(comps):
    lines = [
        "Speedup of the verified references from `python_cache`: median time of `no_cache` divided "
        f"by that of `cache`. In brackets: 95 % bootstrap interval ({BOOTSTRAP} resamples of the "
        "timed runs), which covers the scatter within one measurement, not drift between runs.",
        "",
        "## At the largest size",
        "",
        "| benchmark | size " + HEAD,
        "|---|---" + RULE,
    ]
    for c in comps:
        r = c["rows"][-1]
        size = f"{r['size']}×{r['size']}" if c["matrix"] else f"{r['size']:,} {c['label']}"
        lines.append(f"| {c['name']} | {size} | " + cells(r))
    lines += ["", "## Every size", ""]
    for c in comps:
        lines += [f"### {c['name']}", "", f"| {c['label']} " + HEAD, "|---:" + RULE]
        lines += [f"| {r['size']} | " + cells(r) for r in c["rows"]]
        lines.append("")
    return "\n".join(lines)


def latex_table(comps):
    """The largest sizes as a booktabs tabular, without a table environment (like bench/calls.py)."""
    def num(s):
        return s.replace(",", "{,}")
    lines = [r"\begin{tabular}{@{}llrrr@{}}",
             r"  \toprule",
             r"  & & \multicolumn{2}{c}{Time (ms)} & \\",
             r"  \cmidrule(lr){3-4}",
             r"  Benchmark & Size & no cache & cache & Speedup \\",
             r"  \midrule"]
    for c in comps:
        r = c["rows"][-1]
        n = r["size"]
        size = f"${n}\\times{n}$" if c["matrix"] else num(f"{n:,}")
        # backslashes stay out of f-string expressions: PyPy is Python 3.11
        name = c["name"].replace("_", r"\_")
        x, lo, hi = r["speedup"]
        speedup = (num(fmt_x(x)).replace("x", r"$\times$")
                   + r" {\scriptsize " + fmt_ci(lo, hi).replace(", ", ",~") + "}")
        lines.append(f"  {name} & {size} & {num(fmt_ms(r['no_cache']))} & "
                     f"{num(fmt_ms(r['cache']))} & {speedup} \\\\")
    lines += [r"  \bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def report():
    if not os.path.isdir(OUT):
        sys.exit(f"{OUT} missing: run `bench/caching.py run` first")
    for interp in sorted(os.listdir(OUT)):
        d = os.path.join(OUT, interp)
        if interp == "generated" or not os.path.isdir(d):
            continue
        results = load_results(d)
        if len(results) < len(VARIANTS):
            print(f"{d}: needs results for both variants, skipped")
            continue
        comps = comparisons(results)
        md, tex = os.path.join(d, "summary.md"), os.path.join(d, "caching.tex")
        with open(md, "w") as f:
            f.write(f"# Impact of caching: {interp}\n\n" + summary(comps))
        with open(tex, "w") as f:
            f.write(latex_table(comps))
        print(f"wrote {md}, {tex}")


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
