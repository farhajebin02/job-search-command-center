import re
from difflib import SequenceMatcher

from core.scoring import get_matches
from core.tracker import STAGES

#: Words people say when naming a job that carry no matching value. Without
#: dropping these, "the data analyst job" fails because no title contains
#: "the" or "job".
FILLER = {
    "a", "an", "the", "at", "in", "of", "for", "to", "my", "with", "and",
    "job", "jobs", "role", "roles", "position", "posting", "one",
}

#: How alike two words must be to count as the same one. This exists because
#: speech-to-text does not spell company names the way the database does:
#: "Sanas" comes back as "Senas", "Recode" as "Re-code". 0.78 pairs those while
#: leaving genuinely different companies apart.
FUZZY = 0.78

#: Short words are close to everything, so fuzzy matching them turns the whole
#: feed into a match. "ml" and "ai" have to land literally or not at all.
MIN_FUZZY_LEN = 4

#: When nothing matches every term, how much of what was said a job still has
#: to account for before it is worth offering back. One word landing out of
#: four is noise; three out of four is a misheard company name.
NEAR_COVERAGE = 0.6

#: Near matches are guesses to be confirmed, not answers. A handful is enough
#: to ask "did you mean"; a page of them is worse than saying nothing.
MAX_NEAR = 5


def _terms(q: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9+#.]+", q) if t and t not in FILLER]


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9+#.]+", text) if w]


def _term_score(term: str, blob: str, words: list[str]) -> float:
    """How well one spoken term accounts for one job: 1.0 for a literal hit, a
    similarity ratio for a near miss close enough to be the same word, 0 for
    neither."""
    if term in blob:
        return 1.0
    if len(term) < MIN_FUZZY_LEN:
        return 0.0
    best = max((SequenceMatcher(None, term, w).ratio() for w in words),
               default=0.0)
    return best if best >= FUZZY else 0.0


def _rank(rows: list[dict], terms: list[str]) -> list[dict]:
    """Rank jobs by how much of the query they account for.

    Scoring in Python rather than SQL: SQLite's LIKE cannot express "close
    enough", and the feed is a few hundred rows, so the whole table is cheaper
    to walk than the mismatch it would otherwise hide.
    """
    scored = []
    for r in rows:
        blob = f"{r['title']} {r['company']}".lower()
        words = _words(blob)
        scores = [_term_score(t, blob, words) for t in terms]
        hits = sum(1 for s in scores if s)
        if hits:
            scored.append((hits, sum(scores), r))

    exact = [s for s in scored if s[0] == len(terms)]
    if exact:
        # An unambiguous hit must not drag in everything that shares a word.
        exact.sort(key=lambda s: -s[1])
        return [{**r, "exact": True} for _, _, r in exact]

    near = [s for s in scored if s[0] / len(terms) >= NEAR_COVERAGE]
    near.sort(key=lambda s: (-s[0], -s[1]))
    return [{**r, "exact": False} for _, _, r in near[:MAX_NEAR]]


def find_jobs(conn, query: str) -> list[dict]:
    """Jobs matching a spoken description, each flagged `exact` or not.

    `exact` is the difference between acting and asking. A caller that changes
    an application's stage must confirm a non-exact hit with the user first —
    the alternative is updating whichever job happened to sound closest.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    stage = next((s for s in STAGES if s.replace("_", " ") == q or s == q), None)
    if stage:
        rows = [dict(r) for r in conn.execute(
            """SELECT j.*, a.stage FROM job j
               JOIN application a ON a.job_id = j.id WHERE a.stage=?""", (stage,))]
        jobs = [{**r, "exact": True} for r in rows]
    else:
        # Match term by term rather than as one literal string. A job is named
        # the way it is spoken — "AI Engineer at Recode Solutions" — where the
        # title holds part of the phrase and the company the rest, so no single
        # column ever contains the whole thing.
        terms = _terms(q)
        if not terms:
            return []
        rows = [dict(r) for r in conn.execute(
            """SELECT j.*, a.stage FROM job j
               LEFT JOIN application a ON a.job_id = j.id""")]
        jobs = _rank(rows, terms)

    matches = get_matches(conn, [j["id"] for j in jobs])
    return [{**j, "match": matches.get(j["id"])} for j in jobs]
