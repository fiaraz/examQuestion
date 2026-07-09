"""
Build the full question index across all subjects in Downloads/examPapers,
linking each question paper to its matching mark scheme (same paper + session)
where one exists. Extracts real text from the actual PDFs (not paraphrased),
groups sub-questions under their parent question number, flags any part that
mentions a Figure/Table, and attaches the real AQA mark-scheme answer to each
part where a matching mark scheme was found.
"""
import os
import re
import json
import time
import pdfplumber

ROOT = "/sessions/upbeat-funny-shannon/mnt/Downloads/examPapers"
SUBJECTS = ["Biology", "Chemistry", "Physics", "Combined Science"]
SUBJECT_KEY = {"Biology": "biology", "Chemistry": "chemistry", "Physics": "physics", "Combined Science": "combined_science"}

SESSION_RE = re.compile(r'-(QP|MS|SQP|SMS)-?(.*)\.(pdf|PDF)$')
CODE_RE_SIMPLE = re.compile(r'AQA-(846[123])(\d)H')
CODE_RE_COMBINED = re.compile(r'AQA-8464\d*([BCP])(\d)H')

QP_NOISE = re.compile(
    r'^(Do not write|outside the|box|Turn over.*|IB/.*|\*+\S*\*+|GCSE|'
    r'BIOLOGY|CHEMISTRY|PHYSICS|COMBINED SCIENCE.*|'
    r'Higher Tier.*|H|Answer all questions.*|Centre number.*|Surname|'
    r'Forename\(s\)|Candidate (number|signature)|I declare.*|Please write.*|'
    r'\d{1,3})\s*$', re.IGNORECASE)

MS_NOISE = re.compile(
    r'^(AO\s*/|Question Answers?( Extra information)? Mark|Spec\.?\s*Ref\.?|'
    r'MARK SCHEME.*|\d{1,2})\s*$', re.IGNORECASE)

FIGURE_RE = re.compile(r"\b(Figure|Table)\s+\d+\b", re.IGNORECASE)


def parse_filename(fname):
    m = CODE_RE_COMBINED.search(fname)
    if m:
        key = f"8464{m.group(1)}{m.group(2)}H"
    else:
        m2 = CODE_RE_SIMPLE.search(fname)
        if not m2:
            return None
        key = f"{m2.group(1)}{m2.group(2)}H"
    m3 = SESSION_RE.search(fname)
    if not m3:
        return None
    kind_raw, session_raw, _ext = m3.groups()
    kind = "QP" if kind_raw in ("QP", "SQP") else "MS"
    session_raw = session_raw.strip("-")
    if kind_raw in ("SQP", "SMS"):
        session = f"SPECIMEN-{session_raw}" if session_raw else "SPECIMEN"
    else:
        session = session_raw or "SPECIMEN"
    session = re.sub(r'\s*\(\d+\)$', '', session).strip()
    return key, session, kind


def guess_source_url(code, session):
    m = re.match(r'^(JUN|NOV)(\d{2})$', session)
    if not m:
        return None
    mon, yy = m.groups()
    month = "june" if mon == "JUN" else "november"
    year = f"20{yy}"
    return f"https://filestore.aqa.org.uk/sample-papers-and-mark-schemes/{year}/{month}/AQA-{code}-QP-{session}.PDF"


def scan_subject(subject):
    qp_dir = os.path.join(ROOT, subject, "Higher", "Question Papers")
    ms_dir = os.path.join(ROOT, subject, "Higher", "Mark Schemes")
    qps, mss = {}, {}
    for fname in sorted(os.listdir(qp_dir)):
        parsed = parse_filename(fname)
        if parsed:
            qps[(parsed[0], parsed[1])] = os.path.join(qp_dir, fname)
    for fname in sorted(os.listdir(ms_dir)):
        parsed = parse_filename(fname)
        if parsed:
            mss[(parsed[0], parsed[1])] = os.path.join(ms_dir, fname)
    return qps, mss


def extract_qp(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = [l for l in text.splitlines() if l.strip() and not QP_NOISE.match(l.strip())]
    body = "\n" + "\n".join(lines)
    marker = re.compile(r'\n(\d\s\d\s\.\s\d)\s')
    matches = list(marker.finditer(body))
    out = {}
    order = []
    for idx, m in enumerate(matches):
        ref_raw = m.group(1).replace(" ", "")
        ref = f"{ref_raw[0:2]}.{ref_raw[3]}"
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        chunk = body[m.end():end].strip()
        chunk = re.sub(r'\s+', ' ', chunk)[:600]
        out[ref] = chunk
        order.append(ref)
    return out, order


def extract_ms(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    start = text.find("\nQuestion 1\n")
    if start == -1:
        start = 0
    body = text[start:]
    marker = re.compile(r'\n(\d{2}\.\d{1,2})\b')
    matches = list(marker.finditer(body))
    out = {}
    for idx, m in enumerate(matches):
        ref = m.group(1)
        # sanity: ignore refs with a part number > 20 (garbage decimal matches)
        try:
            main, sub = ref.split(".")
            if int(main) > 20 or int(sub) > 20:
                continue
        except ValueError:
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        chunk = body[m.end():end]
        clean_lines = [l for l in chunk.splitlines() if l.strip() and not MS_NOISE.match(l.strip())]
        cleaned = "\n".join(clean_lines).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)[:500]
        if ref not in out:  # keep first occurrence only
            out[ref] = cleaned
    return out


def group_by_parent(qp_dict, order, ms_dict):
    groups = {}
    group_order = []
    for ref in order:
        parent = ref.split(".")[0]
        if parent not in groups:
            groups[parent] = []
            group_order.append(parent)
        text = qp_dict[ref]
        groups[parent].append({
            "ref": ref,
            "text": text,
            "has_figure": bool(FIGURE_RE.search(text)),
            "ms_answer": ms_dict.get(ref) if ms_dict else None,
        })
    return [{"parent": p, "parts": groups[p]} for p in group_order]


def main():
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else None
    batch = sys.argv[2] if len(sys.argv) > 2 else None  # e.g. "1/2"
    subjects = [only] if only else SUBJECTS
    out_suffix = f"_{SUBJECT_KEY[only]}" if only else ""
    if batch:
        i, n = (int(x) for x in batch.split("/"))
        out_suffix += f"_batch{i}of{n}"

    index = {}
    stats = []
    t_start = time.time()
    for subject in subjects:
        subj_key = SUBJECT_KEY[subject]
        qps, mss = scan_subject(subject)
        items = sorted(qps.items())
        if batch:
            i, n = (int(x) for x in batch.split("/"))
            items = [item for idx, item in enumerate(items) if idx % n == (i - 1)]
        papers = []
        for (code, session), qp_path in items:
            try:
                qp_dict, order = extract_qp(qp_path)
            except Exception as e:
                print(f"  FAILED QP {qp_path}: {e}")
                continue
            ms_path = mss.get((code, session))
            ms_dict = None
            if ms_path:
                try:
                    ms_dict = extract_ms(ms_path)
                except Exception as e:
                    print(f"  FAILED MS {ms_path}: {e}")
            groups = group_by_parent(qp_dict, order, ms_dict)
            n_with_ms = sum(1 for g in groups for part in g["parts"] if part["ms_answer"])
            n_parts = sum(len(g["parts"]) for g in groups)
            papers.append({
                "title": f"AQA GCSE {subject} {code} {session} Higher Tier",
                "code": code,
                "session": session,
                "source": guess_source_url(code, session),
                "has_mark_scheme": ms_path is not None,
                "groups": groups,
            })
            stats.append((subject, code, session, n_parts, n_with_ms, ms_path is not None))
            print(f"  {subject} {code} {session}: {n_parts} parts, {n_with_ms} linked to MS, MS_file={'yes' if ms_path else 'no'}")
        index[subj_key] = papers

    with open(os.path.join(os.path.dirname(__file__), f"full_question_index{out_suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    total_papers = sum(len(v) for v in index.values())
    total_parts = sum(len(g["parts"]) for papers in index.values() for p in papers for g in p["groups"])
    total_linked = sum(1 for papers in index.values() for p in papers for g in p["groups"] for part in g["parts"] if part["ms_answer"])
    print(f"\nDONE in {time.time()-t_start:.1f}s")
    print(f"Total papers: {total_papers}, total sub-questions: {total_parts}, linked to a mark scheme answer: {total_linked}")


if __name__ == "__main__":
    main()
