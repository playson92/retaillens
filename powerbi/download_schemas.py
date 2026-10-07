"""Refresh pinned official Microsoft JSON schemas (explicit, network-only operation)."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent / "schemas"
BASE = "https://developer.microsoft.com/json-schemas/"
ROOTS = [
    "fabric/pbip/pbipProperties/1.0.0/schema.json",
    "fabric/item/report/definitionProperties/2.0.0/schema.json",
    "fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "fabric/item/report/definition/report/3.3.0/schema.json",
    "fabric/item/report/definition/page/2.1.0/schema.json",
    "fabric/item/report/definition/visualContainer/2.9.0/schema.json",
    "fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
]


def get(url):
    with urlopen(Request(url, headers={"User-Agent": "RetailLens-schema-pin"}), timeout=60) as r:
        return r.read()


def refs(node):
    if isinstance(node, dict):
        if "$ref" in node:
            yield node["$ref"]
        for value in node.values():
            yield from refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from refs(value)


def main():
    commit = json.loads(get("https://api.github.com/repos/microsoft/json-schemas/commits/main"))[
        "sha"
    ]
    pending = [BASE + path for path in ROOTS]
    files = {}
    ROOT.mkdir(parents=True, exist_ok=True)
    while pending:
        url = pending.pop()
        if url in files:
            continue
        relative = url.removeprefix(BASE)
        if relative == url or ".." in relative:
            raise ValueError(f"Unexpected schema reference: {url}")
        raw = "https://raw.githubusercontent.com/microsoft/json-schemas/" + commit + "/" + relative
        schema = json.loads(get(raw))
        payload = (json.dumps(schema, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        filename = relative.replace("/", "_")
        (ROOT / filename).write_bytes(payload)
        files[url] = {
            "file": filename,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "source": raw,
        }
        for ref in refs(schema):
            target, _ = urldefrag(urljoin(url, ref))
            if target != url:
                pending.append(target)
    manifest = {
        "repository": "https://github.com/microsoft/json-schemas",
        "commit": commit,
        "files": files,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(files)} official schemas at {commit}")


if __name__ == "__main__":
    main()
