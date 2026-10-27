"""python -m ttgen sample secondary|primary --out FILE
   python -m ttgen check SETUP.xlsx
   python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx [--time 300] [--workers 8]"""
import argparse, sys
from .reader import read_template, derive

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ttgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("kind", choices=["secondary", "primary"]); s.add_argument("--out", required=True)
    c = sub.add_parser("check"); c.add_argument("setup")
    v = sub.add_parser("solve"); v.add_argument("setup"); v.add_argument("--out", required=True); v.add_argument("--time", type=float, default=300); v.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        from .samples import secondary, primary
        from .template import write_template
        write_template(secondary() if a.kind == "secondary" else primary(), a.out); print("wrote", a.out); return 0
    spec = read_template(a.setup)
    if a.cmd == "check":
        probs = derive(spec)
        from .solver import Problem
        P = Problem(spec)
        print(f"{len(spec['classes'])} classes, {len(spec['teachers'])} teachers, {len(spec['lessons'])} lesson rows, {len(spec['blocks'])} blocks, {len(spec.get('rules', []))} rules")
        print(f"{len(P.units)} units to place over {P.ND} days x {P.NP} periods")
        for p in probs or ["No input problems found."]: print(" -", p)
        return 0
    from .solver import solve
    from .report import write_timetable
    res = solve(spec, time_limit=a.time, workers=a.workers)
    probs, stats, post = write_timetable(res, a.out)
    print("wrote", a.out, stats)
    for p in (probs or ["Checks passed: no clashes, every lesson placed with its planned periods."]): print(" -", p)
    for p in post + res.get("notes", []): print(" *", p)
    return 0 if res["lessons"] and not probs else 1

if __name__ == "__main__":
    sys.exit(main())
