"""python -m ttgen sample secondary|primary --out FILE
   python -m ttgen check SETUP.xlsx
   python -m ttgen solve SETUP.xlsx --out TIMETABLE.xlsx [--time 300] [--workers 8] [--staged] [--export DIR]
   python -m ttgen export SETUP.xlsx TIMETABLE.xlsx|TIMETABLE.sqlite --out DIR [--no-pdf] [--no-individual] [--no-html] [--no-excel] [--no-db]
   python -m ttgen check-timetable TIMETABLE.xlsx|TIMETABLE.sqlite [--setup SETUP.xlsx]   (--setup is optional for a database)
   (export also writes the timetable as a SQLite database; a database written this way keeps the setup, so SETUP may be -)"""
import argparse, os, shutil, sys
from .reader import read_template

def _say_outputs(out):
    names = {"excel": "Excel, every timetable", "html": "HTML timetable finder", "pdf_zip": "single PDFs (zip)", "db": "SQLite database, for other systems"}
    for k, v in out.items():
        if k == "pdf_books":
            for p in v: print("wrote", p)
        else: print("wrote", v, f"({names.get(k, k)})")

def record_choices(m, spec, k, path):
    """after a solve at k: put the Choices used rows on the model m and on the workbook at path, and keep the setup as downloaded
    in m (the solver ran on the copy with the first k choices given way on, which must not reach the database)"""
    from . import choices
    rows = choices.used_rows(spec, k)
    if m is not None: m["setup"] = spec
    if rows:
        choices.used_sheet(path, rows)
        if m is not None: m["choices_used"] = rows
    return rows

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ttgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("kind", choices=["secondary", "primary"]); s.add_argument("--out", required=True)
    c = sub.add_parser("check"); c.add_argument("setup")
    v = sub.add_parser("solve"); v.add_argument("setup"); v.add_argument("--out", required=True); v.add_argument("--time", type=float, default=300)
    v.add_argument("--workers", type=int, default=8); v.add_argument("--staged", action="store_true", help="build level by level (big, tight schools); --time is per step")
    v.add_argument("--export", help="also write PDFs and the HTML finder into this folder")
    k = sub.add_parser("check-timetable"); k.add_argument("timetable"); k.add_argument("--setup")
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
    if a.cmd == "check-timetable":
        from .export import model_from_files
        from . import verify
        m = model_from_files(a.setup, a.timetable); r = verify.warnings(m); ws = r["warnings"]
        per = ", ".join(f"{sum(1 for w in ws if w['kind'] == kd)} {kd}" for kd in verify.KINDS if any(w["kind"] == kd for w in ws))
        crit = [w for w in ws if w.get("crit")]
        print(f"{len(ws)} warnings, {len(crit)} critical" + (f" ({per})" if per else ""))
        for kd in verify.KINDS:
            for w in ws:
                if w["kind"] == kd: print(f" - [critical: {verify.CRIT_WORDS[w['crit']]}] {w['text']}" if w.get("crit") else f" - [{kd}] {w['text']}")
        for line in r["not_checked"]: print(f" ? Not checked: {line}")
        return 1 if crit or any(w["strength"] == "Must" for w in ws) else 0
    spec = read_template(a.setup)
    if a.cmd == "check":
        import copy
        from . import checks
        from .solver import Problem
        raw = copy.deepcopy(spec) if spec.get("choices") else None   # for the sums down the give-way list: findings() works the setup out in place
        found = checks.findings(spec); P = Problem(spec)   # the sums of the app's step 7, Will it fit?: the same list, in the same words
        print(f"{len(spec['classes'])} classes, {len(spec['teachers'])} teachers, {len(spec['lessons'])} lesson rows, {len(spec['blocks'])} blocks, "
              f"{len(spec.get('rules', []))} rules, {len(spec.get('students', []))} students")
        print(f"{len(P.units)} units to place over {P.ND} days x {P.NP} periods")
        crit = [f for f in found if f["level"] == checks.CRITICAL]; warn = [f for f in found if f["level"] != checks.CRITICAL]
        print(f"Critical ({len(crit)}): no timetable can be made until these are fixed")   # both headings always, so new scripts can be told from old
        for f in crit: print(f" - [{f['area']}] {f['text']}")
        stop = bool(crit)
        if crit and raw is not None:   # second choices: do the critical items go once the committee's list is given way on, in its order?
            fb = checks.with_fallbacks(raw); k = fb["pass_at"]
            if k: print(f"Giving way in the committee's order, nothing is critical after choice {k}: {'; '.join(fb['items'][:k])}."); stop = False
            elif k is None: m = fb["critical"][-1]; print(f"Even after every second choice ({len(fb['items'])}), {m} thing{'' if m == 1 else 's'} will not fit.")
        print(f"Warnings ({len(warn)}): a timetable can still be made; a person should check these")
        for f in warn: print(f" - [{f['area']}] {f['text']}")
        from .spec import typed_rules, typed_label
        for num, _, r in typed_rules(spec): print(" * For the agent to honour:", typed_label(num, r))
        from . import choices
        bad = {}
        for i, p in choices.problems(spec): bad.setdefault(i, p)
        for n, (i, c) in enumerate(choices.ordered(spec), start=1):
            print(f" * Second choice {n}: {choices.item_label(spec, c)} — {choices.first_text(spec, c)} → {choices.second_text(spec, c)}")
            if i in bad: print(f" ! Second choice {n}: {bad[i]}")
        return 1 if stop else 0   # critical, and no step of the second choices clears it
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
        rows = record_choices(m, spec, k, path) if res["lessons"] else []
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
