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
import json
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


def build(rom_path, out_dir, install, voices, mods_dir=None):
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
        mods = choose_mods_folder(mods_dir)
        if mods:
            install_mod(mod_dir, mods)
        else:
            print("\nThe mod was not installed. Copy the 'Mario64' folder or zip from the folder above")
            print("into your S3AIR 'mods' folder yourself, then enable it in the Mods menu.")
    else:
        print("\nCopy the 'Mario64' folder or zip into your S3AIR 'mods' folder, then enable it in the Mods menu.")


SETTINGS_FILE = os.path.join(HERE, "builder_settings.json")


def _load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=1)
    except OSError:
        pass


def _clean_path(path):
    path = path.strip()
    if path.startswith("& "):
        path = path[2:].strip()
    return os.path.expanduser(os.path.expandvars(path.strip('"').strip("'")))


def choose_mods_folder(mods_dir=None):
    """The mods folder to install into: --mods-dir, otherwise the last one chosen or the detected one,
    which the user can confirm or change. Returns None to skip installing."""
    if mods_dir:
        return _clean_path(mods_dir)

    settings = _load_settings()
    default = settings.get("mods_dir") or s3air_mods_folder()
    if not sys.stdin.isatty():
        return default

    print("\nWhere should the mod be installed?")
    if default:
        print("  Mods folder: %s" % default)
        print("Press Enter to use this folder, or drag & drop / type another folder (or 'skip' to not install):")
    else:
        print("  The Sonic 3 A.I.R. mods folder was not found automatically.")
        if sys.platform.startswith("win"):
            print("  It's usually %APPDATA%\\Sonic3AIR\\mods")
        print("Drag & drop / type the folder to install into, or press Enter to not install:")
    try:
        answer = input("> ")
    except EOFError:
        answer = ""
    answer = _clean_path(answer)
    if answer.lower() == "skip":
        return None
    if not answer:
        return default

    if not os.path.isdir(answer):
        try:
            os.makedirs(answer)
        except OSError as e:
            print("Can't use that folder (%s)." % e)
            return None
    if os.path.basename(os.path.normpath(answer)).lower() != "mods" and os.path.isdir(os.path.join(answer, "mods")):
        # The Sonic3AIR folder itself was chosen: use its mods folder
        answer = os.path.join(answer, "mods")
    settings["mods_dir"] = os.path.abspath(answer)
    _save_settings(settings)
    print("OK, using %s (remembered for next time)." % settings["mods_dir"])
    return settings["mods_dir"]


MOD_IDS = ("mario64-extra-slot", "mario64-sm64-movement")


def _is_mario_mod_json(text):
    return any('"%s"' % mod_id in text for mod_id in MOD_IDS)


def find_installed_copies(mods):
    """All copies of this mod (any version) in the mods folder: list of (path, active-mods entry)."""
    found = []
    for root, dirs, files in os.walk(mods):
        depth = os.path.relpath(root, mods).count(os.sep) + (0 if root == mods else 1)
        if depth > 3:
            dirs[:] = []
            continue
        if root != mods and "mod.json" in files:
            try:
                with open(os.path.join(root, "mod.json"), encoding="utf-8", errors="replace") as f:
                    if _is_mario_mod_json(f.read()):
                        found.append((root, os.path.relpath(root, mods).replace(os.sep, "/")))
            except OSError:
                pass
            dirs[:] = []
            continue
        for fn in files:
            if not fn.lower().endswith(".zip"):
                continue
            path = os.path.join(root, fn)
            try:
                with zipfile.ZipFile(path) as z:
                    for name in z.namelist():
                        if name.endswith("mod.json") and name.count("/") <= 1 and _is_mario_mod_json(z.read(name).decode("utf-8", "replace")):
                            inner = name[:-len("mod.json")].rstrip("/")
                            rel = os.path.relpath(path, mods).replace(os.sep, "/")
                            found.append((path, rel + "/" + inner if inner else rel))
                            break
            except (OSError, zipfile.BadZipFile):
                pass
    return found


def game_is_running():
    if not sys.platform.startswith("win"):
        return False
    try:
        import subprocess
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Sonic3AIR.exe"], capture_output=True, text=True).stdout
        return "sonic3air.exe" in out.lower()
    except Exception:
        return False


def install_mod(mod_dir, mods):
    """Installs the mod as mods/Mario64, moves any other copies of it out of the mods folder, and activates it."""
    if game_is_running():
        print("\nSonic 3 A.I.R. is running - please close it, then press Enter to install the mod.")
        try:
            input()
        except EOFError:
            pass

    os.makedirs(mods, exist_ok=True)
    target = os.path.join(mods, MOD_FOLDER_NAME)

    # Other copies (e.g. a Mario64.zip from the web builder, or older versions) would be listed as
    # separate mods, and the game may keep using one of those, so move them out of the mods folder
    backup = os.path.join(os.path.dirname(mods), "mods_backup_mario64")
    moved = []
    for path, _entry in find_installed_copies(mods):
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(target)):
            continue
        os.makedirs(backup, exist_ok=True)
        dest = os.path.join(backup, os.path.basename(path))
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(backup, "%s (%d)" % (os.path.basename(path), n))
            n += 1
        shutil.move(path, dest)
        moved.append(dest)

    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(mod_dir, target)
    print("\nInstalled into your Sonic 3 A.I.R. mods folder:\n  %s" % target)
    if moved:
        print("Moved other copies of the Mario mod out of the mods folder, so they don't get in the way:")
        for m in moved:
            print("  " + m)

    # Activate it (and drop entries of the copies that are gone)
    active_path = os.path.join(mods, "active-mods.json")
    data = {"ActiveMods": [], "UseLegacyLoading": False}
    try:
        with open(active_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    remaining = set(e for _p, e in find_installed_copies(mods))
    active = [e for e in data.get("ActiveMods", []) if not isinstance(e, str) or e in remaining or not _looks_like_mario_entry(e)]
    if MOD_FOLDER_NAME not in active:
        active.append(MOD_FOLDER_NAME)
    data["ActiveMods"] = active
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print("The mod is activated: start the game and pick Mario in Data Select (he comes after Knuckles).")
    print("In the Mods menu it's listed as '%s'." % _mod_display_name(target))


def _looks_like_mario_entry(entry):
    return "mario64" in entry.lower()


def _mod_display_name(mod_dir):
    try:
        with open(os.path.join(mod_dir, "mod.json"), encoding="utf-8") as f:
            return json.load(f)["Metadata"]["Name"]
    except (OSError, ValueError, KeyError):
        return "Mario 64"


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
    ap.add_argument("--mods-dir", help="S3AIR mods folder to install into (default: ask, or the detected one)")
    args = ap.parse_args()

    interactive = args.rom is None
    print("=== Mario 64 for Sonic 3 A.I.R. - mod builder ===\n")
    rom_path = args.rom or ask_rom_path()
    if not rom_path:
        fail("No ROM given.")
    try:
        os.makedirs(args.out, exist_ok=True)
        build(rom_path, args.out, not args.no_install, not args.no_voices, args.mods_dir)
    finally:
        if interactive:
            try:
                input("\nPress Enter to close.")
            except EOFError:
                pass


if __name__ == "__main__":
    main()
