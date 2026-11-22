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

def coded(*codes, **kw):
    """a published timetable with these setup codes of subjects"""
    pub = a_pub(**kw); pub["model"]["setup"]["subjects"] = [dict(subject="Drama", code=c) for c in codes]
    return pub

def people(*who):
    return [dict(name=w if isinstance(w, str) else w[0], short=w if isinstance(w, str) else w[1], depts=[], role="", teaches=True, staff_only=False) for w in who]

def kids(*who):
    return [dict(id=i, name=n, cls="3A", level="Sec 3", groups=[]) for i, n in who]

def a_names(*staff, students=KIDS, **kw):
    return names.Names(a_pub(**kw), people(*(staff or STAFF)), kids(*students))

def all_where(N, text, want):
    for w in WHERES: same(N.out(text, w), want)

def apart(N, text, typed, rest):
    """one answer in a person's own words, another in a list and in the app's words"""
    same(N.out(text, "typed"), typed)
    for w in ("list", "app"): same(N.out(text, w), rest)

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
    N = a_names((TAN, "TWL"), ("Mr Tan Boon Kiat", "Tan"))                        # the longest match
    same(N.out("Tan Wei Ling, Tan and 1TWL", "typed"), f"{N.code(TAN)}, {N.code('Mr Tan Boon Kiat')} and 1 {N.code(TAN)}")
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
    N = a_names("May (Art)", "Tan Ah Kow (Will)")
    all_where(N, "May (Art), Tan Ah Kow (Will)", "May (Art), T02"); same(N.out("Tan Ah Kow (will be late)", "typed"), "T02 (will be late)")

@t
def a_date_or_a_room_beside_a_name_stays_in_typed_words():
    N = a_names(); lim, koh = N.code(LIM), N.code(KOH)
    for text, want in (("Mdm Lim may be away", f"{lim} may be away"), ("mdm lim may be away", f"{lim} may be away"), ("Mdm Lim May 3", f"{lim} May 3"),
                       ("Mdm Lim May 2027", f"{lim} May 2027"), ("Mdm Lim May 3rd", f"{lim} May 3rd"), ("When may Lim invigilate?", f"When may {lim} invigilate?"),
                       ("on 3 May Lim is away", f"on 3 May {lim} is away"), ("Put Mr Koh Art Room 3A", f"Put {koh} Art Room 3A"),
                       ("Sec 3\tArt\tKoh\t3 May", f"Sec 3\tArt\t{koh}\t3 May"), ("May\nLim", f"May\n{lim}"),
                       ("3 May\nLim, Lim\nMay 3", f"3 May\n{lim}, {lim}\nMay 3"), ("Exams in May, Lim is away", f"Exams in May, {lim} is away"),
                       ("the Tan Wei Ling", f"the {N.code(TAN)}"), ("Lim, May is full", f"{lim}, May is full"), ("on 3rd May Lim is away", f"on 3rd May {lim} is away"), ("English, 3 May, Lim", f"English, 3 May, {lim}")):
        same(N.out(text, "typed"), want)
    N = a_names(LIM, "Mdm Lim Bee Hoon"); same(N.out("on 3 May Lim Bee is away", "typed"), f"on 3 May {N.code('Mdm Lim Bee Hoon')} is away")      # the one word left is looked at again
    N = a_names("Ms Osman Jun Vani English", students=[("S1", "Tan May Ling")])
    same(N.out("Jun   Vani English \t osman", "typed"), "Jun   T01")                                                 # the rest of it, in every cell
    same(N.out("Tan May 3, Ling May 3, 3 May Ling", "typed"), "a student 3, a student 3, 3 a student")                                         # nothing is left that is a match
    same(N.out("Tan\nMay 3, 3 May\nTan", "typed"), "Tan\nMay 3, 3 May\nTan")                                        # part of a student's name
    same(a_names("Ms Tan Wei May").out("Ms Wei May English", "typed"), "T01 English")                                  # in the name's own order it is the name
    same(a_names(LIM, students=[("S1", "May Long Hui")]).out("3 May long papers, May Long", "typed"), "3 May long papers, a student")

@t
def a_date_or_a_room_beside_a_name_stays():
    N = a_names(); lim, koh = N.code(LIM), N.code(KOH)
    all_where(N, "English\tMdm Lim\tMay 3", f"English\t{lim}\tMay 3")
    all_where(N, "on 3 May\nMdm Lim is away", f"on 3 May\n{lim} is away")
    all_where(N, "Mr Koh\nArt\t3 May", f"{koh}\nArt\t3 May")
    all_where(a_names(subjects=("Food and Nutrition",)), "Mr Koh Art and Mdm Lim May and", f"{koh} and {lim} and")
    for text in ("3A will miss Art", "they miss May, so miss English"): all_where(N, text, text)
    all_where(N, "May Mdm Lim come?", f"May {lim} come?")
    all_where(N, "tell each teacher May 3 is fixed", "tell each teacher May 3 is fixed")
    all_where(N, "Teacher Art Room 3A", "Teacher Art Room 3A"); all_where(N, "Teacher\nArt\t3A", "Teacher\nArt\t3A")
    all_where(N, "Mdm Lim\tMay 3\tMr Koh\tArt", f"{lim}\tMay 3\t{koh}\tArt")
    all_where(N, "Mdm May\nLim", lim); same(N.out("May\nLim; Koh\nArt", "list"), f"{lim}; {koh}")                    # a line cut in a name
    all_where(a_names("Ms Tan Wei May"), "Tan Wei May 3A", "T01 3A")
    # what is left out of a name is never a word that only a name has
    for text in ("1 May Lim", "Lim May 3", "May Lim 3"):
        for w in WHERES: assert "Lim" not in N.out(text, w), (text, w, N.out(text, w))

@t
def in_a_list_part_of_a_name_beside_a_date_or_a_subject_stays():
    """the stored names have more words than the text: a month or weekday bound to a day's number never joins part of a name, and
    protected words are cut from its ends, so one word of a name alone is left, which a list leaves alone"""
    N = a_names("Ms May Lim Hui", "Mr Art Koh Beng", students=[("S1", "Goh Jun Wei"), ("S2", "Tan May Ling Ai")]); lim, koh = N.code("Ms May Lim Hui"), N.code("Mr Art Koh Beng")
    for text in ("Sec 3 Art Koh", "Mon 3 Jun Goh 8.00", "on 3 May Lim", "Lim May 3", "Koh Art", "Art, Koh", "Jun Goh", "May\tLim", "Art   Koh", "3A Goh Jun", "Mdm May 3", "Lim\nMay 3"):
        for w in ("list", "app"): same(N.out(text, w), text)
    for w in ("list", "app"):
        same(N.out("Ms Lim May, Ms May, Mr Koh Art Room", w), f"{lim} May, {lim}, {koh} Art Room")          # a title makes a person of what is left
        same(N.out("May Tan Ling, Ling Ai May 3, Koh Beng and", w), f"May a student, a student May 3, {koh} and")       # and so do two words
        same(N.out("Tan May Ling", w), "a student")                                                        # in the middle it is the name

@t
def in_a_list_a_whole_name_of_more_words_is_coded_beside_a_date():
    N = a_names("Mr Art Koh Beng", students=[("S1", "Goh Jun Wei"), ("S2", "Yeo Jun")]); koh = N.code("Mr Art Koh Beng")
    for text in ("Goh   Jun   Wei", "Goh\tJun\tWei", "wei jun GOH", "Goh, Jun Wei", "Yeo\tJun", "Yeo   Jun", "jun Yeo", "Jun\tYeo"): all_where(N, text, "a student")
    apart(N, "Mon 3 Jun Wei Goh 8.00, Sec 3 Art Koh Beng", f"Mon 3 Jun a student 8.00, Sec 3 {koh}", f"Mon 3 a student 8.00, Sec 3 {koh}")
    for w in ("list", "app"): same(N.out("wei GOH jun; Jun\nGoh\nWei", w), "a student; a student")
    for w in ("list", "app"): same(N.out("Yeo Jun 3, Sec 3 Jun Yeo, 3A Jun Yeo", w), "a student 3, Sec 3 a student, 3A a student")      # the 3 of a level is no day

@t
def in_a_list_a_whole_name_of_two_words_is_coded_though_one_is_a_subject_or_a_month():
    """the stored names are exactly the two words: they are always coded, and the subject or the date is asked about"""
    N = a_names(); lim, koh = N.code(LIM), N.code(KOH)
    for w in ("list", "app"):
        same(N.out("Sec 3 Art Koh", w), f"Sec 3 {koh}")
        same(N.out("3 May Lim, Lim May 3, Art\tKoh, 3 May\tLim, Art, Koh, Mdm Lim May 3", w), f"3 {lim}, {lim} 3, {koh}, 3 {lim}, {koh}, {lim} 3")
        same(a_names("Mdm May", "Mr Art").out("Mdm May 3, 3 May, Mr Art Room, May 3", w), "T01 3, 3 May, T02 Room, May 3")       # a whole name of one word, with its title
        same(N.out("when MAY lim, Mr Koh Art Room, Lim may; 3 May\nLim; Lim\nMay 3", w), f"when {lim}, {koh} Room, {lim}; 3 {lim}; {lim} 3")

@t
def a_whole_name_is_coded_whatever_number_stands_before_it():
    N = a_names(students=[("K1", "Goh Jun"), ("K2", "Sun Yang"), ("K3", "June Lee")])
    for before in ("S3 EL P1 {}", "EL P2 {} 3A", "8.30 {}", "9.15 - 10.30 {}", "Room 3-01 {}", "S3 {}", "Group 2 {}", "1h 30 {}", "Mon 3 {} 8.00", "{} 3", "3 {} 4", "1) {}", "(2) {}", "3. {}", "4\t{}", "2027 {}", "3rd {}"):
        for n in ("Sun Yang", "June Lee", "Goh Jun", "Jun Goh", "YANG SUN"):
            for w in ("list", "app"): same(N.out(before.format(n), w), before.format("a student"))
    all_where(N, "Mon 3 Jun Goh 8.00; S3 EL P1 Sun Yang; 8.30 June Lee", "Mon 3 a student 8.00; S3 EL P1 a student; 8.30 a student")

@t
def whole_names_are_decided_first():
    """over the whole text, the whole names that cover the most words; nothing later undoes one"""
    N = names.Names(coded("LI", "MA"), people("Mdm May Lee Hoon", "Mdm May Wong"), kids(("S1", "Li Hao Yu"), ("S2", "Li Yang"), ("S3", "Ma Jia Le"), ("S4", "Ma Rui"), ("S5", "Sun Hao Yu"), ("S6", "Sun Yang")))
    all_where(N, "LI HAO YU\nLI YANG\nMA JIA LE\nMA RUI", "a student\na student\na student\na student")
    for sep in ("\n", "\t", " ", ", ", "   ", "; ", " | ", "\n\n", " - ", " and "):
        for x, y in itertools.permutations(("Sun Hao Yu", "Sun Yang", "Li Yang", "MA RUI", "May Wong"), 2):
            if sep in (", ", "; ") and "May" in x + y: continue
            want = lambda n: "T02" if "May" in n else "a student"
            all_where(N, f"{x}{sep}{y}", f"{want(x)}{sep}{want(y)}")
    all_where(N, "SUN YANG, SUN HAO YU", "a student, a student"); all_where(N, "May Lee Hoon\nMay Wong", "T01\nT02")
    M = a_names(); all_where(M, "May Lim, May 3; Art Koh, Art Room", f"{M.code(LIM)}, May 3; {M.code(KOH)}, Art Room")
    M = a_names(students=[("S1", "Ann Bo"), ("S2", "Cy Di"), ("S3", "Ann Bo Cy Di")]); all_where(M, "Ann Bo Cy Di", "a student")      # the fewest
    M = a_names(students=[("S1", "Ann Bo"), ("S2", "Cy Di"), ("S3", "Bo Cy Di Ed")]); same(M.out("Ann Bo Cy Di Ed", "list"), "Ann a student")      # the fewest, of as many words
    M = a_names(TAN, students=[("S1", "Tan Wei Ling Bo Ai"), ("S2", "Alicia Ng")]); same(M.out("Tan Wei Ling Bo: Ng, Alicia", "list"), "T01 Bo: a student")      # not a longer part
    M = a_names("Ms Loh Ai", students=[("S1", "Sun Loh"), ("S2", "Kim Zain"), ("S3", "Kim Loh")]); same(M.out("8.30 SUN LOH\tKIM ZAIN", "typed"), "8.30 SUN T01\ta student")      # in typed words too
    M = a_names(TAN, students=[("BO TAN", "Cy Foo")]); all_where(M, "BO TAN WEI LING", "BO T01")
    M = a_names(students=[("S1", "Ann Bo"), ("S2", "Bo Cy Di")]); all_where(M, "Bo Ann Bo Cy Di", "a student a student")              # the most words: not Ann Bo twice
    M = a_names(students=[("S1", "Wee Suri"), ("S2", "Suri May"), ("S3", "Yeo Eng"), ("S4", "English Yeo")])
    for w in ("list", "app"): same(M.out("Wee, Suri May 3: English Yeo Eng 3A: Suri May", w), "a student May 3: English a student 3A: a student")      # of as many words, the ones only a name has
    M = a_names("Ms Tan Wei Ling", students=[("S1", "Wei Ling Ho"), ("S2", "Ho Min Jo Bo")]); all_where(M, "Wei Ling Ho Min Jo Bo", "T01 a student")      # not the first that fits
    M = a_names(TAN, students=[("S1", "Alicia Ng"), ("S2", "Ng Wei Jie"), ("S3", "Bo Tan")]); all_where(M, "Alicia Ng, Wei Jie; Ng, Alicia Tan, Bo", "a student, a student; a student a student")      # a comma gives way to what hides more

@t
def a_title_in_capitals():
    c = names.Names(a_pub(rooms=("Art Room", "Lim Studio")), people("Mdm Lim Bee Hoon"), []); all_where(c, "MDM LIM, PUT MDM LIM IN THE HALL", "T01, PUT T01 IN THE HALL")
    N = names.Names(coded("MA", "LI", subjects=("Art",)), people("Mdm Lim Bee Hoon", "Ms Ma Li Na", "Mr Li Jun Wei", "Mdm May Lim Hui", KOH), []); c = N.code
    all_where(N, "PUT MDM LIM BEE IN THE HALL, MR ART, MS MA", f"PUT {c('Mdm Lim Bee Hoon')} IN THE HALL, {c(KOH)}, {c('Ms Ma Li Na')}")
    all_where(N, "MDM LIM, MDM MAY LIM, MDM MAY", f"{c('Mdm Lim Bee Hoon')} or {c('Mdm May Lim Hui')}, {c('Mdm May Lim Hui')}, {c('Mdm May Lim Hui')}")
    apart(N, "MR LI JUN", c("Mr Li Jun Wei"), f"{c('Mr Li Jun Wei')} JUN")
    all_where(N, "3A WILL MISS ART. MISS ENGLISH, 3B!", "3A WILL MISS ART. MISS ENGLISH, 3B!")                       # a subject is missed
    all_where(N, "MISS MAY, MISS LIM BEE, Miss Art, MISS KOH, MISS Art", f"{c('Mdm May Lim Hui')}, {c('Mdm Lim Bee Hoon')}, {c(KOH)}, {c(KOH)}, {c(KOH)}")
    all_where(a_names("MISS ART TAN", subjects=("Art",)), "MISS ART TAN, Miss Art Tan", "T01, T01")                  # as it is stored

@t
def a_unit_after_a_number_stays():
    N = a_names("Mr Jun Min", "Ms Tan Hui Min", "Ms Min Li Goh", students=[("K1", "Min Jun Tan"), ("K2", "Min Thu"), ("K3", "Hr Ong Bo Yi")]); hui, goh = N.code("Ms Tan Hui Min"), N.code("Ms Min Li Goh")
    all_where(N, "1h 50min\tTan Hui Min\tHall", f"1h 50min\t{hui}\tHall"); all_where(N, "90 min, Tan Hui Min", f"90 min, {hui}")
    all_where(N, "1h 50min (Tan Hui Min)", f"1h 50min ({hui})"); all_where(N, "90 min\tTan Hui Min", f"90 min\t{hui}"); all_where(N, "90 min Tan Hui Min", f"90 min {hui}")
    all_where(N, "take 90 min Jun Tan", "take 90 min a student"); all_where(N, "90 min Jun Tan\n90 MIN LI GOH", f"90 min a student\n90 MIN {goh}")        # the rest of a whole name of three
    for text in ("1h30min Thu", "90 min Thu 3 Oct", "90 min Jun 3", "90 Min Jun", "Paper 4 Min Thu", "1h 30 min Thu", "46 Min Thu", "0451 Min Thu", "045 Min Thu", "0 Min Thu", "1" * 5000 + " Min Thu", "45 min\tThu 3 Oct", "30 hr\tOng", "it is 4 Min Thu"): all_where(N, text, text)
    all_where(N, "1 Min Jun Tan", "1 a student"); all_where(N, "1 MIN JUN TAN\n2 Min Li Goh\n3 Tan Min Jun\n4\tMin Jun Tan\n5 Hr Ong Bo Yi\n45 min thu", f"1 a student\n2 {goh}\n3 a student\n4\ta student\n5 a student\n45 a student")
    all_where(N, "English\t4 Min Thu\t3A | 12 Min Thu   7 Min Thu", "English\t4 a student\t3A | 12 a student   7 a student")                # the number of a line, or of a cell
    all_where(N, "Jun5 min Tan", "a student")                                                                         # the 5 is a footnote's
    all_where(N, "3 Min Tan Jun", "3 Min a student")                                                                  # not in the stored order
    all_where(N, "Sec 3 Min Thu; 2) Min Thu; 3. Min Thu; S3 EL P1 Min Thu", "Sec 3 a student; 2) a student; 3. a student; S3 EL P1 a student")      # no length: a level, a line, a paper

@t
def a_title_is_a_teachers():
    N = a_names(TAN, "Mdm Goh Siew Bee", students=[("S1", "Alicia Tan"), ("S2", "Grace Goh Hui"), ("S3", "May Tan"), ("S4", "Tan Wei Jie Bo")]); c, goh = N.code(TAN), N.code("Mdm Goh Siew Bee")
    all_where(N, "Tell Ms Tan, Alicia is away", f"Tell {c}, Alicia is away"); all_where(N, "Ms Tan (Alicia)", f"{c} (Alicia)"); all_where(N, "Ms Tan Alicia", f"{c} Alicia")
    all_where(N, "Ask Mdm Goh, Grace and Faith", f"Ask {goh}, Grace and Faith"); all_where(N, "Mdm Goh Grace Hui", f"{goh} a student")
    all_where(N, "Ms Tan Wei Jie Bo", f"{c} a student")                                                              # what is left is looked at on its own
    M = a_names("Mr Tan Boon Kiat", "Mdm Lee Siew", students=[("S1", "May Tan"), ("S2", "June Lee")])
    all_where(M, "S3 EL P1,Mr Tan,May 3,8.00", f"S3 EL P1,{M.code('Mr Tan Boon Kiat')},May 3,8.00"); all_where(M, "Mdm Lee June 3", f"{M.code('Mdm Lee Siew')} June 3")
    M = a_names("Ms Siti Hawa", students=[("S1", "Siti @ Rose"), ("S2", "Aminah @ Rose")]); all_where(M, "Ms Siti @ Rose, Ms Aminah @ Rose", "T01 @ Rose, Ms a student")
    all_where(N, "Miss Alicia Tan; Dr Grace Goh Hui", "Miss a student; Dr a student")                                # no teacher has the word after the title

@t
def long_ids_are_found_anywhere():
    N = a_names(students=[("T0123456A", "Alicia Ng"), ("T0123456B", "Bo Yeo Li"), ("S101", "Cy Wee"), ("3A-001", "Di Ang"), ("A12345", "Ed Foo"), ("250012", "Fu Gan"), ("K12345", "Gi Heo"), ("K123456", "Hu Ivy"), ("9Z9Z9Z", "Ip Jo")])
    all_where(N, "BaoA12345Cai, x3A-001, K123456x, 9Z9Z9Z9Z, T0123456AS101, 250012, 9250012", "Bao a student Cai, x a student, a student x, a student 9Z, a student a student, a student, 9250012")
    all_where(N, "T0123456AAlicia Ng", "a student a student"); all_where(N, "T0123456ABo Yeo Li", "a student a student"); all_where(N, "Bo Yeo LiT0123456B", "a student a student")
    all_where(N, "xT0123456Ay, t0123456a/T0123456B, 1T0123456A2, T0123\u200b456A, \uff340123456A, 3a\u2011001, T0123456AT0123456B", "x a student y, a student/a student, 1 a student 2, a student, a student, a student, a student a student")
    all_where(N, "S1012, XS101, T0123456, T0123456C, A1234", "S1012, XS101, T0123456, T0123456C, A1234")              # the shorter ones as before

@t
def a_subjects_code_as_a_title():
    N = names.Names(coded("DR"), people(TAN, "Dr Lee Ming", KOH, LIM), kids(*KIDS)); c, lee = N.code(TAN), N.code("Dr Lee Ming")
    all_where(N, "S3 DR LEE, 3A DR Tan 3 May", f"S3 {lee}, 3A {c} 3 May")                                            # before a word only a teacher has
    all_where(N, "3A DR 3 May, DR May 3, DR Art Room, DR\t8.00", "3A DR 3 May, DR May 3, DR Art Room, DR\t8.00"); all_where(N, "Dr May and Dr Lee", f"{N.code(LIM)} and {lee}")
    for w in ("list", "app"): same(N.out("DR\tLee, DR\nTan", w), "DR\tLee, DR\nTan")
    M = names.Names(coded("Ms"), people(TAN, LIM), []); all_where(M, "Ms Tan, MS LIM, ms ling", f"{M.code(TAN)}, {M.code(LIM)}, {M.code(TAN)}")
    for w in ("list", "app"): same(M.out("Ms May, MS MAY", w), f"Ms May, {M.code(LIM)}")

@t
def a_student_is_never_named():
    N = a_names()
    for w in WHERES:
        got = N.out("A make-up for Alicia Ng, S101 and Ng Alicia", w)
        same(got, "A make-up for a student, a student and a student")
        same(N.out("Alicia Ng (S101) and Ng Alicia", w), "a student (a student) and a student")
        same(N.out("s101, ALICIA NG, wei jie", w), "a student, a student, a student")
        same(N.out("Miss Alicia Ng", w), "Miss a student")                         # a title is a teacher's
        same(N.out("S1012, XS101", w), "S1012, XS101")
        same(N.out("Alicia is away", w), "Alicia is away")                         # a first name alone is sent as typed

@t
def a_student_id_that_could_be_a_date_is_not_one():
    N = a_names(students=[("3", "Bee Teo"), ("2027", "Kai Sim"), ("10-05", "Jo Png"), ("3A", "Zed Yap"), ("25001", "Ria Das"), ("1023", "Uma Roy")])
    text = "3 May 2027, 2027-10-05, 3A"
    all_where(N, text, text)
    all_where(N, "25001 and student 1023", "a student and student a student")
    all_where(N, "student, 1023; students 1023. 1023; Student No.: 1023; ID No: 1023; students 1023 and 1023; students 1023 and 12; students 12, 1023 & 3; Students: 1023/12; for 12 students and 3", "student, 1023; students a student. 1023; Student No.: a student; ID No: a student; students a student and a student; students a student and 12; students 12, a student & 3; Students: a student/12; for 12 students and 3")
    all_where(N, "student #1023, student no. 1023, Student No 1023, ID: 1023, pupil number 1023", "student #a student, student no. a student, Student No a student, ID: a student, pupil number a student")
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
    all_where(a_names("Ms Tan Wei", students=[("S1", "Tan Wei Ling Ho")]), "Tan Wei Ling", "T01 Ling")                  # a whole name first
    all_where(a_names(TAN, students=[("S1", "Wei Ling")]), "Wei Ling", "T01")       # part of a teacher's name, and a student's whole one

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
    for text in ("Ms. Tan", "Ms.Tan", "ms tan", "MS TAN", "Ms  Tan", "Ms\u00a0Tan", "Miss Tan", "miss tan", "Mdm. Tan Wei Ling", "(Ms) Tan", "Dr Ling"):
        all_where(N, f"see {text} now", f"see {c} now")
    all_where(N, "Madam Tan Wei Ling", c); all_where(N, "madam tan and MADAM. Ling", f"{c} and {c}")
    all_where(a_names(TAN, "Mdm Tan Ai"), "Madam Tan and Mdm Tan", "T01 and T01")
    all_where(a_names(TAN, "Mr Tan Boon Kiat"), "Mister Tan, mister tan and Mister. Boon", "T01, T01 and T01"); all_where(N, "Mister Koh", N.code("Mr Koh Ah Huat"))
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
    all_where(N, "the teacher Ms Tan and the teacher (Grace Lee)", f"the teacher {c} and the teacher ({N.code('Grace Lee')})")
    all_where(a_names(), "Mr ART", "T03")
    all_where(a_names(), "the teacher Alicia Ng. They miss Alicia Ng.", "the teacher a student. They miss a student.")
    all_where(a_names(students=[("S1", "Siti Aminah @ Rose")]), "the teacher Siti Aminah @ Rose, Siti Aminah", "the teacher a student, a student")
    same(a_names(students=[("S1", "Siti Aminah @ Rose")]).out("Siti Aminah: Rose", "list"), "a student: Rose")
    all_where(a_names("Teacher A"), "Teacher A, Ms a student, Miss a lesson", "T01, Ms a student, Miss a lesson")
    assert set(HONORIFICS) < set(names.TITLES) and {"madam", "mister", "cikgu", "encik", "puan", "ustaz", "ustazah", "sir", "teacher", "prof", "professor"} < set(names.TITLES)
    for h in HONORIFICS: all_where(N, f"{h} ling, {h.upper()}. LING", f"{c}, {c}")

@t
def names_in_every_kind_of_text():
    N = a_names(TAN, RIZAL, "Ms Nur'Aisyah Salleh", "Mr Kumar s/o Raman", "Ms Siti binte Ahmad", "Ms Jean-Marie Png", "Tan Ah Kow (Mrs Teo)", "Mr Teo Wee"); c = N.code(TAN)
    for before, after in (("", ""), ("(", ")"), ("[", "]"), ('"', '"'), ("- ", "\n"), ("\t", "\t"), ("x:", ";"), ("1. ", "."), ("3A/", "/3B"), ("**", "**"), ("", "'s"), ("", "\u2019s"), ("<b>", "</b>"), ("a, ", ", b"), ("\u201c", "\u201d"), ("Mon ", " 3")):
        all_where(N, f"{before}Tan Wei Ling{after}", f"{before}{c}{after}")
        all_where(N, f"{before}Ms Tan{after}", f"{before}{c}{after}")
    all_where(N, "Tan Wei\nLing, Tan  Wei   Ling, Tan\tWei Ling, Tan Wei-Ling, Wei-Ling, Tan Wei-\nLing", f"{c}, {c}, {c}, {c}, {c}, {c}")
    all_where(N, 'Ms "Tan" and Ms *Ling* (Ms (Tan))', f'{c} and {c} ({c})')
    same(N.out("Wei - Ling. Wei: Ling - Wei / Ling + Wei & Ling", "list"), "Wei - Ling. Wei: Ling - Wei / Ling + Wei & Ling")       # not side by side
    all_where(N, "tan.wei.ling@example.org, tan_wei_ling@example.org, Tan_Wei_Ling.docx", f"{c}@example.org, {c}@example.org, {c}.docx")
    aisyah, kumar, siti, jean, teo = (N.code(x) for x in ("Ms Nur'Aisyah Salleh", "Mr Kumar s/o Raman", "Ms Siti binte Ahmad", "Ms Jean-Marie Png", "Tan Ah Kow (Mrs Teo)"))
    all_where(N, "Nur'Aisyah, Nur\u2019Aisyah, Nur Aisyah Salleh, Ms Aisyah", f"{aisyah}, {aisyah}, {aisyah}, {aisyah}")
    all_where(N, "Kumar s/o Raman, Mr Kumar S/O Raman, Mr Raman, Raman Kumar, s/o Raman, Kumar S/O", ", ".join([kumar] * 6))
    all_where(N, "Jean-Marie, Ms Jean Marie, Marie Png", f"{jean}, {jean}, {jean}")
    all_where(N, "Siti binte Ahmad, Ms Siti, Ms Ahmad, Ahmad Siti", f"{siti}, {siti}, {siti}, {siti}")
    same(N.out("Dear Mrs, or Mr", "typed"), "Dear Mrs, or Mr")
    all_where(N, "Tan Ah Kow (Mrs Teo), Mrs Teo, Tan Ah Kow", f"{teo}, {teo}, {teo}")
    same(N.out("Ask Ahmad, Siti and Rizal", "typed"), f"Ask {N.code(RIZAL)} or {siti}, {siti} and {N.code(RIZAL)}")
    N = a_names("Ms Relief @ One", "Mr Relief @ One", "Art / Music", "Mr Aziz Jun", "Ms Aziz Hana Bao", subjects=("Music",))
    all_where(N, "MR RELIEF @ ONE, Art / Music", f"{N.code('Mr Relief @ One')}, Art / Music")
    for w in ("list", "app"): same(N.out("Jun Aziz Hana", w), f"{N.code('Mr Aziz Jun')} Hana")            # a whole name before a longer part of one
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
def a_comma_joins_the_words_of_one_name():
    N = a_names(TAN, "Ms Grace Lim", "Lee, Hui Min", "Mr Koh Ah Huat", students=[("S1", "Alicia Ng"), ("S2", "Ng Wei Jie"), ("S3", "Lim Tan"), ("S4", "Tan Alicia")]); c, g = N.code(TAN), N.code("Ms Grace Lim")
    all_where(N, "Ng, Alicia; Alicia, Ng; ng ,alicia; Ng, Wei Jie; Wei Jie, Ng; JIE, wei", "; ".join(["a student"] * 6))
    all_where(N, "Alicia;Ng", "a student"); all_where(N, "| Alicia | Ng |", "| a student |"); all_where(N, "|Alicia|Ng|\n|Ng|Alicia|", "|a student|\n|a student|")      # a semicolon, and the cells of a row
    for w in ("list", "app"): same(N.out("| Ms | Tan |, 3 May | Wei, Ms|Tan", w), "| Ms | Tan |, 3 May | Wei, Ms|Tan")
    all_where(N, "Ng\u3001Alicia; Ng\uff0c Alicia; Ng,\nAlicia; Ng ,\tAlicia", "; ".join(["a student"] * 4))
    all_where(N, "Lim, Grace; Grace, Lim; Tan, Wei Ling; Wei Ling, Tan; Lee, Hui Min", f"{g}; {g}; {c}; {c}; {N.code('Lee, Hui Min')}")
    all_where(N, "Ms Wei Ling, Tan Wei Ling", f"{c}, {c}")                          # a name on each side
    for w in ("list", "app"): same(N.out("Wei, Ling, Tan", w), f"{c}, Tan")         # one comma in a match
    same(N.out("Ask Tan, Koh and Grace", "typed"), f"Ask {c}, {N.code('Mr Koh Ah Huat')} and {g}")
    same(N.out("Ask Koh, Lim, Tan", "typed"), f"Ask {N.code('Mr Koh Ah Huat')}, {g}, {c}")        # each a teacher of their own, though Lim Tan is a student
    all_where(N, "Tan, Alicia", "a student")
    for w in ("list", "app"): same(N.out("Ms Tan, Ling and Koh", w), f"{c} and Koh")                                  # one word is no match of its own in a list
    N = a_names("Ms Chng Jun Priya Ravi", "Ms Neo Noor", "Mr Neo Noor Qing Ai", "Ms Toh Dewi Jun Suri"); p = N.code("Ms Chng Jun Priya Ravi")
    for w in ("list", "app"): same(N.out("Chng Jun, Priya Ravi; Jun, Chng Priya Ravi; Dewi\tJun,Toh suri", w), f"{p}; {p}; {N.code('Ms Toh Dewi Jun Suri')}")      # not a match on each side
    same(N.out("1DEWI\tJun,Toh suri", "typed"), f"1 {N.code('Ms Toh Dewi Jun Suri')}")
    M = a_names("Ms Ravi Lee", students=[("S1", "Toh Dewi Jun Suri Ravi")])
    for text in ("Dewi Toh\tJun suri, Ravi", "Toh Dewi, Ravi\tJun suri"): assert not {"dewi", "toh", "suri", "ravi"} & set(re.findall("[a-z]+", M.out(text, "typed").lower()))        # nothing is left on either side
    assert "qing" not in N.out("Noor, Neo qing", "typed"), N.out("Noor, Neo qing", "typed")                          # the match after the comma goes further
    all_where(N, "English, Mon 3 May, 08:00, Sec 3, 3A", "English, Mon 3 May, 08:00, Sec 3, 3A")

@t
def a_digit_or_a_mark_glued_to_a_name():
    N = a_names(TAN, "Mr T Kumar", ("Ms Wa Pek", "WA"), "Ms Tan2", rooms=("Art Room", "T02", "5Z Lab")); c = N.code(TAN)
    all_where(N, "Alicia Ng\u00b9, 1Alicia Ng, S101Alicia Ng, S101\u00b9, Alicia\u00b9 Ng\u00b2, Alicia Ng7, Alicia1 Ng",
              "a student \u00b9, 1 a student, a student a student, a student \u00b9, a student \u00b2, a student 7, a student")
    all_where(N, "Alicia 2Ng, 1Alicia 2Ng3, Alicia1234 Ng", "a student, 1 a student 3, a student")
    all_where(a_names(LIM, students=[("S1", "Goh Jun Wei")]), "Goh 3Jun 8.00, Wei3 May", "Goh 3Jun 8.00, Wei3 May")             # but a date is a date
    all_where(N, "Ms Wei Ling\u00b2, Tan Wei Ling\u00b9, Tan Wei Ling3, \u00b9Tan Wei Ling, MS LING4, Tan Wei Ling\u2020", f"{c} \u00b2, {c} \u00b9, {c} 3, \u00b9 {c}, {c} 4, {c}\u2020")
    all_where(N, "Ms Tan2 and Alicia Ng\u00aa, \u2460Alicia Ng", f"{N.code('Ms Tan2')} and a student \u00aa, \u2460 a student")
    all_where(N, "3A, T02, LT1, 5Z, P3, WA2, WA1 3A, T01 and T09", "3A, T02, LT1, 5Z, P3, WA2, WA1 3A, T01 and T09")       # classes, rooms and papers are whole
    M = a_names(TAN, students=[("3A-07", "Bo Yeo"), ("25001", "Cy Wee Li"), ("S101", "Alicia Ng")])
    all_where(M, "Tan Wei Ling3A-07, Bo Yeo25001, 3A-07Bo Yeo, Alicia NgS101, S101S101, A25001, X3A-07, XS101", "T01 a student, a student a student, a student a student, a student a student, a student a student, A25001, X3A-07, XS101")
    same(N.out("Tan Wei3 and Pek3. WA3", "typed"), f"{c} 3 and {N.code('Ms Wa Pek')} 3. WA3")           # a name with a digit; capitals with a digit are a paper
    for w in ("list", "app"): same(N.out("Alicia Ng\u24d0, Mr T09, T09 Kumar, Alicia: 2Ng: 1Alicia: Ng", w), "a student\u24d0, Mr T09, T09 Kumar, Alicia: 2Ng: 1Alicia: Ng")
    M = a_names("Mr Art Koh 1", "Ms June Lee", students=[("S101A", "Bo Yeo"), ("G3", "Di Teo"), ("S1", "Eng Gita Jun Koh")], subjects=("Music G3",))
    for w in ("list", "app"): same(M.out("Sec 3 Art Koh, Mr Art Koh 1, S101A, S101A5, G3, gita \t Koh \t Jun\x01eng3", w), f"Sec 3 Art Koh, {M.code('Mr Art Koh 1')}, a student, S101A5, G3, a student 3")
    same(N.out("Wa, WA and Ms Wa", "typed"), ", ".join([N.code("Ms Wa Pek")]) + f", {N.code('Ms Wa Pek')} and {N.code('Ms Wa Pek')}")
    all_where(N, "Mr T, Mr T02", f"{N.code('Mr T Kumar')}, Mr T02")
    for w in WHERES: same(N.back(N.out("Ms Wei Ling2 and 1Tan Wei Ling", w)), f"{TAN} 2 and 1 {TAN}")                      # a code is never run into a digit

@t
def hidden_characters_dashes_and_wide_forms():
    N = a_names(TAN, students=[("S101", "Alicia Ng"), ("3A-07", "Bo Yeo Li"), ("S-1\u20132", "Cy Wee"), ("AB-9", "Di Teo")]); c = N.code(TAN)
    for i in ("3A-07", "3A\u201107", "3A\u201307", "3A\u201407", "3A\u221207", "3A\uff0d07", "3A\u200b-07", "3A-\u00ad07", "\uff13\uff21-07", "3a-0\u20607", "\uff33101", "S1\u200b01", "s\u00ad101", "S\x00101", "S-1-2", "s\u20101\u20132", "A\u200bB-9", "ab\u00ad-\u200b9"):
        all_where(N, f"for {i}, then", "for a student, then")
    for n in ("Alicia\u200bNg", "Ali\u200bcia Ng", "Ali\u200bcia\u200bNg", "Alicia\u200e Ng", "\u202aAlicia\u202c Ng", "Alicia \u2066Ng\u2069", "Alicia\x01Ng", "A\x01licia Ng", "Ng\u2060Alicia", "Alicia\u3164Ng", "Alicia\ufe0f Ng",
              "Alicia\u034f Ng", "Alicia\ufeffNg", "\uff21\uff4c\uff49\uff43\uff49\uff41 \uff2e\uff47", "Alicia\u2011Ng", "Alicia\u2013Ng", "A\u0301licia N\u0327g", "Ng\uff0cAlicia", "N\u200bg, Alicia"):
        for w in WHERES:
            got = N.out(f"see {n} now", w); assert "a student" in got and not re.search("[A-Za-z]", got.replace("see", "").replace("a student", "").replace("now", "")), (n, w, got)
    for n in ("Ms\u200bTan", "Ms\u200b Tan", "T\u200ban W\u200bei Ling", "Tan\u200bWei\u200bLing", "Tan\u200bWei Ling", "\uff2d\uff53 \uff34\uff41\uff4e", "Ta\x7fn Wei Ling", "Tan\u2013Wei\u2013Ling", "Wei\u00adLi\u200bng", "Ms Ta\x02n"):
        all_where(N, f"see {n}, now", f"see {c}, now")
    N = a_names("Ms Sng Ai Li", "Ms Lian Koh", students=[("S1", "Ng S Mei Jun"), ("S2", "Heng Li An"), ("S3", "See Alicia Ong")])       # a word that can be read as two
    all_where(N, "S\x01N\u200eg \t Jun   MEI; Li\u200bAn, Heng; See\u200bAlicia", "a student; a student; a student")
    all_where(N, "Xyz\u200bHeng Li An", "Xyz\u200ba student")
    many = "x\u200b " * 120                                                           # a long text is read both ways in one order only
    for w in ("list", "app"): same(N.out(many + "S\x01N\u200eg \t Jun   MEI; Heng\u200bLi An; Xyz\u200bHeng Li; T\u00ada", w), many + "a student; a student; Xyz\u200ba student; T\u00ada")
    M = a_names("Ng June", "Mr A Rahman", "Mr T Kumar", students=[("S1", "Sng June"), ("S2", "May The Yap")])
    all_where(M, "S\u200bNg June", "a student"); same(M._left("T01, a student at the school, may\u200b P3, 3A")[0], 0); same(M._left("Kumar\u200bJune and Ng")[0], 4)
    M = a_names(TAN, "Mr T Kumar", "Ms Li An", "Ms Sng Ai", students=[("S1", "Ng S Mei")])
    same(M.out("T\u200ban; see S\x01Ng Mei", "typed"), f"{M.code(TAN)}; see a student")
    for w in ("list", "app"):
        same(a_names("Mdm Sng Art", students=[("S1", "Ng S")]).out("S\x01NG ART - 3A", w), "T01 - 3A")
        same(a_names("Mr A Heng", students=[("S1", "May Eng Cai Ah")]).out("a\u00adh\u200beng | Cai", w), "a student")
        same(a_names("Mdm Sng May S Ng").out("Sng\r\nS\u200bNG\x01May", w), "T01")
    all_where(a_names("Ms Sng Xin Ai", students=[("S1", "Ng S Art Xin")]), "S\x01Ng-Xin Art", "a student")
    all_where(a_names(TAN, "Mr T Kumar", "Ms Li An"), "T\u200ban Wei Ling, Wei T\u200ban", "T03, T03")
    for w in ("list", "app"): same(a_names("Ng Li Ah S", students=[("S1", "Sng Li")]).out("Li (S\x01Ng\" Ah, L\u200bi Sng", w), "T01, a student")
    for text in ("Caf\u00e9 \u2013 3 May \u00bd \uff21\uff22", "a\u200bb \u2014 \u2460 x\u00b2", "\u200b\u200e\u00ad", "\u0301\u0302", "Sec\u200b 3 \u2013 English"): all_where(N, text, text)       # and nothing else is changed

@t
def a_unit_after_a_number_is_not_a_name():
    N = a_names("Mr Jun Min", "Ms Min An", "Mr Hr Goh", "Ms Sec Mins")
    for text in ("90 min Jun 3", "90 Min Jun 3", "1 h 30 min an extra", "2 hrs, 45mins, 30 sec, 1h30min, 1 hr", "30-min paper, 90 MIN"): all_where(N, text, text)
    for w in ("list", "app"): same(N.out("Jun 5min, Jun 5 min, Jun An 90min paper", w), "Jun 5min, Jun 5 min, Jun An 90min paper")
    all_where(N, "Mr Min An, Min Jun and Ms An", f"{N.code('Ms Min An')}, {N.code('Mr Jun Min')} and {N.code('Ms Min An')}")
    M = a_names(("Mr Ming Yap", "MIN"), "Min @ Li", "Min Jo @ Li")
    same(M.out("90 MIN, MIN is free", "app"), f"90 MIN, {M.code('Mr Ming Yap')} is free")
    for w in ("list", "app"): same(M.out("90 Min @ Li: Min @ Li", w), f"90 Min @ Li: {M.code('Min @ Li')}")

@t
def what_is_not_a_title():
    N = names.Names(coded("DR", subjects=("Art",)), people(TAN, "Dr Lee Ming", KOH, LIM), kids(*KIDS)); c, lee = N.code(TAN), N.code("Dr Lee Ming")
    all_where(N, "Dr Lee, Dr. Ming and DR LEE MING", f"{lee}, {lee} and {lee}")
    all_where(N, "3A WILL MISS ART", "3A WILL MISS ART")
    all_where(N, "MISS TAN, Miss May and MR ART KOH", f"{c}, {N.code(LIM)} and {N.code(KOH)}")
    for text in ("Ms\tTan", "Ms   Tan", "Ms\nTan", "Ms\r\nTan"):                             # another cell or line
        same(N.out(text, "list"), text); same(N.out(text, "typed"), text.replace("Tan", c))
    all_where(N, "Ms Tan\n3A; Ms Wei\t3 May", f"{c}\n3A; {c}\t3 May")
    same(N.out("Ms Tan\nWei went", "list"), f"{c}\nWei went")
    all_where(N, "Ms\tTan Wei Ling, Ms Tan\tWei Ling", f"Ms\t{c}, {c}")                      # but a whole name is a name

@t
def marks_round_the_words_of_a_name():
    N = a_names(); c = N.code(TAN)
    all_where(N, "(Alicia) Ng, **Alicia** Ng, Alicia (Ng), \"Alicia\" Ng, [Alicia] [Ng], Alicia 'Ng', *Alicia Ng*, \u201cAlicia\u201d Ng", ", ".join(["a student"] * 4 + ["[a student]", "a student", "*a student*", "a student"]))
    all_where(N, "(Tan) Wei Ling, Ms (Wei) Ling, Wei (Ling)", f"{c}, {c}, {c}")
    all_where(N, "Room (Art), English (3A), (May) 3", "Room (Art), English (3A), (May) 3")

@t
def small_words_and_times_are_not_people():
    N = a_names("Ms Do Thi An", ("Mr Ang Min", "AM"), "Mr Will Tay", ("Ms On Go", "On"), ("Mr S Kumar", "S"), "Mr A Rahman", students=[("S1", "Go Kah On")])
    text = "3A will do an extra paper and go on to 3B by 8 am"
    all_where(N, text, text)
    all_where(N, "from 8.00 AM to 9 AM", "from 8.00 AM to 9 AM")
    same(N.out("AM is free", "app"), f"{N.code('Mr Ang Min')} is free")
    same(N.out("Mr Tay will be away and mr tay will go", "typed"), f"{N.code('Mr Will Tay')} will be away and {N.code('Mr Will Tay')} will go")
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
    pub = a_pub(rooms=("Caf\u00e9",), subjects=("Mathematics",)); pub["model"]["classes"].append(dict(name="9Q", level="Sec 9", size=1, home="Nook", parents=[]))
    assert {"caf\u00e9", "cafe", "math", "9q", "nook"} < names.protected(pub)
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
    text = f"T99, T7, t01, X{c}, {c}A, {c}0, L{c}, 1{c}"
    same(N.back(text), text)
    same(N.back(f"_{c}_, {c}_1, *{c}*"), f"_{TAN}_, {TAN}_1, *{TAN}*")
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
    odd = ("\uff9e", "\uff9f\uff9e", "\u200b", "\u0301", "\x00", "\ud800", "\u3164", "\u00b2", "^", "_")
    M = names.Names(a_pub(school="\uff9e\uff9e\uff9e\uff9e"), people(*odd, *[f"Ms {x}" for x in odd], *[(f"Mr X{i} Q", x) for i, x in enumerate(odd)]) + [None, 3, "x"], kids(*[(x, x) for x in odd], *[(f"9{x}", f"Z {x}") for x in odd]) + [None, 7])
    for x in odd + tuple(f"Ms {x} a{x}b {x}9" for x in odd): all_where(M, x, x)
    M = names.Names(a_pub(), iter(people(TAN)), (x for x in kids(*KIDS))); all_where(M, "Ms Tan, Alicia Ng", "T01, a student")      # any kind of list
    names.Names([], [], []); names.Names("x", (), ()); names.Names(dict(model=[], meta=[]), [], [])
    for bad in (None, 3, 2.5, ["Ms Tan"], {"a": 1}, b"Ms Tan"):
        for w in WHERES: assert N.out(bad, w) is bad
        assert N.back(bad) is bad
    for text in ("", " ", "\n", "...", "\ud800", "Ms", "Ms.", "Teacher", "\u0301"): all_where(N, text, text)
    same(N.out("Ask Tan", "somewhere else"), f"Ask {N.code(TAN)}"); same(N.out("Ask Tan", None), f"Ask {N.code(TAN)}")      # an unknown place hides the most

_FIRST = "Bao Cai Dewi Eng Farid Gita Hana Indra Jun Kiran Lian May Mei Min Noor Omar Priya Qing Ravi Suri Tuan Umi Vani Wen Xin Yati Zul".split()
_LAST = "Aziz Beh Chng Das Foo Gan Heng Ismail Jalil Kwek Loh Maniam Neo Osman Poh Quah Rao Sng Sun Toh Vasu Wee Yeo Zain".split()

def a_big_school():
    """120 staff and 1,000 students with months, a weekday and a unit's word in their names, first and last, and IDs of every kind"""
    rnd = random.Random(7)
    def one(k): return " ".join([rnd.choice(_LAST)] + rnd.sample(_FIRST, k))
    staff = sorted({f"{rnd.choice(['Mr', 'Ms', 'Mdm', 'Mrs', 'Miss', 'Dr', 'Mr'])} {one(rnd.choice((1, 2, 2, 3)))}" for _ in range(160)})[:120]
    pupils = sorted({one(rnd.choice((1, 2, 3, 3, 4))) for _ in range(1400)} - {n.split(" ", 1)[1] for n in staff})[:1000]
    assert len(staff) == 120 and len(pupils) == 1000
    return staff, [((f"S{i:04d}", f"T{i:07d}A", f"{1 + i % 4}{'ABCD'[i % 4]}-{i:03d}")[i % 3], n) for i, n in enumerate(pupils)]

def dressed(rnd, ws, joins):
    """the words ws as somebody might write them: each in a case of its own, joined by joins (a comma at most once), hidden
    characters between or inside them, a mark or a digit glued on"""
    ws = [rnd.choice((str, str, str.lower, str.upper, str.title))(x) for x in ws]
    if rnd.random() < .2: k = rnd.randrange(len(ws)); ws[k] = ws[k][:1] + rnd.choice("\u200b\u00ad\u200e\x01\u2060") + ws[k][1:]
    if rnd.random() < .1: ws = ["".join(chr(ord(c) + 0xfee0) if "!" <= c <= "~" else c for c in x) for x in ws]
    if rnd.random() < .1: ws[-1] += rnd.choice("\u00b9\u00b2\u20203")
    out, comma = ws[0], False
    for x in ws[1:]:
        j = rnd.choice(joins)
        if set(",;") & set(j) and comma: j = " "
        comma = comma or bool(set(",;") & set(j))
        out += j + x
    return out

@t
def nobody_known_leaks_in_any_form():
    """every teacher and student, orders of the words, with titles, after any number, in every kind of text and dressed up in every
    way above. A whole name leaves no word of it in a list and in the app's words, and only a month in typed ones; part of a name of
    two or more words that are not months, and a titled one, leave none but a month. What R4 and R1 leave is left out: a unit's word
    straight after a number, and part of a name that has somebody's whole name in it"""
    staff, pupils = a_big_school(); rnd = random.Random(11)
    N = names.Names(a_pub(), people(*staff), kids(*pupils))
    free = names.protected(a_pub()); units = names._UNITS
    frames = ("{}", "see {} on Mon 4", "3A\t{}\t08:00", "({})", "{},", "Room 3-01: {}\n- next", "x {}'s", "1{}", "\u201c{}\u201d", "English {} 3A", "Sec 3 {}", "S3 EL P1 {} 3A", "8.30 {}", "Room 3-01 {}", "Group 2 {}", "90 {}", "12 {}", "1) {}", "4\t{}", "| {} |")
    part, whole = (" ", " ", "  ", "-", ", ", " ,", "\u2011", "\u00a0", ") (", "\u200b", "** "), (" ", "   ", "\t", ", ", ",", "\n", "\u200b", "\u2013", "\x01", " \u200e", " (", "\" ", "; ", " | ")
    words = lambda s: {x for x in re.findall(r"[^\W\d_]+", names._fold(s)[0].casefold())}
    fold = lambda ws: tuple(sorted(w.casefold() for w in ws))
    every = {fold(n.split()[1:]) for n in staff} | {fold(n.split()) for _, n in pupils}
    holds = lambda p: any(fold(p[i:j]) in every for i in range(len(p)) for j in range(i + 2, len(p) + 1))          # somebody's whole name is in it
    some = lambda ws, k, m: rnd.sample(list(itertools.permutations(ws, k)), min(m, len(list(itertools.permutations(ws, k)))))
    n = 0
    def check(f, p, whole_name, titled, w):
        nonlocal n; n += 1
        frame = rnd.choice(frames)
        got = N.out(frame.format(f), w); left = words(" ".join(p)) & words(got); real = words(" ".join(p)) - free
        if p[0].casefold() in units and re.search(r"\d ?\{", frame) and not titled:
            if whole_name and len(p) > 2 and " ".join(p) in f: assert not left - free - units, (f, frame, w, got)
            return
        if whole_name and len(p) > 1 and real:
            assert not (left - free if w == "typed" or titled else left), (f, frame, w, got)
        elif titled or len(real) > 1 and not holds(p): assert not left - free, (f, frame, w, got)
    for name in staff:
        ws = name.split()[1:]
        for k in range(1, len(ws) + 1):
            for p in some(ws, k, 5):
                heads = [f"{h} {dressed(rnd, p, (' ', ' ', '-', '  '))}" for h in rnd.sample(("Ms", "mr.", "MDM", "Madam", "Cikgu", "(Dr)"), 2)] + [f"{rnd.choice(('MDM', 'MR', 'MS', 'DR'))} {' '.join(p).upper()}"]
                if holds(p) and k < len(ws): heads = []
                for f in heads: check(f, p, k == len(ws), True, rnd.choice(WHERES))
                for f in [dressed(rnd, p, part) for _ in range(2)] if k > 1 else []: check(f, p, False, False, rnd.choice(WHERES)) if k < len(ws) else None
                for f in [dressed(rnd, p, whole) for _ in range(4)] if k == len(ws) else []:
                    for w in WHERES: check(f, p, True, False, w)
        for w in WHERES: same(N.out(name, w), N.code(name)); same(N.back(N.out(name, w)), name); same(N.out(N.out(name, w), w), N.code(name))
    for i, name in pupils:
        ws = name.split()
        for k in range(2, len(ws) + 1):
            for p in some(ws, k, 2): check(dressed(rnd, p, whole if k == len(ws) else part), p, k == len(ws), False, rnd.choice(WHERES))
        if rnd.random() < .2:
            all_where(N, f"({i}) {i.lower()}\u00b9 {i[0]}\u200b{i[1:]}", "(a student) a student \u00b9 a student")
            if len(i) > 5: all_where(N, f"{i}Zzz {i}{i} x{i}", "a student Zzz a student a student x a student")
    assert n > 9000, n

@t
def two_whole_names_side_by_side():
    """any two people, with anything that joins words between them, after any number: no word of either is left"""
    staff, pupils = a_big_school(); rnd = random.Random(12)
    N = names.Names(a_pub(), people(*staff), kids(*pupils))
    free = names.protected(a_pub())
    everyone = [n.split()[1:] for n in staff] + [n.split() for _, n in pupils]
    odd = [v for v in everyone if {z.casefold() for z in v} & free]                  # with a month or a weekday in it
    for _ in range(1500):
        x, y = rnd.sample(odd, 2) if rnd.random() < .7 else rnd.sample(everyone, 2)
        if rnd.random() < .5: x, y = (sorted(v, key=lambda z: (z.casefold() not in free, rnd.random())) for v in (x, y))        # the month or weekday first
        sep, w = rnd.choice((" ", ", ", "\t", "\n", "; ", " | ", "   ", " and ", "\n1 ", "\n2) ", " - ")), rnd.choice(WHERES)
        f = rnd.choice(("{}", "1 {}", "P1 {}", "8.30 {}", "{} 3A", "({})")).format(rnd.choice((str, str.upper, str.lower))(" ".join(x) + sep + " ".join(y)))
        if "min" in (x[0].casefold(), y[0].casefold()): continue                    # a unit's word straight after a number
        got = N.out(f, w); left = {v.casefold() for v in x + y} & {v.casefold() for v in re.findall(r"[A-Za-z]+", got.replace("a student", ""))}
        assert not (left - free if w == "typed" else left), (f, w, got)

@t
def a_titled_teacher_is_never_a_student():
    staff, pupils = a_big_school(); rnd = random.Random(13)
    N = names.Names(a_pub(), people(*staff), kids(*pupils))
    for name in staff:
        h, last = name.split()[:2]
        for _, kid in [p for p in pupils if last in p[1].split()][:4]:
            other = rnd.choice([w for w in kid.split() if w != last])
            if any({last, other} <= set(n.split()) for n in staff): continue
            for text in (f"Tell {h} {last}, {other} is away", f"{h} {last} ({other})", f"{h.upper()} {last.upper()} {other.upper()}", f"S3 EL P1,{h} {last},{other} 3,8.00"):
                for w in WHERES: got = N.out(text, w); assert "a student" not in got and re.search(r"\bT\d\d", got) and other.casefold() in got.casefold() + (other.casefold() if w == "typed" else ""), (text, w, got)

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
    """20,000 characters in under half a second with 120 staff and 1,000 students, however they are put together (the work, not
    the wait: an ordinary one takes about 0.1 s)"""
    staff, pupils = a_big_school(); rnd = random.Random(3)
    N = names.Names(a_pub(school="Gita Hana School"), people(*staff, ("Ms Tan Wei Ling", "T W L")), kids(*pupils, ("A-1-B-2-C-3", "Bao Bao Bao Cai")))
    words = _FIRST + _LAST + ["Mon", "3", "May", "English", "Ms", "Mr", "Room", "to", "an", "S0001", "T01"]
    texts = []
    for sep in (" ", "\n", ", ", "-", "\u200b", "\t", " ("):
        text = ""
        while len(text) < 20000: text += rnd.choice(words) + sep
        texts.append(text)
    one, two = pupils[0][1], staff[0].split(" ", 1)[1]
    texts += [x * (20000 // len(x) + 1) for x in ("dr\n", "dr ", "Ms. ", "Mr Dr ", "teacher ", "(Ms) ", "DR\t", " ", "\t", "\n", "a", "\u0301", "\u200b", "a\u200b", "Bao\u200b", "1a", "S0001", "-", "(", "*", ",", ", ", "Bao ", "Bao, ", "Bao-",
                                                   "Bao Cai ", "Tan, Wei Ling, ", "Wei, Ling, ", one + " ", one + ", ", two + ", ", "Ms " + two + ", ", "the ", "The Gita ", "Gita Hana ", "3 May ", "May ", "student ", "student no. 1", "A-1-", "T W ", "T\u00b9",
                                                   "Bao Bao ", "Jun ", "Jun 3 ", "x" * 5000 + " ", "\uff21", "\u00bd", "\u3164", "\ufdfa", " \u200b", "Bao     ", "Bao" + " " * 4000)]
    six = "May Jun Sat Sun Mon English".split()                                       # a name of six protected words and one more
    M = names.Names(a_pub(), people("Ms " + " ".join(six) + " Koh"), kids(("K1", "Bo " + " ".join(six))))
    for sep in ("\n", " ", ", ", "\t"):
        for ws in (six, six[::-1], six + ["Koh"]):
            for w in WHERES:
                at = time.process_time(); M.out(((sep.join(ws) + sep) * 2000)[:20000], w); took = time.process_time() - at
                assert took < 0.5, f"{took:.2f} s: {ws} {sep!r} {w}"
    texts += ["Bao" + " " * 19000 + "Cai", "Bao" * 6000 + "\u200b", "\u200b".join("BaoCai" * 3000), "Ms" + " " * 19000]
    for text in texts:
        for w in WHERES:
            at = time.process_time(); N.out(text[:20000], w); took = time.process_time() - at
            assert took < 0.5, f"{took:.2f} s: {text[:20]!r}"

print(f"{COUNT} plan tests passed")
