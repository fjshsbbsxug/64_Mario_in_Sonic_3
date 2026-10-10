#!/usr/bin/env python3
"""
Bundles the JavaScript mod builder (web/) into one self-contained HTML file.

The file contains the builder scripts, the static mod files (mod/) and the Ogg Vorbis
encoder, so it works offline in any modern browser and inside the Android app.

Usage: python make_web.py [--out FILE]      (default: dist/Mario64-S3AIR-Builder-v<version>.html)
"""

import argparse
import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
SCRIPTS = ["vendor/WasmMediaEncoder.min.js", "js/util.js", "js/rom.js", "js/model.js",
           "js/sprites.js", "js/icons.js", "js/extras.js", "js/audio.js", "js/build.js"]
MARKER = "<!-- @BUNDLE -->"


def read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


def script_tag(code):
    # Keep "</script>" inside strings from closing the tag
    return "<script>\n" + code.replace("</script", "<\\/script") + "\n</script>\n"


def mod_files():
    files = {}
    root = os.path.join(HERE, "mod")
    for base, _dirs, names in os.walk(root):
        for name in sorted(names):
            full = os.path.join(base, name)
            files[os.path.relpath(full, root).replace(os.sep, "/")] = read(full)
    return files


def bundle():
    version = json.loads(read(os.path.join(HERE, "mod", "mod.json")))["Metadata"]["ModVersion"].rsplit(".0", 1)[0]
    parts = [script_tag("window.M64_VERSION = %s;\nwindow.M64_MOD_FILES = %s;" % (json.dumps(version), json.dumps(mod_files(), indent=0))),
             script_tag("window.M64_OGG_WASM_BASE64 = \"%s\";" % base64.b64encode(read(os.path.join(WEB, "vendor", "ogg.wasm"), "rb")).decode("ascii"))]
    parts += [script_tag(read(os.path.join(WEB, s))) for s in SCRIPTS]
    html = read(os.path.join(WEB, "index.html"))
    if MARKER not in html:
        raise SystemExit("Bundle marker missing in web/index.html")
    return html.replace(MARKER, "".join(parts)), version


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--out")
    args = ap.parse_args()
    html, version = bundle()
    args.out = args.out or os.path.join(HERE, "dist", "Mario64-S3AIR-Builder-v%s.html" % version)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("%s (v%s, %d KB)" % (args.out, version, len(html.encode("utf-8")) // 1024))


if __name__ == "__main__":
    main()
