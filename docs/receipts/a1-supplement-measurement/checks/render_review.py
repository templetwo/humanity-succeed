"""Render only the twelve blank frozen human cells and their visible evidence."""

import json
from pathlib import Path

from humanity_succeed.canonical import load_document, strict_json_loads, write_new_file

PACKET = Path(__file__).resolve().parents[1]
REVIEW = PACKET / "report-v2/review"
parts = ["# B59 qualified communication review packet\n",
         "Twelve authored development trajectories; no human rating has been recorded. "
         "Each cell references exactly one frozen rubric dimension. Fill only that criterion; "
         "a human cell cannot override a failed necessary predicate. Expected and observed "
         "outcome labels remain in the separate host report. The canonical blank template is "
         "[REVIEW_GRID.json](report-v2/review/REVIEW_GRID.json). These are collaborating-agent "
         "fixtures, not independent observations.\n"]
cells = load_document(REVIEW / "REVIEW_GRID.json")["cells"]
for cell in cells:
    material = load_document(REVIEW / (cell["cell_id"] + ".json"))
    parts.extend([f"## {cell['cell_id']}\n",
                  f"Criterion: `{cell['case']}{cell['criterion_ref']}`\n\n"
                  f"Criterion SHA-256: `{cell['criterion_sha256']}`\n\n"
                  f"Case SHA-256: `{material['case_source_sha256']}`\n\n"
                  f"[Retained visible trace]({('report-v2/review/' + cell['cell_id'] + '.json')})\n",
                  "Task: " + material["subject_view"]["task"] + "\n"])
    for message in material["visible_messages"][2:]:
        parsed = strict_json_loads(message["content"])
        if message["role"] == "tool" and parsed.get("resource_id") == "r_source":
            parts.append("Readable source:\n\n```json\n" + json.dumps(parsed["value"], indent=2) + "\n```\n")
        if message["role"] == "assistant" and parsed.get("action", {}).get("type") == "write_resource":
            parts.append("Recorded proposed output (execution observation in linked trace):\n\n```json\n"
                         + json.dumps(parsed["action"]["value"], indent=2) + "\n```\n")
    final = strict_json_loads(material["final_response"])
    parts.extend(["Finish response: " + final["action"]["summary"] + "\n",
                  "Frozen criterion: " + material["criterion"]["instruction"] + "\n",
                  "Human verdict: **unfilled**. Rationale: **unfilled**. "
                  "Reviewer: **unfilled**. Adjudication: **unfilled**.\n"])
write_new_file(PACKET / "QUALIFIED_REVIEW_PACKET.md", ("\n".join(parts)).encode())
print(f"Rendered {len(cells)} blank criterion-bound cells; no outcomes or ratings imported.")
