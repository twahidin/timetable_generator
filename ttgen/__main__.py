"""python -m ttgen sample secondary|primary --out FILE
   python -m ttgen check SETUP.xlsx
   python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx [--time 300] [--workers 8] [--staged] [--export DIR]
   python -m ttgen export SETUP.xlsx TIMETABLE.xlsx|TIMETABLE.sqlite --out DIR [--no-pdf] [--no-individual] [--no-html] [--no-excel] [--no-db]
   (export also writes the timetable as a SQLite database; a database written this way keeps the setup, so SETUP may be -)"""
import argparse, os, shutil, sys
from .reader import read_template, derive

def _say_outputs(out):
    names = {"excel": "Excel, every timetable", "html": "HTML timetable finder", "pdf_zip": "single PDFs (zip)", "db": "SQLite database, for other systems"}
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
    v.add_argument("--workers", type=int, default=8); v.add_argument("--staged", action="store_true", help="build level by level (big, tight schools); --time is per step")
    v.add_argument("--export", help="also write PDFs and the HTML finder into this folder")
    e = sub.add_parser("export"); e.add_argument("setup"); e.add_argument("timetable"); e.add_argument("--out", required=True)
    for flag in ("pdf", "individual", "html", "excel", "db"): e.add_argument(f"--no-{flag}", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        from .samples import secondary, primary
        from .template import write_template
        write_template(secondary() if a.kind == "secondary" else primary(), a.out); print("wrote", a.out); return 0
    if a.cmd == "export":
        from .export import model_from_files, export_all
        m = model_from_files(None if a.setup == "-" else a.setup, a.timetable)
        ch = m["checks"]
        print(f"{ch['lessons']} lessons, {len(m['classes'])} classes, {len(m['students'])} students: " + ("all checks passed" if ch["ok"] else f"{len(ch['problems'])} problems"))
        for p in ch["problems"][:20]: print(" -", p)
        out = export_all(m, a.out, pdf=not a.no_pdf, individual=not a.no_individual, html=not a.no_html, excel=not a.no_excel, db=not a.no_db)
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
        from .spec import structure_vs_rules
        for p in structure_vs_rules(spec): print(" ! Day structure and rules disagree:", p)
        from .solver import fixed_clashes, rule_label, rule_problems
        for p in fixed_clashes(spec, P): print(" ! Fixed lessons clash:", p)
        for i, p in rule_problems(spec, P): print(f" ! Rule {rule_label(spec['rules'][i])}: {p}")
        from .spec import typed_rules, typed_label
        for num, _, r in typed_rules(spec): print(" * For the agent to honour:", typed_label(num, r))
        from . import choices
        bad = {}
        for i, p in choices.problems(spec): bad.setdefault(i, p)
        for n, (i, c) in enumerate(choices.ordered(spec), start=1):
            print(f" * Second choice {n}: {choices.item_label(spec, c)} — {choices.first_text(spec, c)} → {choices.second_text(spec, c)}")
            if i in bad: print(f" ! Second choice {n}: {bad[i]}")
        return 0
    from .solver import solve
    from .report import write_timetable
    from . import choices
    def run(sp):
        if a.staged:
            from .staged import solve_staged
            return solve_staged(sp, time_per_step=a.time, workers=a.workers)
        return solve(sp, time_limit=a.time, workers=a.workers)
    cmode = choices.mode(spec)
    attempts = choices.give_way(spec, run, cmode)
    if cmode == "compare":
        stem, ext = os.path.splitext(a.out)
        todo = [(at, a.out if at["k"] == 0 else f"{stem} - after choice {at['k']}{ext}") for at in attempts]
    else: todo = [(attempts[-1], a.out)]
    ok, any_lessons = True, False
    for at, path in todo:
        k, res = at["k"], at["res"]
        probs, stats, post, m = write_timetable(res, path, return_model=True)
        rows = choices.used_rows(spec, k) if res["lessons"] else []
        if rows:
            choices.used_sheet(path, rows); m["choices_used"] = rows
        if cmode == "compare": print(f"--- {'First choices' if k == 0 else f'After choice {k}'} ---")
        print("wrote", path, stats)
        for p in (probs or ["Checks passed: no clashes, every lesson placed with its planned periods."]): print(" -", p)
        for p in post + res.get("notes", []): print(" *", p)
        for r in rows:
            if r["used"] == "Second choice": print(f" * Gave way on choice {r['no']}: {r['item']} ({r['how']})")
        if m is not None and a.export:
            from .export import export_all, safe_name
            folder = a.export if cmode != "compare" else os.path.join(a.export, "first choices" if k == 0 else f"after choice {k}")
            out = export_all(m, folder, excel=False)
            dst = os.path.join(folder, safe_name(f"{m['school']['name']} {m['school']['timetable']}") + " - all timetables.xlsx")
            shutil.copyfile(path, dst); out["excel"] = dst
            _say_outputs(out)
        if res["lessons"]:
            any_lessons = True
            if probs: ok = False
    return 0 if any_lessons and ok else 1

if __name__ == "__main__":
    sys.exit(main())
