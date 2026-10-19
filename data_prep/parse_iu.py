"""Parse IU (Open-i) XML reports into a flat JSONL with manual and automatic codes."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])

rows = []
for p in sorted(src.glob("*.xml"), key=lambda x: int(x.stem)):
    root = ET.parse(p).getroot()
    sec = {}
    for a in root.iter("AbstractText"):
        sec[a.get("Label")] = (a.text or "").strip()
    mesh = root.find("MeSH")
    major = [m.text.strip() for m in mesh.findall("major")] if mesh is not None else []
    auto = [m.text.strip() for m in mesh.findall("automatic")] if mesh is not None else []
    rows.append({
        "id": int(p.stem),
        "licence": (root.findtext("ccLicense") or "").strip(),
        "comparison": sec.get("COMPARISON", ""),
        "indication": sec.get("INDICATION", ""),
        "findings": sec.get("FINDINGS", ""),
        "impression": sec.get("IMPRESSION", ""),
        "major": major,
        "automatic": auto,
        "n_images": len(root.findall("parentImage")),
    })

with out.open("w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows), "reports written to", out)
