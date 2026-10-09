# Mario 64 in Sonic 3 A.I.R.

A Sonic 3 A.I.R. mod that adds **Mario from Super Mario 64** as an **extra character slot**.
He plays in 2D with regular Sonic 3 controls (no 3D controls), but keeps his SM64 moveset.

His sprites are rendered from the real SM64 3D model and animations, and his voice clips
come straight from the SM64 ROM. A build script generates all of these from your own game files.

## Selecting Mario

In **Normal Game → Data Select**, pick a new save slot (or "No Save") and press **Up/Down**
to cycle through the characters. Mario comes after Knuckles (or Knuckles & Tails, if unlocked):

`Sonic & Tails → Sonic → Tails → Knuckles → (Knuckles & Tails) → Mario`

Save slots remember Mario. He plays Sonic's route through the game.

Optional mod setting (**Options → Mods → Mario 64**):
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

## Building the mod

The repository does not contain any Nintendo or SEGA assets. Generate the mod from your own files:

Requirements: Python 3 with `numpy` and `Pillow`, `gcc` and `ffmpeg` (voice clip conversion).

```sh
python3 tools/build_mod.py \
    --sm64-decomp path/to/sm64-master \
    --sm64-rom    "path/to/Super Mario 64 (U).z64" \
    --s3air       path/to/sonic3air_game
```

- `--sm64-decomp`: the [SM64 decompilation](https://github.com/n64decomp/sm64) source. It provides Mario's model, display lists and animations.
- `--sm64-rom`: a **US** Super Mario 64 ROM in `.z64` (big endian) format. It provides the textures and voice clips.
- `--s3air`: your Sonic 3 A.I.R. game folder. The HUD font sprites in `doc/modding/sprites` are used to compose the "MARIO" name texts.
- `--no-voices`: skip voice clip extraction.

The output is `build/Mario64/` and `build/Mario64.zip`. Copy the `Mario64` folder (or the zip)
into your S3AIR `mods` folder, then enable it in the in-game **Mods** menu.

## How it works

- `tools/sm64model.py` is a small software renderer for Mario's high-poly model. It interprets the F3D display lists from `actors/mario/model.inc.c`, the skeleton from `geo.inc.c` and the animation tables, and decodes the RGBA16 textures from the ROM (MIO0).
- `tools/gen_sprites.py` renders about 90 frames with 4× supersampling, from a side view turned slightly towards the camera. It then downsamples them, quantizes them to a shared 5-bit-per-channel palette, and packs them into a sprite sheet.
- `tools/build_mod.py` puts the mod together: sprites, lives icon, Data Select portrait, the "MARIO" results nameplate and the voice clips (decoded with the decomp's `disassemble_sound.py` / `aifc_decode`).
- `mod/scripts/*.lemon` is the script part:
  - `mario_dataselect.lemon` adds the extra slot. Save slots store character value `5` for Mario.
  - `mario_moves.lemon` makes Mario use the Sonic character object (and Sonic's route) and replaces the moveset.
  - `mario_render.lemon` replaces the player sprites via `Standalone.getModdedAnimationSpriteKey`, and also swaps the HUD lives icon and the results nameplate.

## Known limitations

- Some non-player graphics still show Sonic: the AIZ intro (Super Sonic), signposts, the
  continue screen, Blue Sphere special stages, and the lives icons inside Data Select slots.
- Mario's sprites are true-color, so they are not tinted by underwater palettes.
- Not available in Competition mode.
