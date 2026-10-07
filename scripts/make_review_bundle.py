"""Compact source/evidence bundle, applicable EMPTY_TREE patch, checksum and ZIP audit."""

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--run", type=Path)
    cli.add_argument("--baseline", default=EMPTY_TREE)
    args = cli.parse_args()
    run = (
        args.run
        or ROOT
        / "output"
        / "codex_runs"
        / (ROOT / "output" / "current_run.txt").read_text().strip()
    )
    run = run.resolve()
    if not run.is_relative_to(ROOT / "output" / "codex_runs"):
        raise ValueError("Run directory must stay inside output/codex_runs")
    run.mkdir(parents=True, exist_ok=True)
    head = git("rev-parse", "HEAD").decode().strip()
    state = git("status", "--porcelain=v1").decode()
    if state:
        raise ValueError("Commit reviewed source before packaging; working tree must be clean")
    patch = git("diff", "--binary", args.baseline, head)
    (run / "changes.patch").write_bytes(patch)
    paths = git("ls-files", "-z").decode().strip("\0").split("\0")
    source = {}
    for name in paths:
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or name.startswith(("output/", "data/raw/", ".env", ".git/", ".venv/"))
        ):
            if name == ".env.example" or name == "data/raw/.gitkeep":
                pass
            else:
                raise ValueError(f"Excluded file accidentally tracked: {name}")
        source[name] = git("show", f"{head}:{name}")
    # Validate on a clean, isolated checkout. No unrelated workspace is removed.
    with tempfile.TemporaryDirectory(prefix="retaillens_patch_", dir=ROOT / "output") as temporary:
        directory = Path(temporary)
        if not directory.resolve().is_relative_to((ROOT / "output").resolve()):
            raise ValueError("Patch verification directory escaped the project output directory")
        git("init", "-q", cwd=directory)
        if args.baseline != EMPTY_TREE:
            git("fetch", str(ROOT), args.baseline, cwd=directory)
            git("checkout", "--detach", "FETCH_HEAD", cwd=directory)
        git("apply", "--check", str(run / "changes.patch"), cwd=directory)
        git("apply", str(run / "changes.patch"), cwd=directory)
        git("add", ".", cwd=directory)
        expected_tree = git("rev-parse", f"{head}^{{tree}}").decode().strip()
        applied_tree = git("write-tree", cwd=directory).decode().strip()
        if expected_tree != applied_tree:
            raise ValueError("Applied patch does not reproduce the final source tree")
    write_json(
        run / "patch_check.json",
        {
            "status": "PASS",
            "baseline": args.baseline,
            "head": head,
            "tree": expected_tree,
            "check": "git apply --check, apply, git write-tree equality",
        },
    )
    manifest_path = run / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    manifest.update(
        {
            "repo": str(ROOT),
            "branch": git("branch", "--show-current").decode().strip(),
            "baseline": "EMPTY_TREE" if args.baseline == EMPTY_TREE else args.baseline,
            "baseline_sha": args.baseline,
            "final_head": head,
            "final_worktree": state,
            "files": [
                {"path": name, "bytes": len(data), "sha256": digest(data)}
                for name, data in source.items()
            ],
            "patch_check": "PASS",
        }
    )
    write_json(manifest_path, manifest)
    # Evidence only: explicit extension/size policy; never include a cache, database or ZIP.
    evidence = {}
    for path in sorted(run.rglob("*")):
        if any(part in {"unit_tmp", "integration_tmp"} for part in path.relative_to(run).parts):
            continue
        if path.name == "bundle_contents.json":
            continue
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".log", ".patch", ".csv"}:
            if path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError(f"Evidence artifact too large for compact review: {path.name}")
            evidence[path.relative_to(run).as_posix()] = path.read_bytes()
    archive = run / "REVIEW_BUNDLE.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for name, data in source.items():
            zipped.writestr(f"source/{name}", data)
        for name, data in evidence.items():
            zipped.writestr(f"review/{name}", data)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("ZIP integrity failure")
        contents = [
            {"path": item.filename, "bytes": item.file_size, "compressed_bytes": item.compress_size}
            for item in zipped.infolist()
        ]
        assert len(contents) == len({item["path"] for item in contents}), "Duplicate ZIP entries"
    write_json(
        run / "bundle_contents.json",
        {
            "status": "PASS",
            "entries": contents,
            "zip_bytes": archive.stat().st_size,
            "zip_sha256": digest(archive.read_bytes()),
            "zip_integrity": "PASS",
            "patch_check": "PASS",
        },
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "zip": str(archive),
                "bytes": archive.stat().st_size,
                "entries": len(contents),
                "patch_check": "PASS",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
