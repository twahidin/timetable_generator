"""python -m ttgen sample secondary|primary --out FILE
   python -m ttgen check SETUP.xlsx
   python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx [--time 300] [--workers 8] [--export DIR]
   python -m ttgen export SETUP.xlsx TIMETABLE.xlsx --out DIR [--no-pdf] [--no-individual] [--no-html] [--no-excel]"""
import argparse, os, shutil, sys
from .reader import read_template, derive

def _say_outputs(out):
    names = {"excel": "Excel, every timetable", "html": "HTML timetable finder", "pdf_zip": "single PDFs (zip)"}
    for k, v in out.items():
        if k == "pdf_books":
            for p in v: print("wrote", p)
        else: print("wrote", v, f"({names.get(k, k)})")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ttgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("kind", choices=["secondary", "primary"]); s.add_argument("--out", required=True)
    c = sub.add_parser("check"); c.add_argument("setup")
    v = sub.add_parser("solve"); v.add_argument("setup"); v.add_argument("--out", required=True); v.add_argument("--time", type=float, default=300)
    v.add_argument("--workers", type=int, default=8); v.add_argument("--export", help="also write PDFs and the HTML finder into this folder")
    e = sub.add_parser("export"); e.add_argument("setup"); e.add_argument("timetable"); e.add_argument("--out", required=True)
    for flag in ("pdf", "individual", "html", "excel"): e.add_argument(f"--no-{flag}", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        from .samples import secondary, primary
        from .template import write_template
        write_template(secondary() if a.kind == "secondary" else primary(), a.out); print("wrote", a.out); return 0
    if a.cmd == "export":
        from .export import model_from_files, export_all
        m = model_from_files(a.setup, a.timetable)
        ch = m["checks"]
        print(f"{ch['lessons']} lessons, {len(m['classes'])} classes, {len(m['students'])} students: " + ("all checks passed" if ch["ok"] else f"{len(ch['problems'])} problems"))
        for p in ch["problems"][:20]: print(" -", p)
        out = export_all(m, a.out, pdf=not a.no_pdf, individual=not a.no_individual, html=not a.no_html, excel=not a.no_excel)
        _say_outputs(out); return 0 if ch["ok"] else 1
    spec = read_template(a.setup)
    if a.cmd == "check":
        probs = derive(spec)
        from .solver import Problem
        P = Problem(spec)
        print(f"{len(spec['classes'])} classes, {len(spec['teachers'])} teachers, {len(spec['lessons'])} lesson rows, {len(spec['blocks'])} blocks, "
              f"{len(spec.get('rules', []))} rules, {len(spec.get('students', []))} students")
        print(f"{len(P.units)} units to place over {P.ND} days x {P.NP} periods")
        for p in probs or ["No input problems found."]: print(" -", p)
        return 0
    from .solver import solve
    from .report import write_timetable
    res = solve(spec, time_limit=a.time, workers=a.workers)
    probs, stats, post, m = write_timetable(res, a.out, return_model=True)
    print("wrote", a.out, stats)
    for p in (probs or ["Checks passed: no clashes, every lesson placed with its planned periods."]): print(" -", p)
    for p in post + res.get("notes", []): print(" *", p)
    if a.export and m is not None:
        from .export import export_all, safe_name
        out = export_all(m, a.export, excel=False)
        dst = os.path.join(a.export, safe_name(f"{m['school']['name']} {m['school']['timetable']}") + " - all timetables.xlsx")
        shutil.copyfile(a.out, dst); out["excel"] = dst
        _say_outputs(out)
    return 0 if res["lessons"] and not probs else 1

if __name__ == "__main__":
    sys.exit(main())
