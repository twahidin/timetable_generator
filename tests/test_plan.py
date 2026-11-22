"""Plain-assert tests for Plan with AI: .venv/bin/python tests/test_plan.py"""
import itertools, os, random, re, secrets, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = tempfile.mkdtemp()
KEY = secrets.token_hex(16)
os.environ.pop("HEADS_CODE", None)
os.environ.pop("TYPED_REQUEST_MODEL", None)          # no test calls a real AI
os.environ.update(DATA_DIR=DATA, SECRET_KEY=KEY, AI_API_KEY="", COMMITTEE_CODE=secrets.token_hex(4), TEACHER_CODE=secrets.token_hex(4), STUDENT_CODE=secrets.token_hex(4))
sys.path.insert(0, ROOT)
from exams import fake as F  # noqa: E402
from relief.pick import HONORIFICS  # noqa: E402
from plan import names  # noqa: E402

def raises(exc, f, text=None):
    try: f()
    except exc as e:
        if text is not None: assert str(e) == text, str(e)
        return
    raise AssertionError("did not raise")

COUNT = 0
def t(f):
    global COUNT
    f(); COUNT += 1
    return f

def same(got, want):
    assert got == want, f"{got!r} is not {want!r}"

# ---------------------------------------------------------------- names to codes (every name here is made up)
TAN, RIZAL, LIM, KOH = "Ms Tan Wei Ling", "Mr Ahmad Rizal", "Mdm May Lim", "Mr Art Koh"
STAFF = [(TAN, "TWL"), RIZAL, LIM, KOH]
KIDS = [("S101", "Alicia Ng"), ("S102", "Ng Wei Jie")]
WHERES = ("typed", "list", "app")

def a_pub(rooms=("Art Room",), school="Sample School", subjects=()):
    pub = F.sample_pub(); m = pub["model"]
    m["rooms"] += [dict(name=n, kind="special room", capacity=40, parts=[]) for n in rooms]
    m["lessons"] += [dict(m["lessons"][0], id=90 + i, subject=s) for i, s in enumerate(subjects)]
    m["school"]["name"] = school; pub["meta"]["school"] = school
    m["students"] = []
    return pub

def people(*who):
    return [dict(name=w if isinstance(w, str) else w[0], short=w if isinstance(w, str) else w[1], depts=[], role="", teaches=True, staff_only=False) for w in who]

def kids(*who):
    return [dict(id=i, name=n, cls="3A", level="Sec 3", groups=[]) for i, n in who]

def a_names(*staff, students=KIDS, **kw):
    return names.Names(a_pub(**kw), people(*(staff or STAFF)), kids(*students))

def all_where(N, text, want):
    for w in WHERES: same(N.out(text, w), want)

@t
def a_teacher_goes_as_one_code_however_the_name_is_written():
    N = a_names()
    c = N.code(TAN); assert re.fullmatch(r"T\d\d", c) and N.code(TAN) == c
    same(N.out("Ms Tan, Tan Wei Ling and Ms Ling", "typed"), f"{c}, {c} and {c}")
    all_where(N, "Ask Ms Tan, Ms Wei Ling, Tan Wei Ling and Wei Tan Ling", f"Ask {c}, {c}, {c} and {c}")
    all_where(N, "Ms Tan Wei Ling", c); all_where(N, "Ms Tan wei ling, Tan wei and tan Wei", f"{c}, {c} and {c}")
    all_where(N, "ms tan wei ling, MS TAN WEI LING and Ling Wei", f"{c}, {c} and {c}")
    same(N.out("ask tan", "typed"), "ask tan")
    same(N.out("Ask Tan", "typed"), f"Ask {c}"); same(N.out("ASK TAN", "typed"), f"ASK {c}")
    same(N.out("Ask Tan and Ling", "list"), "Ask Tan and Ling"); same(N.out("Ask Tan and Ling", "app"), "Ask Tan and Ling")

@t
def the_short_name_is_a_name_in_typed_and_app_text_and_not_in_a_list():
    N = a_names(); c = N.code(TAN)
    same(N.out("TWL is free", "typed"), f"{c} is free"); same(N.out("TWL is free", "app"), f"{c} is free")
    same(N.out("TWL is free", "list"), "TWL is free")
    same(N.out("twl is free, TWLX too", "app"), "twl is free, TWLX too")          # exactly as it is written
    N = a_names(("Ms Chua Li Hui", "W.L. Chua"), ("Mr Goh Ah Seng", "Goh AS"))
    same(N.out("W.L. Chua, Goh AS", "app"), f"{N.code('Ms Chua Li Hui')}, {N.code('Mr Goh Ah Seng')}")
    N = a_names(("Ms Wong Mei", "W.M."), ("Mr Lau Kit", "L K"), ("Mdm Ho Siu", "Ms Ho"), "Ms Ho Yan")
    same(N.out("W.M. and L K and Ms Ho", "app"), f"{N.code('Ms Wong Mei')}. and {N.code('Mr Lau Kit')} and {N.code('Mdm Ho Siu')}")
    same(N.out("W.M. and L K and Ms Ho", "list"), f"W.M. and L K and {N.code('Ms Ho Yan')}")
    N = a_names(("Ms Tan Wei Ling", "TWL"), ("Mr Teo Wee Leong", "TWL"))          # one short name, two people
    same(N.out("TWL", "app"), f"{N.code('Mr Teo Wee Leong')} or {N.code(TAN)}")

@t
def days_months_subjects_and_rooms_are_never_changed():
    N = a_names()
    all_where(N, "May 2027, the Art Room, English on Mon 3 May", "May 2027, the Art Room, English on Mon 3 May")
    all_where(N, "Mon 3 May, Art Room", "Mon 3 May, Art Room")
    all_where(N, "MAY 2027, ART ROOM, art, may, Art and May", "MAY 2027, ART ROOM, art, may, Art and May")
    all_where(N, "Sec 3 English Paper 1\t3A, 3B\t2027-05-03\t08:00\t3-01", "Sec 3 English Paper 1\t3A, 3B\t2027-05-03\t08:00\t3-01")
    for n in (LIM, KOH): all_where(N, f"for {n}.", f"for {N.code(n)}.")
    all_where(N, "Mdm May Lim, May Lim and Lim May", ", ".join([N.code(LIM)] * 2) + f" and {N.code(LIM)}")
    all_where(N, "Ms May and Mr Art", f"{N.code(LIM)} and {N.code(KOH)}")          # a title makes a person of it
    N = a_names(("Ms May Art", "ART"), "May June")                                # all its words are protected
    all_where(N, "May June, Art May and May", "May June, Art May and May")
    same(N.out("ART is full", "typed"), "ART is full"); same(N.out("ART is full", "app"), "ART is full")
    all_where(N, "Ms May Art", N.code("Ms May Art"))
    all_where(a_names("May (Art)", "Tan Ah Kow (Will)"), "May (Art), Tan Ah Kow (Will), Tan Ah Kow (will be late)", "May (Art), T02, T02 (will be late)")

@t
def a_date_or_a_room_beside_a_name_stays():
    N = a_names(); lim, koh = N.code(LIM), N.code(KOH)
    all_where(N, "Mdm Lim may be away", f"{lim} may be away")
    all_where(N, "Mdm Lim May 3", f"{lim} May 3"); all_where(N, "Mdm Lim May 2027", f"{lim} May 2027")
    all_where(N, "Mdm Lim May 3rd", f"{lim} May 3rd")
    same(N.out("When may Lim invigilate?", "typed"), f"When may {lim} invigilate?")
    same(N.out("on 3 May Lim is away", "typed"), f"on 3 May {lim} is away")
    all_where(N, "English\tMdm Lim\tMay 3", f"English\t{lim}\tMay 3")
    all_where(N, "on 3 May\nMdm Lim is away", f"on 3 May\n{lim} is away")
    same(N.out("English\t3 May\tLim\nMaths\tLim\tMay 4", "list"), "English\t3 May\tLim\nMaths\tLim\tMay 4")
    all_where(N, "Put Mr Koh Art Room 3A", f"Put {koh} Art Room 3A")
    all_where(N, "Mr Koh\nArt\t3 May", f"{koh}\nArt\t3 May")
    all_where(a_names(subjects=("Food and Nutrition",)), "Mr Koh Art and Mdm Lim May and", f"{koh} and {lim} and")
    for text in ("3A will miss Art", "they miss May, so miss English"): all_where(N, text, text)
    all_where(N, "mdm lim may be away", f"{lim} may be away"); all_where(N, "May Mdm Lim come?", f"May {lim} come?")
    for w in ("list", "app"): same(N.out("When may Lim come? Lim may be late.", w), "When may Lim come? Lim may be late.")
    all_where(N, "tell each teacher May 3 is fixed", "tell each teacher May 3 is fixed")
    all_where(N, "Teacher Art Room 3A", "Teacher Art Room 3A"); all_where(N, "Teacher\nArt\t3A", "Teacher\nArt\t3A")
    same(N.out("Sec 3\tArt\tKoh\t3 May\nSec 4\tArt   Koh", "list"), "Sec 3\tArt\tKoh\t3 May\nSec 4\tArt   Koh")      # cells of a row
    all_where(N, "Mdm Lim\tMay 3\tMr Koh\tArt", f"{lim}\tMay 3\t{koh}\tArt")
    all_where(N, "Mdm May\nLim", lim); same(N.out("May\nLim", "typed"), f"May\n{lim}"); same(N.out("May\nLim, Koh\nArt", "list"), f"{lim}, {koh}")                    # a line cut in a name
    same(N.out("3 May\nLim, Lim\nMay 3", "list"), "3 May\nLim, Lim\nMay 3"); same(N.out("3 May\nLim, Lim\nMay 3", "typed"), f"3 May\n{lim}, {lim}\nMay 3")
    all_where(a_names("Ms Tan Wei May"), "Ms Wei May English, Tan Wei May 3A", "T01 English, T01 3A")                  # in the name's own order it is the name
    all_where(a_names(LIM, students=[("S1", "May Long")]), "3 May long papers, May Long", "3 May long papers, a student")
    # what is left out of a name is never a word that only a name has
    for text in ("1 May Lim", "Lim May 3", "May Lim 3"):
        for w in WHERES: assert "Lim" not in N.out(text, w), (text, w, N.out(text, w))

@t
def a_student_is_never_named():
    N = a_names()
    for w in WHERES:
        got = N.out("A make-up for Alicia Ng, S101 and Ng Alicia", w)
        same(got, "A make-up for a student, a student and a student")
        same(N.out("Alicia Ng (S101) and Ng Alicia", w), "a student (a student) and a student")
        same(N.out("s101, ALICIA NG, wei jie", w), "a student, a student, a student")
        same(N.out("Miss Alicia Ng", w), "a student")
        same(N.out("S1012, XS101", w), "S1012, XS101")
        same(N.out("Alicia is away", w), "Alicia is away")                         # a first name alone is sent as typed

@t
def a_student_id_that_could_be_a_date_is_not_one():
    N = a_names(students=[("3", "Bee Teo"), ("2027", "Kai Sim"), ("10-05", "Jo Png"), ("3A", "Zed Yap"), ("25001", "Ria Das"), ("1023", "Uma Roy")])
    text = "3 May 2027, 2027-10-05, 3A"
    all_where(N, text, text)
    all_where(N, "25001 and student 1023", "a student and student a student")
    all_where(a_names(students=[("Lab 3-08", "Jo Png"), ("3A-01", "Bo Yeo")]), "Lab 3-08, lab 3-08 and 3a-01", "Lab 3-08, lab 3-08 and a student")
    N = a_names(students=[("ZYAP", "Zed Yap"), ("MAY", "Uma Roy"), ("A", "Bo Yeo"), ("Wee Kim", "Wee Kim")])       # an ID with no digit: as it is written
    all_where(N, "ZYAP, zyap, MAY, May, A Wee Kim and wee kim", "a student, zyap, MAY, May, A a student and a student")
    N = names.Names(F.sample_pub(), [], F.sample_pub()["model"]["students"])
    for s in F.sample_pub()["model"]["students"]: all_where(N, f"{s['id']}, {s['name']}.", "a student, a student.")
    all_where(N, "3A, 3B and 3-01, 3A 10, 3A 30 and Student", "3A, 3B and 3-01, 3A 10, 3A 30 and Student")

@t
def a_class_a_period_and_an_unknown_name_are_left_alone():
    N = a_names()
    text = "3A, 4B, P3, Sec 3, Ms Unknown, Mr Nobody Here, Jane Doe, 12 students, 08:00 to 10:00, AM and PM, Teacher, a sir"
    all_where(N, text, text)

@t
def a_teacher_wins_over_a_student():
    N = a_names(students=[("S1", "Tan Wei Ling"), ("S2", "Wei Ling Ho"), ("S3", "Tan Wei Ling Faith")]); c = N.code(TAN)
    all_where(N, "Tan Wei Ling", c); all_where(N, "Wei Ling", c); all_where(N, "S1", "a student")
    all_where(N, "Wei Ling Ho and Tan Wei Ling Faith", "a student and a student")   # the longer one is the student's alone

@t
def two_people_who_fit_the_same_words_go_as_both_codes():
    KIAT = "Mr Tan Boon Kiat"
    N = a_names((TAN, "TWL"), KIAT); her, his = N.code(TAN), N.code(KIAT)
    both = " or ".join(sorted((her, his)))
    all_where(N, "Mr Tan and Ms Tan", f"{his} and {her}")
    same(N.out("Ask Tan", "typed"), f"Ask {both}")
    all_where(N, "Mrs Tan", both)                                                  # no Mrs Tan: the chat asks which
    all_where(N, "Dr Tan Boon", his); all_where(N, "Mr Tan Wei Ling", her)         # the words fit one person
    same(N.out("Ask Boon", "typed"), f"Ask {his}")
    N = a_names("Ms Siti Aminah", "Ms Siti Aisyah")
    all_where(N, "Ms Siti", f"{N.code('Ms Siti Aisyah')} or {N.code('Ms Siti Aminah')}")
    all_where(N, "Ms Siti Aminah", N.code("Ms Siti Aminah"))
    N = a_names("Ms Lee Hui", "Ms Lee Hui Min")
    all_where(N, "Lee Hui, hui lee and Lee Min", "T01, T01 and T02")
    N = a_names("Ms Goh Ah (HOD)", "Mr Goh Ah (HOD)")
    all_where(N, "MS GOH AH (HOD) and goh ah (hod)", f"{N.code('Ms Goh Ah (HOD)')} and T01 or T02")
    for w in ("list", "app"): same(a_names("Ms Lin Lin Goh", TAN).out("Lin Lin, Wei Wei and Lin", w), "T01, Wei Wei and Lin")    # a word said twice is there twice
    # a name that is another name with more words: the whole name is the one meant
    N = a_names("Ms Lee Hui", "Ms Lee Hui Min", "Lee Hui")
    all_where(N, "Ms Lee Hui", N.code("Ms Lee Hui")); all_where(N, "Ms Lee Hui Min", N.code("Ms Lee Hui Min")); all_where(N, "Lee Hui and lee hui", f"{N.code('Lee Hui')} and {N.code('Lee Hui')}")
    N = a_names("Mr Koh", "Mr Koh Ah Huat", "Kamala", "Ms Kamala Devi")
    all_where(N, "mr koh and KAMALA", f"{N.code('Mr Koh')} and {N.code('Kamala')}")
    N = a_names("Ms Tan Wei-Ling", "Ms Tan Wei Ling", "Ms TAN Wei Ling")           # the same words: as it is stored
    for n in ("Ms Tan Wei-Ling", "Ms Tan Wei Ling", "Ms TAN Wei Ling"): all_where(N, n, N.code(n))

@t
def a_name_of_one_word():
    N = a_names("Kamala", "Mr Koh", students=[("S1", "Kavin"), ("S2", "May")]); ka, ko = N.code("Kamala"), N.code("Mr Koh")
    all_where(N, "Kamala, KAMALA and Mr Koh", f"{ka}, {ka} and {ko}")              # the whole stored name, in every text
    all_where(N, "Koh and Kavin", f"{ko} and a student")
    all_where(N, "kamala, koh, kavin, May", "kamala, koh, kavin, May")             # not in small letters, and never a month
    N = a_names("Relief1", "Ms Tan2", "Relief Teacher 3", "Staff 3A")
    all_where(N, "Relief1, Ms Tan2, Relief Teacher 3 and Staff 3A", ", ".join(N.code(x) for x in ("Relief1", "Ms Tan2", "Relief Teacher 3")) + f" and {N.code('Staff 3A')}")
    all_where(N, "3A, 3 teachers, staff of 3A", "3A, 3 teachers, staff of 3A")
    N = a_names("Mr Koh", "Ms Koh Li Ting")
    all_where(N, "Mr Koh", N.code("Mr Koh")); all_where(N, "Ms Koh", N.code("Ms Koh Li Ting"))
    all_where(N, "Koh", f"{N.code('Mr Koh')} or {N.code('Ms Koh Li Ting')}")

@t
def titles_with_stops_in_any_case_and_the_ones_used_here():
    N = a_names(TAN, "Ms Siti Aminah binte Yusof", RIZAL, "Grace Lee", "Mr Koh Ah Huat")
    c = N.code(TAN)
    for text in ("Ms. Tan", "Ms.Tan", "ms tan", "MS TAN", "Ms  Tan", "Ms\u00a0Tan", "Ms\nTan", "Miss Tan", "miss tan", "Mdm. Tan Wei Ling", "(Ms) Tan", "Dr Ling"):
        all_where(N, f"see {text} now", f"see {c} now")
    all_where(N, "Madam Tan Wei Ling", c); all_where(N, "madam tan and MADAM. Ling", f"{c} and {c}")
    all_where(a_names(TAN, "Mdm Tan Ai"), "Madam Tan and Mdm Tan", "T01 and T01")
    all_where(N, "Cikgu Siti", N.code("Ms Siti Aminah binte Yusof")); all_where(N, "Encik Ahmad", N.code(RIZAL))
    all_where(N, "Puan Aminah, Ustazah Siti, Ustaz Rizal, Prof. Koh and Professor Koh",
              ", ".join([N.code("Ms Siti Aminah binte Yusof")] * 2) + f", {N.code(RIZAL)}, " + " and ".join([N.code("Mr Koh Ah Huat")] * 2))
    all_where(N, "Teacher Grace and teacher Grace", f"{N.code('Grace Lee')} and {N.code('Grace Lee')}")
    all_where(N, "Sir Koh", N.code("Mr Koh Ah Huat"))
    all_where(N, "Teacher\nGrace Lee, Teacher\tGrace Lee", f"Teacher\n{N.code('Grace Lee')}, Teacher\t{N.code('Grace Lee')}")      # the head of a column
    for text in ("teacher grace", "sir koh", "every teacher", "Teacher Alicia", "Dear Sir or Madam", "the teacher, Grace", "the professor"):
        same(N.out(text, "list"), text)
    for text in ("teacher grace", "sir koh", "Teacher Alicia", "Dear Sir or Madam"): same(N.out(text, "typed"), text)
    all_where(a_names(TAN, students=[("S1", "Grace Ho")]), "Teacher Grace", "Teacher Grace")       # Grace is not a teacher
    all_where(N, "the teacher Ms Tan", f"the teacher {c}")
    all_where(a_names(), "the teacher Alicia Ng. They miss Alicia Ng.", "the teacher a student. They miss a student.")
    all_where(a_names(students=[("S1", "Siti Aminah @ Rose")]), "the teacher Siti Aminah @ Rose, Siti Aminah", "the teacher a student, a student")
    all_where(a_names("Teacher A"), "Teacher A, Ms a student, Miss a lesson", "T01, Ms a student, Miss a lesson")
    assert set(HONORIFICS) < set(names.TITLES) and {"madam", "cikgu", "encik", "puan", "ustaz", "ustazah", "sir", "teacher", "prof", "professor"} < set(names.TITLES)
    for h in HONORIFICS: all_where(N, f"{h} ling, {h.upper()}. LING", f"{c}, {c}")

@t
def names_in_every_kind_of_text():
    N = a_names(TAN, RIZAL, "Ms Nur'Aisyah Salleh", "Mr Kumar s/o Raman", "Ms Siti binte Ahmad", "Ms Jean-Marie Png", "Tan Ah Kow (Mrs Teo)", "Mr Teo Wee"); c = N.code(TAN)
    for before, after in (("", ""), ("(", ")"), ("[", "]"), ('"', '"'), ("- ", "\n"), ("\t", "\t"), ("x:", ";"), ("1. ", "."), ("3A/", "/3B"), ("**", "**"), ("", "'s"), ("", "\u2019s"), ("<b>", "</b>"), ("a, ", ", b"), ("\u201c", "\u201d"), ("Mon ", " 3")):
        all_where(N, f"{before}Tan Wei Ling{after}", f"{before}{c}{after}")
        all_where(N, f"{before}Ms Tan{after}", f"{before}{c}{after}")
    all_where(N, "Tan Wei\nLing, Tan  Wei   Ling, Tan\tWei Ling, Tan Wei-Ling, Wei-Ling, Tan Wei-\nLing, Ms\tTan", f"{c}, {c}, {c}, {c}, {c}, {c}, {c}")
    all_where(N, 'Ms "Tan" and Ms *Ling*', f'{c}" and {c}*')
    same(N.out("Wei - Ling. Wei; Ling: Wei / Ling, Wei & Ling", "list"), "Wei - Ling. Wei; Ling: Wei / Ling, Wei & Ling")       # not side by side
    all_where(N, "tan.wei.ling@example.org, tan_wei_ling@example.org, Tan_Wei_Ling.docx", f"{c}@example.org, {c}@example.org, {c}.docx")
    aisyah, kumar, siti, jean, teo = (N.code(x) for x in ("Ms Nur'Aisyah Salleh", "Mr Kumar s/o Raman", "Ms Siti binte Ahmad", "Ms Jean-Marie Png", "Tan Ah Kow (Mrs Teo)"))
    all_where(N, "Nur'Aisyah, Nur\u2019Aisyah, Nur Aisyah Salleh, Ms Aisyah", f"{aisyah}, {aisyah}, {aisyah}, {aisyah}")
    all_where(N, "Kumar s/o Raman, Mr Kumar S/O Raman, Mr Raman, Raman Kumar, s/o Raman, Kumar S/O", ", ".join([kumar] * 6))
    all_where(N, "Jean-Marie, Ms Jean Marie, Marie Png", f"{jean}, {jean}, {jean}")
    all_where(N, "Siti binte Ahmad, Ms Siti, Ms Ahmad, Ahmad Siti", f"{siti}, {siti}, {siti}, {siti}")
    same(N.out("Dear Mrs, or Mr", "typed"), "Dear Mrs, or Mr")
    all_where(N, "Tan Ah Kow (Mrs Teo), Mrs Teo, Tan Ah Kow", f"{teo}, {teo}, {teo}")
    same(N.out("Ask Ahmad, Siti and Rizal", "typed"), f"Ask {N.code(RIZAL)} or {siti}, {siti} and {N.code(RIZAL)}")
    all_where(N, "bin and binte, s/o and d/o", "bin and binte, s/o and d/o")       # what joins a name is not a name
    same(N.out("And of The Bin", "typed"), "And of The Bin")
    N = a_names("Nora and Tan", "Ms Hope of Glory")
    same(N.out("Hope and Nora of 3A. And so on.", "typed"), f"{N.code('Ms Hope of Glory')} and {N.code('Nora and Tan')} of 3A. And so on.")
    all_where(N, "Nora and Tan", N.code("Nora and Tan")); all_where(N, "3A and 3B of 2027", "3A and 3B of 2027")

@t
def the_same_letters_in_another_form():
    N = a_names(TAN, "Ms Ren\u00e9e Tho\u00e9", "Mr Rafiq Salim"); c, r = N.code(TAN), N.code("Ms Ren\u00e9e Tho\u00e9")
    for text in ("Rene\u0301e Thoe\u0301", "Renee Thoe", "REN\u00c9E THO\u00c9"): all_where(N, text, r)
    all_where(N, "\uff34\uff41\uff4e Wei Ling", c); all_where(N, "T\u00adan W\u200bei\u200b Ling", c)
    all_where(N, "Ra\ufb01q Salim", N.code("Mr Rafiq Salim")); all_where(N, "Tan\u2009Wei\u3000Ling", c)

@t
def a_comma_in_the_stored_order_hides_the_whole_name_in_a_list():
    N = a_names(TAN, "Ms Grace Lim", "Lee, Hui Min"); c = N.code(TAN)
    for w in ("list", "app"): same(N.out("Tan, Wei Ling", w), c)
    same(N.out("Tan, Wei Ling", "typed"), f"{c}, {c}")
    same(N.out("Ask Grace, Lim and Tan", "typed"), f"Ask {N.code('Ms Grace Lim')}, {N.code('Ms Grace Lim')} and {c}")
    all_where(N, "Lee, Hui Min", N.code("Lee, Hui Min"))
    same(a_names().out("English, 3 May, Lim", "list"), "English, 3 May, Lim")

@t
def small_words_and_times_are_not_people():
    N = a_names("Ms Do Thi An", ("Mr Ang Min", "AM"), "Mr Will Tay", ("Ms On Go", "On"), ("Mr S Kumar", "S"), "Mr A Rahman", students=[("S1", "Go Kah On")])
    text = "3A will do an extra paper and go on to 3B by 8 am"
    all_where(N, text, text)
    all_where(N, "from 8.00 AM to 9 AM", "from 8.00 AM to 9 AM")
    same(N.out("AM is free", "app"), f"{N.code('Mr Ang Min')} is free")
    all_where(N, "Mr Tay will be away and mr tay will go", f"{N.code('Mr Will Tay')} will be away and {N.code('Mr Will Tay')} will go")
    same(N.out("On Mon, S is on", "app"), "On Mon, S is on")                       # a short name that is a small word or one letter
    same(N.out("Ask Kumar a question", "typed"), f"Ask {N.code('Mr S Kumar')} a question"); same(N.out("KUMAR'S", "typed"), f"{N.code('Mr S Kumar')}'S")
    same(a_names(LIM, students=[("S1", "Tan Will An")]).out("Tan will be away, Tan Will", "list"), "Tan will be away, a student")
    N2 = a_names("Ms Li An"); same(N2.out("An\nLi", "typed"), "T01"); all_where(N2, "Ms Li\nAn", "T01")
    same(N.out("A paper is on Mon", "typed"), "A paper is on Mon")                 # one letter alone is not a name
    all_where(N, "Mr S and Mr Kumar's", f"{N.code('Mr S Kumar')} and {N.code('Mr S Kumar')}'s")
    all_where(N, "S. Kumar, S Kumar, Mr. S. Kumar", ", ".join([N.code("Mr S Kumar")] * 3))

@t
def codes_are_in_order_of_the_names_and_never_a_word_of_the_timetable():
    N = a_names(rooms=("Art Room", "T02"))
    same([N.code(n) for n in (LIM, RIZAL, KOH, TAN)], ["T01", "T03", "T04", "T05"])
    same(N.known_codes(), frozenset({"T01", "T03", "T04", "T05"}))
    all_where(N, "Room T02 and Mr Koh", "Room T02 and T04")
    same(N.back("T02 is a room, T04 is not"), "T02 is a room, Mr Art Koh is not")
    raises(KeyError, lambda: N.code("Nobody")); raises(KeyError, lambda: N.code(""))
    pub = a_pub(); pub["model"]["lessons"][0]["group"] = "T01"; pub["model"]["setup"]["subjects"] = [dict(subject="Drama", code="T04")]
    N = names.Names(pub, people((TAN, "T03"), RIZAL), kids(("T02", "Bee Teo")))     # a group, a setup code, a short name, an ID
    same([N.code(RIZAL), N.code(TAN)], ["T05", "T06"])
    many = people(*[f"Ms Aaa{chr(97 + i // 26)}{chr(97 + i % 26)} Bbb" for i in range(120)])
    N = names.Names(None, list(reversed(many)), [])
    same([N.code(p["name"]) for p in many], [f"T{i:02d}" for i in range(1, 121)])
    same(N.back("T99, T100 and T1000"), f"{many[98]['name']}, {many[99]['name']} and T1000")

@t
def what_is_protected():
    pub = a_pub(subjects=("Design & Technology",))
    m = pub["model"]; m["levels"].append("Sec 9 Quill"); m["setup"]["subjects"] = [dict(subject="Music G3", code="MU")]; m["subjects"] = {"English": dict(short="EL", dept="LANG")}
    got = names.protected(pub)
    assert isinstance(got, frozenset) and all(w == w.casefold() for w in got)
    for w in ("monday", "mon", "sunday", "sun", "may", "september", "sep", "sec", "3", "3a", "4a", "english", "quill", "design", "technology", "music", "g3", "mu", "el", "art", "room", "lab", "hall", "lt1", "08"):
        assert w in got, w
    for w in ("tan", "rahman", "aisha", "lim", "rizal", "mr", "lang"): assert w not in got, w
    bare = names.protected(None)
    assert bare == names.protected({}) and {"mon", "monday", "may", "december", "dec"} < bare and "english" not in bare
    assert len(bare) == 7 * 2 + 12 * 2 - 1, "May is its own three letters"
    pub = a_pub(rooms=("Mdm Lim Studio",))                                         # a room with a person's name in it
    assert "lim" in names.protected(pub) and "mdm" not in names.protected(pub)
    N = names.Names(pub, people(LIM), [])
    all_where(N, "Mdm Lim", N.code(LIM)); same(N.out("Lim Studio", "typed"), "Lim Studio")

@t
def the_school_is_never_named():
    N = a_names(school="CTSS Sample School")
    all_where(N, "CTSS Sample School timetable", "the school timetable"); all_where(N, "at the CTSS  SAMPLE\nschool's hall", "at the school's hall")
    assert "the school" in a_names().out("CTSS Sample School timetable", "app")
    all_where(a_names(school="CTSS"), "ctss and CTSS exam, CTSSX", "the school and the school exam, CTSSX")
    all_where(a_names(school="St. Mary's"), "St. Mary's", "the school")
    for s in ("ABC", "", "School", "  "): all_where(a_names(school=s), "ABC school day", "ABC school day")
    pub = a_pub(); pub["meta"]["school"] = "Alpha Beta"; pub["model"]["school"]["name"] = "Gamma Delta"
    all_where(names.Names(pub, [], []), "Alpha Beta, Gamma Delta", "the school, the school")

@t
def codes_become_names_again():
    N = a_names(); c = N.code(TAN)
    for n in (TAN, RIZAL, LIM, KOH):
        for w in WHERES: same(N.back(N.out(f"{n} is on duty, as {n}", w)), f"{n} is on duty, as {n}"); same(N.out(N.back(N.out(n, w)), w), N.code(n))
    same(N.back(N.out("Ask Tan, TWL and ms ling", "typed")), f"Ask {TAN}, {TAN} and {TAN}")
    same(N.back(f"{c}'s, ({c}), {c}/{c}, {c}."), f"{TAN}'s, ({TAN}), {TAN}/{TAN}, {TAN}.")
    text = f"T99, T7, t01, X{c}, {c}A, {c}_1, _{c}, {c}0, L{c}"
    same(N.back(text), text)
    odd = "Tan Ah Kow (Mrs Teo)"; N = a_names(odd, TAN)
    for w in WHERES: same(N.back(N.out(f"{odd}, {TAN}", w)), f"{odd}, {TAN}")

@t
def whole_records_are_scrubbed_and_nothing_else_passes():
    N = a_names()
    src = {"a": [TAN], "b": 3, "c": "Alicia Ng", TAN: (RIZAL, None, True, 1.5, {"deep": ["TWL"]})}
    got = N.scrub(src, "app")
    same(got, {"a": [N.code(TAN)], "b": 3, "c": "a student", TAN: (N.code(RIZAL), None, True, 1.5, {"deep": [N.code(TAN)]})})
    assert got[TAN][2] is True and isinstance(got[TAN], tuple) and src["a"] == [TAN], "keys and the record given are unchanged"
    assert "Tan" not in N.scrub({"a": [TAN], "n": 3}, "app")["a"][0]
    same(N.scrub("TWL"), N.code(TAN)); same(N.scrub("TWL", "list"), "TWL"); same(N.scrub(["Ask Tan"], "typed"), [f"Ask {N.code(TAN)}"])
    class Own: pass
    for bad in (Own(), {1, 2}, b"Tan", [Own()], {"a": (Own(),)}, object): raises(TypeError, lambda: N.scrub(bad))
    try: N.scrub({"a": {TAN}})
    except TypeError as e: assert "Tan" not in str(e)

@t
def nothing_published_and_nobody_listed():
    for pub in (None, {}, dict(model=None, meta=None), dict(model={}), dict(model=dict(rooms=None, lessons=None, classes=None, school=None, setup=None))):
        N = names.Names(pub, None, None)
        all_where(N, "Ms Tan on Mon 3 May", "Ms Tan on Mon 3 May"); same(N.known_codes(), frozenset()); same(N.back("T01"), "T01")
        N = names.Names(pub, people(TAN), [])
        all_where(N, "Ms Tan on Mon 3 May", "T01 on Mon 3 May")
    N = names.Names(a_pub(), [dict(name=" Ms Tan Wei Ling ", short=None), dict(name=""), dict(name=None), {}, dict(name="Mr"), dict(name="---"), dict(name=TAN, short="XYZ")], [{}, dict(id=None, name=None), dict(id=7, name="")])
    all_where(N, "Ms Tan, Mr, ---, XYZ, 7", f"{N.code(TAN)}, Mr, ---, XYZ, 7")      # of two with one name the first is kept
    for bad in (None, 3, 2.5, ["Ms Tan"], {"a": 1}, b"Ms Tan"):
        for w in WHERES: assert N.out(bad, w) is bad
        assert N.back(bad) is bad
    for text in ("", " ", "\n", "...", "\ud800", "Ms", "Ms.", "Teacher", "\u0301"): all_where(N, text, text)
    same(N.out("Ask Tan", "somewhere else"), f"Ask {N.code(TAN)}"); same(N.out("Ask Tan", None), f"Ask {N.code(TAN)}")      # an unknown place hides the most

_FIRST = "Bao Cai Dewi Eng Farid Gita Hana Indra Jun Kiran Lian Mei Noor Omar Priya Qing Ravi Suri Tuan Umi Vani Wen Xin Yati Zul".split()
_LAST = "Aziz Beh Chng Das Foo Gan Heng Ismail Jalil Kwek Loh Maniam Neo Osman Poh Quah Rao Sng Toh Vasu Wee Yeo Zain".split()

def a_big_school():
    rnd = random.Random(7)
    def one(k): return " ".join([rnd.choice(_LAST)] + rnd.sample(_FIRST, k))
    staff = sorted({f"{rnd.choice(['Mr', 'Ms', 'Mdm', 'Mrs', 'Miss', 'Dr', 'Mr'])} {one(rnd.choice((1, 2, 2, 3)))}" for _ in range(160)})[:120]
    pupils = sorted({one(rnd.choice((2, 3, 3, 4))) for _ in range(1400)} - {n.split(" ", 1)[1] for n in staff})[:1000]
    assert len(staff) == 120 and len(pupils) == 1000
    return staff, [(f"S{i:04d}", n) for i, n in enumerate(pupils)]

@t
def nobody_known_leaks_in_any_form():
    """every teacher and student, every order of two or more of the words, with titles, in every kind of text: no word of the
    name is left (but one that is a month), and who it is is among the codes sent"""
    staff, pupils = a_big_school(); rnd = random.Random(11)
    N = names.Names(a_pub(), people(*staff), kids(*pupils))
    free = names.protected(a_pub())
    frames = ("{}", "see {} on Mon 3 May", "3A\t{}\t08:00", "({})", "{},", "Room 3-01: {}\n- next", "x {}'s")
    words = lambda s: {x.casefold() for x in re.findall(r"[^\W_]+", s)}
    n = 0
    for name in staff:
        ws = name.split()[1:]
        for k in range(1, len(ws) + 1):
            for p in itertools.permutations(ws, k):
                forms = [f"{h} {' '.join(p)}" for h in ("Ms", "mr.", "MDM", "Madam", "Cikgu")]
                if k > 1: forms += [" ".join(p), "\n".join(p), " ".join(p).upper(), "-".join(p).lower()]
                for f in forms:
                    for w in WHERES:
                        got = N.out(rnd.choice(frames).format(f), w); n += 1
                        assert not (words(" ".join(p)) - free) & words(got), (f, w, got)
                        if k == len(ws) and "\n" not in f and f.split()[0].casefold().strip(".") not in names.TITLES or f == " ".join([name.split()[0], *p]):
                            assert N.code(name) in got, (f, w, got)
    for i, name in pupils:
        ws = name.split()
        for k in range(2, len(ws) + 1):
            for p in itertools.permutations(ws, k):
                got = N.out(rnd.choice(frames).format(rnd.choice((" ".join(p), " ".join(p).lower(), " ".join(p).upper()))), rnd.choice(WHERES)); n += 1
                assert not (words(" ".join(p)) - free) & words(got), (p, got)
        all_where(N, f"({i})", "(a student)")
    assert n > 10000, n
    for name in staff:
        for w in WHERES: same(N.out(name, w), N.code(name)); same(N.back(N.out(name, w)), name); same(N.out(N.out(name, w), w), N.code(name))

@t
def ordinary_text_never_changes():
    """any run of days, months, dates, classes, subjects and rooms, beside each other in any order, in every kind of text, while
    people are called May, Art, June, Mon and Grace and a class is called Grace"""
    pub = a_pub(subjects=("Art G3", "Design & Technology", "Mathematics"))
    pub["model"]["classes"].append(dict(name="3 Grace", level="Sec 3", size=30, home="", parents=[]))
    N = names.Names(pub, people(LIM, KOH, "Ms June Tan", ("Mr Mon Sat", "MS"), "Grace Lee", "Mr English", "Hall", "Ms Room May Art"), kids(("S1", "May June Art"), ("S2", "Grace"), ("S3", "June May Ho")))
    rnd = random.Random(5)
    bits = "Mon Tue Wednesday SAT 3 14 2027 May MAY may June jun Art ART art Room Hall English Mathematics Design Technology Grace grace 3A 3-01 08:00 LT1 Sec Lab paper 1 2 the and at in of on to for".split()
    for _ in range(3000):
        text = "".join(rnd.choice(bits) + rnd.choice((" ", " ", " ", ", ", "\t", "\n", ". ", " - ", ": ")) for _ in range(rnd.randint(1, 9)))
        all_where(N, text, text)

@t
def a_long_text_is_quick():
    staff, pupils = a_big_school(); rnd = random.Random(3)
    N = names.Names(a_pub(), people(*staff), kids(*pupils))
    words = _FIRST + _LAST + ["Mon", "3", "May", "English", "Ms", "Mr", "Room", "to", "an", "S0001", "T01"]
    for sep in (" ", "\n", ", "):
        text = ""
        while len(text) < 20000: text += rnd.choice(words) + sep
        for w in WHERES:
            at = time.process_time(); N.out(text[:20000], w); took = time.process_time() - at        # the work, not the wait: it is 0.05 s
            assert took < 0.5, f"{took:.2f} s"

print(f"{COUNT} plan tests passed")
