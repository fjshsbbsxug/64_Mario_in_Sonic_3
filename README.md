# Mario 64 in Sonic 3 A.I.R.

A Sonic 3 A.I.R. mod that adds **Mario from Super Mario 64** as an **extra character slot**.
He plays in 2D with regular Sonic 3 controls (no 3D controls). His movement is a 2D port of
Super Mario 64's own Mario code: the same actions, speeds, gravity, jump heights, slopes,
slides and swimming, running at SM64's 30 actions per second.

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
   
   The builder installs the required Python packages (`numpy`, `pillow`, `soundfile`), creates the mod in about a minute and installs it into your S3AIR `mods` folder. Before installing, it shows the mods folder it found: press Enter to use it, or drag & drop / type a different folder (it remembers your choice; `--mods-dir FOLDER` sets it on the command line). It also activates the mod, and moves any other copies of the Mario mod (older versions, or a `Mario64.zip` from the web builder) to a `mods_backup_mario64` folder next to the mods folder, so they can't get in the way.
3. Start Sonic 3 A.I.R., open **Mods** in the main menu and enable **Mario 64 (SM64 movement)**.

The built mod is also saved as `output/Mario64.zip`, in case you want to install it by hand
(see "Where to put mods" in the S3AIR modding docs).

Command line options: `python build_mario_mod.py [ROM] [--out FOLDER] [--mods-dir FOLDER] [--no-install] [--no-voices]`

## Android

**Mario64-S3AIR-Builder-v….apk** builds the mod right on your phone, with no PC needed.

1. Install the APK. Your phone will ask you to allow installing apps from your browser or file manager.
2. Open **Mario 64 Mod Builder**, tap **Choose ROM file** and pick your Super Mario 64 (USA) ROM.
3. Tap **Build Mario64.zip**. It takes a few seconds up to about a minute, depending on the phone.
4. Tap **Save** and save `Mario64-v<version>.zip`, e.g. to *Downloads*.
5. Delete any older Mario zips (`Mario64.zip`, `Mario64 (1).zip`, `Mario64-v….zip`) from the Sonic 3 A.I.R. mods folder, then move the new zip there, and leave it zipped:
   `Android/data/org.eukaryot.sonic3air/files/mods`
   (start Sonic 3 A.I.R. once first, so the folder exists).
   On Android 11 and newer, many file managers can't open `Android/data`. Use one that can
   (e.g. ZArchiver), or copy the file over from a PC via USB.
   On Android 10 and older, the app can do this for you: tap **Install into Sonic 3 A.I.R.**
6. Start Sonic 3 A.I.R., open **Mods** and enable **Mario 64 (SM64 movement)**.

If Mario still moves like Sonic (standing still while sliding around), an older version of the mod is still installed: delete the old
`Mario64` folder from the mods folder, or deactivate the mod called just **Mario 64** (versions
before 2.1 had that name; the game shows a conflict warning when both are active).

The same builder also exists as a single web page, **Mario64-S3AIR-Builder-v….html**. Open it
in a browser on any device (PC, Android, iPhone/iPad), pick the ROM and download `Mario64.zip`.
Everything runs offline in the browser, and the ROM is never uploaded.

## Selecting Mario

In **Normal Game → Data Select**, pick a new save slot (or "No Save") and press **Up/Down**
to cycle through the characters. Mario comes after Knuckles (or Knuckles & Tails, if unlocked):

`Sonic & Tails → Sonic → Tails → Knuckles → (Knuckles & Tails) → Mario → Mario & Tails`

**Mario & Tails** works like Sonic & Tails: Tails follows Mario as his sidekick (and a second
player can control Tails with another controller). With *Tails Assist* enabled in the game's
options, hold **Up** and press **Jump** in mid-air to call Tails; jump into him to grab on, and
hold Up to fly higher. Save slots remember the choice. Mario plays
Sonic's route through the game, including the IceCap snowboard ride, where he rides his own
red snowboard, and the hollow tree in Angel Island Act 1: walk into it at any speed and it carries
Mario up around the trunk automatically.

Mod settings (**Options → Mods → Mario 64 (SM64 movement)**):
- **Mario replaces Sonic**: "Also in Act Select & Time Attack" makes the "Sonic" (and "Sonic & Tails") choice there play as Mario.
- **World scale**: "Sonic 3" (default) scales Mario's movement so he covers ground about as fast as
  Sonic does. "Mario 64" uses Mario's true size relative to the Sonic 3 levels (he is slower and jumps lower).
- **Mario voice clips**: on/off.

## Controls (2D)

The controls follow Super Mario 64:

| SM64 button | Gamepad | Keyboard (S3AIR default) |
|---|---|---|
| **A** (jump) | A | A |
| **B** (punch / kick / dive) | B or X | S or D |
| **Z** (crouch / ground pound) | Y, R or Down | W or Down |

Under *Options → Mods → Mario 64 → Controls*, you can switch to the Sonic 3 layout instead:
A/B jump, X (Genesis C) attacks and Down crouches.

| Move | Input |
|---|---|
| Walk / run | Left / Right (Mario accelerates like in SM64; reversing at speed makes him skid and turn) |
| Jump, Double Jump, Triple Jump | Jump; Jump again right after landing (the triple jump needs running speed) |
| Backflip | Hold **Z** (crouch) + Jump |
| Side Flip | Turn around while running, then Jump while skidding |
| Long Jump | Run, then **Z** (crouch slide) + Jump |
| Wall Kick | Jump right after hitting a wall in mid-air |
| Punch, punch, kick | **B** while standing (press repeatedly) |
| Dive / belly slide | **B** while running or in mid-air; Jump or B during the slide to roll out |
| Slide Kick | **B** during a crouch slide (Z while running) |
| Jump Kick | **B** in mid-air while jumping slowly |
| Ground Pound | **Z** in mid-air |
| Crouch / crawl | Hold **Z** (and Left/Right to crawl) |
| Swim | Underwater: Jump to swim a stroke, hold Jump to flutter kick, Up/Down to swim up/down. Jump at the surface (or from the floor in shallow water) to jump out |
| Water punch | **B** while swimming (defeats enemies and breaks walls underwater) |

Steep slopes make Mario slide like in SM64 (butt slide), and falling from high up makes him
land with a short stun.

Springs, bumpers and other objects launch Mario like Sonic. In boss fights, all of Mario's
jumps hit the boss (like Sonic's spin jump), and every hit (stomp, kick, punch, dive, slide
kick, ground pound) bounces him up and away from the boss.

Mario defeats enemies by jumping on them or with his attacks: punches, kicks, dives, slides
and the ground pound. Punches, kicks, dives and slides also break Sonic 3's breakable walls
and rocks. He has no Spindash, Drop Dash, Insta-Shield, Super Peel-Out, shield abilities or
Super form.

## How it works

- `builder/rom.py` checks the ROM and reads Mario's data from it: the MIO0-compressed model segment, the animation table and the VADPCM voice samples (with a pure-Python decoder).
- `builder/model.py` interprets the F3D display lists of Mario's high-poly model and rasterizes them with N64-style lighting and texturing.
- `builder/sprites.py` renders about 450 frames of Mario's SM64 animations from a side view turned slightly towards the camera. It supersamples them 4×, then downsamples, quantizes them to a shared 5-bit-per-channel palette and packs them into a sprite sheet. It also writes the animation timing data (`mario_animdata.lemon`) for the scripts.
- `builder/icons.py` draws the HUD lives icon, the "MARIO" results nameplate, the Data Select portrait and the mod icons.
- `builder/audio.py` writes the voice clips as Ogg Vorbis files (through the `soundfile` package, or `ffmpeg` if that's installed instead).
- `mod/scripts/*.lemon` is the script part of the mod:
  - `mario_dataselect.lemon` adds the extra slot. Save slots store character value `5` for Mario.
  - `mario_actions.lemon` is the 2D port of SM64's Mario action code (`mario_actions_*.c`, `mario_step.c`, `mario.c` in the SM64 decompilation): every action with its physics, transitions and animations. Positions and speeds stay in SM64 units and are converted to Sonic 3 pixels with the world scale.
  - `mario_core.lemon` hooks the actions into the Sonic character object (Mario plays Sonic's route). Sonic 3's own collision code moves him, so he works with loops, slopes, springs, water and all level objects.
  - `mario_render.lemon` draws Mario's sprites instead of Sonic's (via `Standalone.drawCharacterSprite`), and also swaps the HUD lives icon and the results nameplate.

The Android app and the web page use a JavaScript port of the builder (`web/js/`), which
produces the same mod:
- `web/index.html` is the page and `web/js/*.js` mirror the Python modules. Ogg Vorbis encoding uses libvorbis compiled to WebAssembly ([wasm-media-encoders](https://github.com/arseneyr/wasm-media-encoders), MIT license, in `web/vendor/`).
- `android/` is a small Java app that shows the page in a WebView and provides the ROM file picker, saving, and the direct install on Android 10 and older.

Release packaging:
- `python make_release.py` packages the Python builder into `dist/`.
- `python make_web.py` bundles the web builder into one offline HTML file.
- `python make_apk.py` builds the APK without Gradle. It needs a JDK and `aapt`, `dx`, `zipalign`, `apksigner` and an `android.jar`. On Debian/Ubuntu: `apt install aapt dalvik-exchange zipalign apksigner android-sdk-platform-23`. It signs with `android/release.keystore`, which is created on the first build.

## Known limitations

- Some non-player graphics still show Sonic: the AIZ intro (Super Sonic), signposts, the
  continue screen, Blue Sphere special stages, and the lives icons inside Data Select slots.
- Mario's sprites are true-color, so they are not tinted by underwater palettes.
- Not available in Competition mode.
- Only the USA version of Super Mario 64 is supported.
