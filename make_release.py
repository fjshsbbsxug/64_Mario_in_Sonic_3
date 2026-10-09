#!/usr/bin/env python3
"""Packages the mod builder into dist/Mario64-S3AIR-Builder-<version>.zip for a release."""

import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["build_mario_mod.py", "Build Mario Mod (Windows).bat", "build_mario_mod.sh", "README.md"]
FOLDERS = ["builder", "mod"]


def main():
    with open(os.path.join(HERE, "mod", "mod.json")) as f:
        version = json.load(f)["Metadata"]["ModVersion"]
    name = "Mario64-S3AIR-Builder-v%s" % version.rsplit(".0", 1)[0]
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    path = os.path.join(HERE, "dist", name + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        entries = list(FILES)
        for folder in FOLDERS:
            for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
                if "__pycache__" in root:
                    continue
                entries += [os.path.relpath(os.path.join(root, fn), HERE) for fn in sorted(files)]
        for rel in entries:
            info = zipfile.ZipInfo.from_file(os.path.join(HERE, rel), os.path.join(name, rel))
            info.compress_type = zipfile.ZIP_DEFLATED
            if rel.endswith(".sh"):
                info.external_attr = 0o755 << 16
            with open(os.path.join(HERE, rel), "rb") as f:
                z.writestr(info, f.read())
    print(path)


if __name__ == "__main__":
    main()
