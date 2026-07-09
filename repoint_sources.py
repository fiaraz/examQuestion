"""
Replace each paper's 'source' (previously a guessed/sometimes-missing AQA URL)
with the relative path to the actual local PDF file, now that examPapers/ is
being committed into the repo alongside the HTML tool.
"""
import json
import os
from build_full_index import scan_subject, SUBJECTS, SUBJECT_KEY, ROOT
DOWNLOADS = os.path.dirname(ROOT)

BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, "full_question_index.json"), encoding="utf-8") as f:
    index = json.load(f)

lookup = {}
for subject in SUBJECTS:
    qps, mss = scan_subject(subject)
    subj_key = SUBJECT_KEY[subject]
    lookup[subj_key] = {"qp": qps, "ms": mss}

updated = 0
missing = 0
for subj_key, papers in index.items():
    for paper in papers:
        key = (paper["code"], paper["session"])
        qp_path = lookup[subj_key]["qp"].get(key)
        ms_path = lookup[subj_key]["ms"].get(key)
        if qp_path:
            paper["source"] = os.path.relpath(qp_path, DOWNLOADS)
            updated += 1
        else:
            missing += 1
        if ms_path:
            paper["ms_source"] = os.path.relpath(ms_path, DOWNLOADS)

with open(os.path.join(BASE, "full_question_index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False)

print(f"updated: {updated}, missing (no local file found): {missing}")
