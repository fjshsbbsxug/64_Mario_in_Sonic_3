# Mario 64 in Sonic 3 A.I.R.

A Sonic 3 A.I.R. mod that adds **Mario from Super Mario 64** as an **extra character slot**.
He plays in 2D with regular Sonic 3 controls (no 3D controls), but keeps his SM64 moveset.

The mod contains no Nintendo assets. A small Python builder creates them from **your own
Super Mario 64 (USA) ROM**: it renders Mario's sprites from the 3D model and animations
inside the ROM, and extracts his voice clips from it as well.

## Installation

You need:
- Sonic 3 A.I.R. (start it at least once)
- **Python 3.8 or newer**. On Windows, get it from [python.org](https://www.python.org/downloads/) and tick *"Add python.exe to PATH"* during setup.
- A **Super Mario 64 (USA)** ROM (`.z64`, `.v64` or `.n64`)

Steps:
1. Download and unzip the release (`Mario64-S3AIR-Builder-v….zip`).
2. Build the mod:
   - **Windows:** double-click **`Build Mario Mod (Windows).bat`**, or drag your ROM onto it. When asked, drag the ROM into the window and press Enter.
   - **Linux / macOS:** run `./build_mario_mod.sh path/to/SuperMario64.z64`
   
   The builder installs the required Python packages (`numpy`, `pillow`, `soundfile`), creates the mod in about 10 seconds and copies it straight into your S3AIR `mods` folder.
3. Start Sonic 3 A.I.R., open **Mods** in the main menu and enable **Mario 64**.

The built mod is also saved as `output/Mario64.zip`, in case you want to install it by hand
(see "Where to put mods" in the S3AIR modding docs).

Command line options: `python build_mario_mod.py [ROM] [--out FOLDER] [--no-install] [--no-voices]`

## Selecting Mario

In **Normal Game → Data Select**, pick a new save slot (or "No Save") and press **Up/Down**
to cycle through the characters. Mario comes after Knuckles (or Knuckles & Tails, if unlocked):

`Sonic & Tails → Sonic → Tails → Knuckles → (Knuckles & Tails) → Mario`

Save slots remember Mario. He plays Sonic's route through the game.

Mod settings (**Options → Mods → Mario 64**):
- **Mario replaces Sonic**: "Also in Act Select & Time Attack" makes the "Sonic" choice there play as Mario.
- **Mario voice clips**: on/off.

## Controls (2D)

| Move | Input |
|---|---|
| Jump | Jump (A/B/C) |
| Double / Triple Jump | Jump again right after landing while running (triple jump needs some speed) |
| Backflip | Hold **Down** (crouch) + Jump |
| Long Jump | Run, hold **Down** + Jump (or Jump during a crouch slide) |
| Crouch slide | Down while running (replaces Sonic's roll) |
| Dive | Jump in mid-air. You land in a belly slide; Jump during it to roll out |
| Wall Kick | Jump while touching a wall in mid-air (a dive into a wall also works) |
| Ground Pound | **Down** in mid-air |

Mario defeats enemies by jumping on them or by attacking with any of his jumps, dives, slides
and the ground pound. He has no Spindash, Drop Dash, Insta-Shield, Super Peel-Out, shield
abilities or Super form.

## How it works

- `builder/rom.py` checks the ROM and reads Mario's data from it: the MIO0-compressed model segment, the animation table and the VADPCM voice samples (with a pure-Python decoder).
- `builder/model.py` interprets the F3D display lists of Mario's high-poly model and rasterizes them with N64-style lighting and texturing.
- `builder/sprites.py` renders about 90 frames from a side view turned slightly towards the camera. It supersamples them 4×, then downsamples, quantizes them to a shared 5-bit-per-channel palette and packs them into a sprite sheet.
- `builder/icons.py` draws the HUD lives icon, the "MARIO" results nameplate, the Data Select portrait and the mod icons.
- `builder/audio.py` writes the voice clips as Ogg Vorbis files (through the `soundfile` package, or `ffmpeg` if that's installed instead).
- `mod/scripts/*.lemon` is the script part of the mod:
  - `mario_dataselect.lemon` adds the extra slot. Save slots store character value `5` for Mario.
  - `mario_moves.lemon` makes Mario use the Sonic character object (and Sonic's route) and replaces the moveset.
  - `mario_render.lemon` replaces the player sprites via `Standalone.getModdedAnimationSpriteKey`, and also swaps the HUD lives icon and the results nameplate.

`python make_release.py` packages the builder into `dist/` for a release.

## Known limitations

- Some non-player graphics still show Sonic: the AIZ intro (Super Sonic), signposts, the
  continue screen, Blue Sphere special stages, and the lives icons inside Data Select slots.
- Mario's sprites are true-color, so they are not tinted by underwater palettes.
- Not available in Competition mode.
- Only the USA version of Super Mario 64 is supported.
