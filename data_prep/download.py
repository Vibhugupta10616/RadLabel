"""Download the Open-i report archive, verify it, extract the XML into its own directory.

Usage: python -I data_prep/download.py data/raw
Open-i is tried first; if it returns something else (e.g. a maintenance page) the identical
Wayback Machine capture is used (Academic Torrents is the manual fallback). Whatever the source,
the SHA-256 must match; the URL used is recorded in data/raw/source.json.
"""

import hashlib
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

URLS = [
    "https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz",
    "https://web.archive.org/web/20211130094334id_/https://openi.nlm.nih.gov/imgs/collections/NLMCXR_reports.tgz",
]
SHA256 = "8fb6de7eec73d8c3665067ad4bb003ccd57f971ae316d2642e1627ac7268667a"


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tgz = out / "NLMCXR_reports.tgz"
    if not (tgz.exists() and hashlib.sha256(tgz.read_bytes()).hexdigest() == SHA256):
        for url in URLS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "radlabel-data-prep"})
                data = urllib.request.urlopen(req, timeout=120).read()
            except OSError as e:
                print(f"skip {url}: {e}")
                continue
            if hashlib.sha256(data).hexdigest() == SHA256:
                tgz.write_bytes(data)
                (out / "source.json").write_text(json.dumps({"url": url, "sha256": SHA256}), encoding="utf-8")
                print(f"downloaded {len(data)} bytes from {url}")
                break
            print(f"skip {url}: checksum mismatch ({len(data)} bytes)")
        else:
            sys.exit("could not download a verified NLMCXR_reports.tgz")
    xml_dir = out / "xml"
    if not (xml_dir / "ecgen-radiology").exists():
        with tarfile.open(tgz) as tf:
            tf.extractall(xml_dir, filter="data")  # untrusted archive: data-only extraction
    print(len(list((xml_dir / "ecgen-radiology").glob("*.xml"))), "XML files in", xml_dir)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
