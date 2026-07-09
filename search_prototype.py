"""
GCSE Question Search - prototype
Searches a small local corpus of real AQA GCSE Physics past-paper questions
(text extracted from PDFs published at filestore.aqa.org.uk) for a topic
keyword, e.g. "Fleming's left hand rule".

This demonstrates the core design problem: exam questions almost never use
the exact textbook phrase for a concept. A literal string search for
"fleming's left hand rule" returns nothing, because real questions ask about
"the effect that causes the wire to move" or "the motor effect" instead.
The fix is a small synonym/topic map that expands a search term into the
phrases exam papers actually use.
"""

import re
import glob
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# Curated topic -> related exam phrasing. In a full build this would be a much
# larger, subject-wide table (or replaced with embedding-based semantic search).
SYNONYMS = {
    "fleming's left hand rule": [
        "motor effect",
        "force on a current-carrying conductor",
        "force on a current carrying wire",
        "wire in a magnetic field",
        "magnetic flux density",
        "current balance",
    ],
    "fleming's right hand rule": [
        "generator effect",
        "electromagnetic induction",
        "induced potential difference",
    ],
    "specific heat capacity": ["specific heat capacity"],
    "specific latent heat": ["specific latent heat", "latent heat of vaporisation", "latent heat of fusion"],
    "half-life": ["half-life", "radioactive decay", "activity"],
    "national grid": ["national grid", "transformer", "step-up transformer", "step-down transformer"],
}


def load_papers():
    papers = []
    for path in sorted(glob.glob(os.path.join(BASE, "paper_*.txt"))):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        meta = {"file": os.path.basename(path)}
        questions = []
        body_started = False
        for line in lines:
            if line.startswith("PAPER:"):
                meta["title"] = line.replace("PAPER:", "").strip()
            elif line.startswith("SOURCE:"):
                meta["source"] = line.replace("SOURCE:", "").strip()
            elif line.strip() == "---":
                body_started = True
            elif body_started and line.strip():
                m = re.match(r"^(\d\s\d\s\.\s\d)\s(.*)", line)
                if m:
                    questions.append({"ref": m.group(1).replace(" ", ""), "text": m.group(2)})
        papers.append({**meta, "questions": questions})
    return papers


def search(query, papers):
    query_l = query.strip().lower()
    terms = SYNONYMS.get(query_l, [query_l])

    literal_hits = []
    expanded_hits = []
    for paper in papers:
        for q in paper["questions"]:
            text_l = q["text"].lower()
            if query_l in text_l:
                literal_hits.append((paper, q, query_l))
            else:
                for term in terms:
                    if term in text_l:
                        expanded_hits.append((paper, q, term))
                        break
    return literal_hits, expanded_hits


def show(query, papers):
    literal, expanded = search(query, papers)
    print(f"\n=== Search: \"{query}\" ===")
    print(f"Literal phrase matches: {len(literal)}")
    for paper, q, term in literal:
        print(f"  [{paper['title']}] Q{q['ref']}: {q['text']}")

    print(f"Synonym-expanded matches: {len(expanded)}")
    for paper, q, term in expanded:
        print(f"  [{paper['title']}] Q{q['ref']} (matched via \"{term}\"): {q['text']}")


if __name__ == "__main__":
    papers = load_papers()
    total_q = sum(len(p["questions"]) for p in papers)
    print(f"Loaded {len(papers)} papers, {total_q} questions.")
    show("Fleming's left hand rule", papers)
    show("specific latent heat", papers)
    show("half-life", papers)
