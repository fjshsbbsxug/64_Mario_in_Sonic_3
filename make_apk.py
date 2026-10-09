#!/usr/bin/env python3
"""
Builds the Android app (Mario 64 Mod Builder) as an APK, without Gradle or Android Studio.

The app is a WebView that runs the JavaScript mod builder (see make_web.py), so the mod
gets built right on the phone from the user's own ROM.

Needs a JDK (javac, keytool) and these Android tools, e.g. from Debian/Ubuntu packages
(apt install aapt dalvik-exchange zipalign apksigner android-sdk-platform-23):
  aapt, dx (or dalvik-exchange), zipalign, apksigner and an android.jar (API 21 or newer).
Paths can be given with --android-jar or the ANDROID_JAR environment variable.

The APK is signed with android/release.keystore, which is created on first use.

Usage: python make_apk.py [--out FILE]      (default: dist/Mario64-S3AIR-Builder-v<version>.apk)
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

import make_web

HERE = os.path.dirname(os.path.abspath(__file__))
ANDROID = os.path.join(HERE, "android")
BUILD = os.path.join(HERE, "build", "android")
KEYSTORE = os.path.join(ANDROID, "release.keystore")
KEY_ALIAS = "mario64builder"
KEY_PASS = "mario64builder"


def tool(*names):
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    raise SystemExit("Missing tool: %s" % " / ".join(names))


def find_android_jar(arg):
    candidates = [arg, os.environ.get("ANDROID_JAR")]
    for sdk in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"), "/usr/lib/android-sdk"):
        if sdk:
            candidates += sorted(glob.glob(os.path.join(sdk, "platforms", "android-*", "android.jar")), reverse=True)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    raise SystemExit("android.jar not found, use --android-jar")


def run(cmd, **kw):
    print("  " + " ".join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)))
    subprocess.check_call(cmd, **kw)


def main():
    ap = argparse.ArgumentParser(description="Builds the Mario 64 Mod Builder APK.")
    ap.add_argument("--out", help="output APK path")
    ap.add_argument("--android-jar")
    args = ap.parse_args()

    android_jar = find_android_jar(args.android_jar)
    aapt = tool("aapt")
    dx = tool("dx", "dalvik-exchange")
    zipalign = tool("zipalign")
    apksigner = tool("apksigner")
    javac = tool("javac")
    keytool = tool("keytool")

    with open(os.path.join(HERE, "mod", "mod.json")) as f:
        version_full = json.load(f)["Metadata"]["ModVersion"]
    version = version_full.rsplit(".0", 1)[0]
    parts = [int(p) for p in version_full.split(".")] + [0, 0, 0, 0]
    version_code = parts[0] * 1000000 + parts[1] * 10000 + parts[2] * 100 + parts[3]
    out = args.out or os.path.join(HERE, "dist", "Mario64-S3AIR-Builder-v%s.apk" % version)

    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    for d in ("assets", "gen", "classes"):
        os.makedirs(os.path.join(BUILD, d))

    print("Bundling the web builder...")
    html, _v = make_web.bundle()
    with open(os.path.join(BUILD, "assets", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    with open(os.path.join(ANDROID, "AndroidManifest.xml"), encoding="utf-8") as f:
        manifest = f.read().replace("@VERSION_CODE@", str(version_code)).replace("@VERSION_NAME@", version)
    manifest_path = os.path.join(BUILD, "AndroidManifest.xml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest)

    print("Packaging resources...")
    unsigned = os.path.join(BUILD, "app-unsigned.apk")
    run([aapt, "package", "-f", "-M", manifest_path, "-S", os.path.join(ANDROID, "res"), "-A", os.path.join(BUILD, "assets"),
         "-I", android_jar, "-J", os.path.join(BUILD, "gen"), "-F", unsigned])

    print("Compiling Java...")
    sources = glob.glob(os.path.join(ANDROID, "src", "**", "*.java"), recursive=True)
    sources += glob.glob(os.path.join(BUILD, "gen", "**", "*.java"), recursive=True)
    run([javac, "-nowarn", "-Xlint:-options", "-source", "8", "-target", "8", "-encoding", "UTF-8",
         "-bootclasspath", android_jar, "-classpath", android_jar, "-d", os.path.join(BUILD, "classes")] + sources)

    print("Converting to dex...")
    run([dx, "--dex", "--min-sdk-version=21", "--output=" + os.path.join(BUILD, "classes.dex"), os.path.join(BUILD, "classes")])
    run([aapt, "add", unsigned, "classes.dex"], cwd=BUILD, stdout=subprocess.DEVNULL)

    print("Aligning and signing...")
    aligned = os.path.join(BUILD, "app-aligned.apk")
    run([zipalign, "-f", "4", unsigned, aligned])
    if not os.path.exists(KEYSTORE):
        run([keytool, "-genkeypair", "-keystore", KEYSTORE, "-alias", KEY_ALIAS, "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "10000", "-storepass", KEY_PASS, "-keypass", KEY_PASS, "-dname", "CN=Mario 64 Mod Builder"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run([apksigner, "sign", "--ks", KEYSTORE, "--ks-key-alias", KEY_ALIAS, "--ks-pass", "pass:" + KEY_PASS,
         "--key-pass", "pass:" + KEY_PASS, "--min-sdk-version", "21", "--out", out, aligned])
    run([apksigner, "verify", out])
    print("\n%s (%d KB)" % (out, os.path.getsize(out) // 1024))


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
