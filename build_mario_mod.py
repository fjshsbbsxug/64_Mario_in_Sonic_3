#!/usr/bin/env python3
"""
Mario 64 for Sonic 3 A.I.R. - mod builder

Builds the "Mario 64" mod from your own Super Mario 64 (USA) ROM:
Mario's sprites are rendered from the model and animations inside the ROM,
and his voice clips are extracted from it as well.

Usage:
    python build_mario_mod.py [path/to/SuperMario64.z64] [--out FOLDER] [--no-install] [--no-voices]

Without a ROM path, the builder asks for it (you can drag & drop the file into the window).
"""

import argparse
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "builder"))

MOD_FOLDER_NAME = "Mario64"


def fail(msg):
    print("\nERROR: " + msg)
    raise SystemExit(1)


try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
except ImportError:
    fail("Missing Python packages. Please run:\n\n    python -m pip install numpy pillow soundfile\n")

import audio  # noqa: E402
import icons  # noqa: E402
import model as mdl  # noqa: E402
import rom as romdata  # noqa: E402
import sprites  # noqa: E402


def s3air_mods_folder():
    """The Sonic 3 A.I.R. mods folder in the saved data directory, if the game was started at least once."""
    if sys.platform.startswith("win"):
        base = os.path.join(os.environ.get("APPDATA", ""), "Sonic3AIR")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Sonic3AIR")
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "Sonic3AIR")
    return os.path.join(base, "mods") if os.path.isdir(base) else None


def ask_rom_path():
    print("Please drag & drop your Super Mario 64 (USA) ROM into this window, then press Enter:")
    try:
        path = input("> ").strip()
    except EOFError:
        path = ""
    # Strip quotes / PowerShell call operator added by drag & drop
    if path.startswith("& "):
        path = path[2:].strip()
    return path.strip('"').strip("'")


def progress_bar(done, total):
    if not sys.stdout.isatty() and done != total and done % 15 != 0:
        return
    width = 30
    filled = int(width * done / total)
    sys.stdout.write(("\r" if sys.stdout.isatty() else "") + "  Rendering sprites [%s%s] %d/%d" % ("#" * filled, "." * (width - filled), done, total))
    sys.stdout.flush()
    if done == total or not sys.stdout.isatty():
        sys.stdout.write("\n")


def build(rom_path, out_dir, install, voices):
    print("Reading ROM: %s" % rom_path)
    try:
        rom = romdata.load_rom(rom_path)
    except (OSError, romdata.RomError) as e:
        fail(str(e))

    start = time.time()
    mod_dir = os.path.join(out_dir, MOD_FOLDER_NAME)
    if os.path.exists(mod_dir):
        shutil.rmtree(mod_dir)
    shutil.copytree(os.path.join(HERE, "mod"), mod_dir)
    sprites_dir = os.path.join(mod_dir, "sprites")
    os.makedirs(sprites_dir, exist_ok=True)

    print("Loading Mario's model and animations...")
    model = mdl.Model(romdata.mario_segment(rom))
    anims = romdata.load_animations(rom)

    head, portrait = sprites.render_all(model, anims, sprites_dir,
                                         os.path.join(mod_dir, "scripts", "mario_animdata.lemon"), progress_bar)
    print("Creating icons...")
    icons.write_icons(head, portrait, sprites_dir, mod_dir)

    if voices:
        encoder = audio.find_encoder()
        if encoder is None:
            print("NOTE: Voice clips skipped - no Ogg Vorbis encoder found.\n"
                  "      Install one with 'python -m pip install soundfile' and run the builder again to get them.")
            _disable_voices(mod_dir)
        else:
            print("Extracting voice clips...")
            audio.write_voices(rom, os.path.join(mod_dir, "audio"), encoder)
    else:
        _disable_voices(mod_dir)

    zip_path = os.path.join(out_dir, MOD_FOLDER_NAME + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(mod_dir):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, out_dir))

    print("\nDone in %.0f seconds." % (time.time() - start))
    print("  Mod folder: %s" % mod_dir)
    print("  Mod zip:    %s" % zip_path)

    if install:
        mods = s3air_mods_folder()
        if mods:
            os.makedirs(mods, exist_ok=True)
            target = os.path.join(mods, MOD_FOLDER_NAME)
            if os.path.exists(target):
                shutil.rmtree(target)
            shutil.copytree(mod_dir, target)
            print("\nInstalled into your Sonic 3 A.I.R. mods folder:\n  %s" % target)
            print("Start the game, open 'Mods' in the main menu and enable 'Mario 64'.")
        else:
            print("\nCouldn't find the Sonic 3 A.I.R. saved data folder (start the game once first),")
            print("so copy the 'Mario64' folder or zip into your S3AIR 'mods' folder yourself.")
    else:
        print("\nCopy the 'Mario64' folder or zip into your S3AIR 'mods' folder, then enable it in the Mods menu.")


def _disable_voices(mod_dir):
    """Without voice clips, default the voice setting to off so the game doesn't look for them."""
    path = os.path.join(mod_dir, "mod.json")
    with open(path) as f:
        text = f.read()
    marker = '"Variable": "mario.option.voice",'
    i = text.find(marker)
    if i >= 0:
        j = text.find('"DefaultValue": "1"', i)
        if j >= 0:
            text = text[:j] + '"DefaultValue": "0"' + text[j + len('"DefaultValue": "1"'):]
    with open(path, "w") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description="Builds the Mario 64 mod for Sonic 3 A.I.R. from your Super Mario 64 (USA) ROM.")
    ap.add_argument("rom", nargs="?", help="Super Mario 64 (USA) ROM (.z64, .v64 or .n64)")
    ap.add_argument("--out", default=os.path.join(HERE, "output"), help="output folder (default: ./output)")
    ap.add_argument("--no-install", action="store_true", help="don't copy the mod into the S3AIR mods folder")
    ap.add_argument("--no-voices", action="store_true", help="skip the voice clips")
    args = ap.parse_args()

    interactive = args.rom is None
    print("=== Mario 64 for Sonic 3 A.I.R. - mod builder ===\n")
    rom_path = args.rom or ask_rom_path()
    if not rom_path:
        fail("No ROM given.")
    try:
        os.makedirs(args.out, exist_ok=True)
        build(rom_path, args.out, not args.no_install, not args.no_voices)
    finally:
        if interactive:
            try:
                input("\nPress Enter to close.")
            except EOFError:
                pass


if __name__ == "__main__":
    main()
