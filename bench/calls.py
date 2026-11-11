"""
Count function calls: the same workloads as bench/run.py, counted once with a sys.setprofile hook,
for the generated reference and the library side by side. Counts are split into Python-level calls,
calls into C (builtins and C extension modules such as _heapq), and the dataclass-generated
__init__ calls, i.e. objects built from a HOL datatype. A call into C counts once, however much
work it does there.

Each side runs once untimed first (warming caches such as SymPy's), then once under the hook.
The table rounds the counts (e.g. 129k); the exact counts go to bench/out/<interpreter>/calls.json.
Meant for CPython; under PyPy the profile hook disables most of the JIT.

    uv run python bench/calls.py                     # 1000 keys / elements, 5 x 5 matrices
    uv run python bench/calls.py --elements 10000 --matrix-n 8
    uv run python bench/calls.py --only rbt_map smith
    uv run python bench/calls.py --latex             # also bench/out/cpython/calls.tex
"""
import argparse
import json
import os
import random
import sys

import run   # the workloads and generated modules of the benchmark
from common import is_matrix


def count(fn, arg):
    """(total, python, c, dataclass inits) calls for one run of fn(arg)."""
    fn(arg)
    # count the profiler events directly (the hook cProfile uses): pstats keys its stats by
    # (file, line, name), under which the generated __init__ of every dataclass looks the same
    # and only one would survive
    c = {"python": 0, "c": 0, "dataclass_inits": 0}

    def hook(frame, event, _):
        if event == "call":
            c["python"] += 1
            code = frame.f_code
            # dataclasses compile __init__ from a string, so it has no real source file
            if code.co_name == "__init__" and code.co_filename.startswith("<"):
                c["dataclass_inits"] += 1
        elif event == "c_call":           # builtins and C extensions
            c["c"] += 1

    sys.setprofile(hook)
    try:
        fn(arg)
    finally:
        sys.setprofile(None)
    return {"total": c["python"] + c["c"], **c}


def short(n):
    """A call count for the table, rounded: 2,003 -> '2.0k', 128,634 -> '129k', 1,089,678 -> '1.09M'."""
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.2f}M"


def latex_table(benchmarks):
    """
    A booktabs tabular (no table environment, so the paper sets caption and placement) with one
    row per benchmark: size, calls and objects of the reference, calls of the library, ratio.
    """
    lines = [r"\begin{tabular}{@{}lrrrrr@{}}",
             r"  \toprule",
             r"  & & \multicolumn{2}{c}{Generated} & Library & \\",
             r"  \cmidrule(lr){3-4}\cmidrule(lr){5-5}",
             r"  Benchmark & Size & Calls & Objects & Calls & Ratio \\",
             r"  \midrule"]
    for b in benchmarks:
        name = b["name"].replace("_", r"\_")
        n = b["size"]
        size = f"${n}\\times{n}$" if is_matrix(b["label"]) else f"{n:,}".replace(",", "{,}")
        ref, lib = b["reference"], b["library"]
        lines.append(f"  {name} & {size} & {short(ref['total'])} & {short(ref['dataclass_inits'])} & "
                     f"{short(lib['total'])} & {b['ratio']:.0f}$\\times$ \\\\")
    lines += [r"  \bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="+", help="benchmark names to run")
    p.add_argument("--elements", type=int, default=1000,
                   help="keys or elements for the map and heap benchmarks (default 1000)")
    p.add_argument("--matrix-n", type=int, default=5, help="n for the n x n matrices (default 5)")
    p.add_argument("--seed", default="0")
    p.add_argument("--out", help=f"output directory (default bench/out/{run.INTERPRETER})")
    p.add_argument("--latex", nargs="?", const="", metavar="PATH",
                   help="also write the table as a LaTeX tabular (default: calls.tex next to calls.json)")
    args = p.parse_args()

    out = args.out or os.path.join(run.OUT, run.INTERPRETER)
    os.makedirs(out, exist_ok=True)
    json_path = os.path.join(out, "calls.json")
    results = {"interpreter": run.INTERPRETER, "python": sys.version.split()[0], "benchmarks": []}

    print(f"{'benchmark':14} {'size':>6} {'side':10} {'total':>10} {'python':>10} {'C':>8} "
          f"{'dc inits':>9}")
    for b in run.benchmarks():
        if args.only and b.name not in args.only:
            continue
        n = args.matrix_n if b.matrix else args.elements
        arg = b.make(n, random.Random(f"{args.seed}-{b.name}-{n}"))
        counts = {side: count(fn, arg) for side, fn in (("reference", b.ref), ("library", b.lib))}
        for side, c in counts.items():
            print(f"{b.name:14} {n:>6} {side:10} {short(c['total']):>10} {short(c['python']):>10} "
                  f"{short(c['c']):>8} {short(c['dataclass_inits']):>9}")
        ratio = counts["reference"]["total"] / counts["library"]["total"]
        print(f"{'':14} {'':>6} {'ratio':10} {ratio:>9.1f}x", flush=True)
        results["benchmarks"].append({"name": b.name, "label": b.label, "lib_name": b.lib_name,
                                      "size": n, **counts, "ratio": ratio})
    with open(json_path, "w") as f:
        json.dump(results, f, indent=1)
    print(f"wrote {json_path}")
    if args.latex is not None:
        tex_path = args.latex or os.path.join(out, "calls.tex")
        with open(tex_path, "w") as f:
            f.write(latex_table(results["benchmarks"]))
        print(f"wrote {tex_path}")


if __name__ == "__main__":
    main()
