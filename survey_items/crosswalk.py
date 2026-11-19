"""Map every (wave, item code) in FEVS 2012-2024 to one canonical question.

Item codes are not stable across waves: OPM renumbers items (job satisfaction is Q69 in 2012 and Q70
in 2024), and a code can be reused for a different question. So a question is identified by its
wording and its response scale, never by its code.

Rules, in order:
1. Two item-waves with the same normalized wording and the same response scale are the same question.
   A wave whose codebook has no response labels (2012-2013) takes the scale of the same wording in
   the nearest later wave, and is marked scale_source='inherited'.
2. Wordings that are near-duplicates (similarity >= NEAR) must have a reviewed decision in
   wording_decisions.csv: 'same' (typo or example edit), 'reworded' (same construct, the wording
   changed, so trends get a break marker), or 'different'. The build fails on any unreviewed pair,
   so a new wave cannot slip a changed question into a trend without someone deciding.
3. One question never has two different known response scales, and never two codes in one wave.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

NEAR = 0.85
HERE = Path(__file__).resolve().parent
DECISIONS = HERE / "wording_decisions.csv"
UNTRENDED = "untrended option"
SEVERITY = {"unchanged": 0, "same": 1, "reworded": 2}


class CrosswalkError(ValueError):
    """The item catalog and the reviewed decisions disagree; the message lists every problem."""


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def scale_of(responses: dict) -> tuple:
    """The substantive scale: numeric codes and their labels. 'X' (Do Not Know / No Basis to Judge)
    is a non-response option that OPM drops from some items after 2021, so it does not split a question."""
    return tuple(sorted((k, normalize(v)) for k, v in responses.items() if k.strip().isdigit()))


@dataclass(frozen=True)
class Node:
    text: str      # normalized wording, or a placeholder for items without codebook text
    scale: tuple   # () when the codebook gives no labels


def load_decisions(path: Path = DECISIONS) -> dict[frozenset, tuple[str, str]]:
    with open(path, newline="") as f:
        return {frozenset((r["text_a"], r["text_b"])): (r["decision"], r["reason"]) for r in csv.DictReader(f)}


def _node(row: dict) -> Node | None:
    if row["is_redacted"]:
        return None
    scale = scale_of(row["responses"])
    if not normalize(row["item_text"]) or (re.search(r"_\d+$", row["item_code"]) and [k for k, _ in scale] == ["1"]):
        # A check-all-that-apply option: the codebook prints the option ("Paid or Unpaid Leave") but not
        # the question it belongs to, and the same option appears under several questions. Its wording
        # cannot identify it, so it stays wave-specific and is never trended.
        return Node(f"{UNTRENDED} {row['wave']} {row['item_code'].lower()} {normalize(row['item_text'])}", scale)
    return Node(normalize(row["item_text"]), scale)


def near_pairs(texts) -> list[tuple[str, str, float]]:
    keys = sorted(set(texts))
    out = []
    for i, a in enumerate(keys):
        sm = difflib.SequenceMatcher(None, a, autojunk=False)
        for b in keys[i + 1:]:
            sm.set_seq2(b)
            if sm.real_quick_ratio() >= NEAR and sm.quick_ratio() >= NEAR and sm.ratio() >= NEAR:
                out.append((a, b, sm.ratio()))
    return out


def build(rows: list[dict], decisions: dict[frozenset, tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Return (questions, crosswalk). Raise CrosswalkError listing every unresolved problem."""
    problems = []
    nodes = {(r["wave"], r["item_code"]): _node(r) for r in rows}
    real = [n for n in nodes.values() if n]
    texts = {n.text for n in real}

    for a, b, s in near_pairs(t for t in texts if not t.startswith(UNTRENDED)):
        if frozenset((a, b)) not in decisions:
            problems.append(f"unreviewed near-duplicate wording ({s:.2f}): '{a}' vs '{b}'")
    for pair, (decision, _) in decisions.items():
        if decision not in ("same", "reworded", "different"):
            problems.append(f"unknown decision '{decision}' for {sorted(pair)}")
        missing = [t for t in pair if t not in texts]
        if missing:
            problems.append(f"decision refers to wording not in any wave: {missing}")

    # Inherit a scale for unlabeled waves from the nearest later wave with the same wording.
    by_text: dict[str, list[tuple[int, str]]] = {}
    for (wave, code), n in nodes.items():
        if n:
            by_text.setdefault(n.text, []).append((wave, code))
    inherited = set()
    for text, keys in by_text.items():
        labelled = sorted((w, nodes[(w, c)].scale) for w, c in keys if nodes[(w, c)].scale)
        for w, c in keys:
            if not nodes[(w, c)].scale and labelled:
                later = [s for lw, s in labelled if lw > w] or [labelled[-1][1]]
                nodes[(w, c)] = Node(text, later[0])
                inherited.add((w, c))

    parent: dict[Node, Node] = {n: n for n in nodes.values() if n}

    def find(n: Node) -> Node:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def compatible(x: Node, y: Node) -> bool:
        return not x.scale or not y.scale or x.scale == y.scale

    unique = list(parent)
    for pair, (decision, _) in decisions.items():
        if decision in ("same", "reworded") and len(pair) == 2:
            a, b = tuple(pair)
            for x in (n for n in unique if n.text == a):
                for y in (n for n in unique if n.text == b and compatible(x, n)):
                    parent[find(x)] = find(y)

    groups: dict[Node, list[tuple[int, str]]] = {}
    for key, n in nodes.items():
        if n:
            groups.setdefault(find(n), []).append(key)

    questions, crosswalk = [], []
    ordered = sorted(groups.values(), key=lambda ks: min((w, _code_order(c)) for w, c in ks))
    for i, keys in enumerate(ordered, start=1):
        qid = f"fq{i:03d}"
        keys.sort()
        scales = {nodes[k].scale for k in keys if nodes[k].scale}
        if len(scales) > 1:
            problems.append(f"{qid} mixes response scales: {sorted(keys)}")
        waves = [w for w, _ in keys]
        if len(waves) != len(set(waves)):
            problems.append(f"{qid} has two item codes in one wave: {sorted(keys)}")
        text_of = {k: next(r["item_text"] for r in rows if (r["wave"], r["item_code"]) == k) for k in keys}
        breaks, prev = [], None
        for k in keys:
            status = "first" if prev is None else _change(nodes[prev].text, nodes[k].text, decisions)
            if status == "reworded":
                breaks.append(k[0])
            crosswalk.append({"wave": k[0], "item_code": k[1], "question_id": qid, "item_text": text_of[k],
                              "wording_status": status,
                              "scale_source": "inherited" if k in inherited else
                              ("codebook" if nodes[k].scale else "none")})
            prev = k
        scale = next(iter(scales), ())
        questions.append({"question_id": qid, "canonical_text": text_of[keys[-1]],
                          "first_wave": keys[0][0], "last_wave": keys[-1][0], "n_waves": len(keys),
                          "waves": " ".join(str(w) for w in waves),
                          "wording_breaks": " ".join(str(w) for w in breaks),
                          "response_scale": json.dumps(dict(scale))})

    for (wave, code), n in nodes.items():
        if not n:
            crosswalk.append({"wave": wave, "item_code": code, "question_id": "",
                              "item_text": next(r["item_text"] for r in rows
                                                if (r["wave"], r["item_code"]) == (wave, code)),
                              "wording_status": "redacted", "scale_source": "none"})
    if problems:
        raise CrosswalkError("\n".join(problems))
    crosswalk.sort(key=lambda r: (r["wave"], _code_order(r["item_code"])))
    return questions, crosswalk


def _code_order(code: str) -> tuple:
    m = re.match(r"([A-Z]+)(\d+)(?:_(\d+))?", code)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (code, 0, 0)


def _change(prev: str, cur: str, decisions) -> str:
    if prev == cur:
        return "unchanged"
    decision = decisions.get(frozenset((prev, cur)), ("reworded", ""))[0]
    return decision if decision in SEVERITY else "reworded"


def write(questions: list[dict], crosswalk: list[dict], out: Path = HERE) -> None:
    for name, data in (("question_catalog.csv", questions), ("question_crosswalk.csv", crosswalk)):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)


if __name__ == "__main__":
    import sys

    from survey_items.codebooks import read_all

    extracted = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "extracted"
    qs, cw = build(read_all(extracted), load_decisions())
    write(qs, cw)
    print(f"{len(cw)} item-waves -> {len(qs)} questions; "
          f"{sum(1 for r in cw if r['wording_status'] == 'redacted')} redacted; "
          f"{sum(1 for q in qs if q['wording_breaks'])} questions with a wording break")
