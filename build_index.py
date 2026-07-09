"""
Builds the JSON question index from all paper_*.txt files and groups
sub-questions (e.g. 04.1, 04.2, 04.3) under their parent question number (04),
so that a keyword match on one sub-part returns the whole parent question -
every sub-part plus a note about any diagrams ("Figure N") mentioned in it.

We only have text extracted from AQA's PDFs, not the original page images,
so actual diagrams can't be pulled out - instead each sub-part that mentions
a Figure/Table is flagged, with a link back to the source PDF page where the
real diagram can be seen.
"""

import re
import glob
import os
import json

BASE = os.path.dirname(os.path.abspath(__file__))

FIGURE_RE = re.compile(r"\b(Figure|Table)\s+\d+\b", re.IGNORECASE)


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
            elif line.startswith("SPEC:"):
                meta["spec"] = line.replace("SPEC:", "").strip()
            elif line.startswith("SUBJECT:"):
                meta["subject"] = line.replace("SUBJECT:", "").strip()
            elif line.startswith("SOURCE:"):
                meta["source"] = line.replace("SOURCE:", "").strip()
            elif line.strip() == "---":
                body_started = True
            elif body_started and line.strip():
                m = re.match(r"^(\d\s\d)\s\.\s(\d)\s(.*)", line)
                if m:
                    parent = m.group(1).replace(" ", "")
                    ref = f"{parent}.{m.group(2)}"
                    text = m.group(3)
                    has_figure = bool(FIGURE_RE.search(text))
                    questions.append({
                        "parent": parent,
                        "ref": ref,
                        "text": text,
                        "has_figure": has_figure,
                    })
        papers.append({**meta, "questions": questions})
    return papers


def group_by_parent(paper):
    """Group a paper's flat sub-question list into parent-question groups."""
    groups = {}
    order = []
    for q in paper["questions"]:
        if q["parent"] not in groups:
            groups[q["parent"]] = []
            order.append(q["parent"])
        groups[q["parent"]].append(q)
    return [{"parent": p, "parts": groups[p]} for p in order]


def build_index():
    papers = load_papers()
    by_subject = {}
    for paper in papers:
        subject = paper.get("subject", "unknown")
        by_subject.setdefault(subject, []).append({
            "title": paper["title"],
            "spec": paper.get("spec", ""),
            "source": paper.get("source", ""),
            "groups": group_by_parent(paper),
        })
    return by_subject


if __name__ == "__main__":
    index = build_index()
    total_papers = sum(len(v) for v in index.values())
    total_q = sum(
        len(pt["parts"])
        for papers in index.values()
        for p in papers
        for pt in p["groups"]
    )
    print(f"Subjects: {list(index.keys())}")
    for subj, papers in index.items():
        n_q = sum(len(pt['parts']) for p in papers for pt in p['groups'])
        print(f"  {subj}: {len(papers)} papers, {n_q} sub-questions")
    print(f"TOTAL: {total_papers} papers, {total_q} sub-questions")

    with open(os.path.join(BASE, "question_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    print("Wrote question_index.json")
