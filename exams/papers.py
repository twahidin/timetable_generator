"""Papers of an exam schedule."""


def label(paper) -> str:
    """a paper's name in messages: level, subject and paper, leaving out the paper part when it is empty"""
    return " ".join(str(paper.get(k) or "").strip() for k in ("level", "subject", "paper") if str(paper.get(k) or "").strip())
