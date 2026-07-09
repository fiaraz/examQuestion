import json
import glob
import os

BASE = os.path.dirname(os.path.abspath(__file__))
merged = {}

for path in sorted(glob.glob(os.path.join(BASE, "full_question_index_*.json"))):
    with open(path, encoding="utf-8") as f:
        chunk = json.load(f)
    for subject, papers in chunk.items():
        merged.setdefault(subject, []).extend(papers)

with open(os.path.join(BASE, "full_question_index.json"), "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False)

total_papers = sum(len(v) for v in merged.values())
total_parts = sum(len(g["parts"]) for papers in merged.values() for p in papers for g in p["groups"])
total_linked = sum(1 for papers in merged.values() for p in papers for g in p["groups"] for part in g["parts"] if part["ms_answer"])

for subj, papers in merged.items():
    n_parts = sum(len(g['parts']) for p in papers for g in p['groups'])
    n_linked = sum(1 for p in papers for g in p['groups'] for part in g['parts'] if part['ms_answer'])
    print(f"{subj}: {len(papers)} papers, {n_parts} sub-questions, {n_linked} linked to a mark scheme")

print(f"\nTOTAL: {total_papers} papers, {total_parts} sub-questions, {total_linked} linked")
