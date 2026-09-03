#!/usr/bin/env python3
"""Build hf-dataset/questions.jsonl from the repo's questions.json.

Run this after any change to questions.json so the Hugging Face copy never drifts
from the answer key the grader uses:

    python hf-dataset/build_jsonl.py

One JSON object per line, one line per question. The only transformation is the
must_include column: in questions.json a slot is either a plain string or
{"any": [synonyms]}. Arrow cannot infer a column that mixes strings and structs,
so every slot becomes a list of strings (a plain string becomes a one-element
list). A slot is satisfied when any one of its strings appears in the answer,
exactly as in bench.py. harness/diamondbench_metric.py converts the lists back.

Standard library only.
"""
import io
import json
import os

HERE = os.path.abspath(os.path.dirname(__file__))
SRC = os.path.join(HERE, "..", "questions.json")
DST = os.path.join(HERE, "questions.jsonl")

FIELDS = ["id", "category", "question", "must_include", "must_not_include",
          "correct_answer", "sources"]


def normalize_slot(slot):
    if isinstance(slot, dict):
        return list(slot.get("any", []))
    return [slot]


def main():
    data = json.load(io.open(SRC, encoding="utf-8-sig"))
    questions = data["questions"]
    n = 0
    with io.open(DST, "w", encoding="utf-8", newline="\n") as out:
        for q in questions:
            row = {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "must_include": [normalize_slot(s) for s in q["must_include"]],
                "must_not_include": list(q.get("must_not_include", [])),
                "correct_answer": q["correct_answer"],
                "sources": [{"claim": s.get("claim", ""), "source": s.get("source", ""),
                             "date": str(s.get("date", ""))} for s in q.get("sources", [])],
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print("wrote %d rows to %s (answer key version %s, updated %s)"
          % (n, DST, data.get("version"), data.get("updated")))


if __name__ == "__main__":
    main()
