// Builds the "Mario 64" mod from a Super Mario 64 (USA) ROM (port of build_mario_mod.py)

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.build = (function()
{
	const MOD_FOLDER_NAME = "Mario64";

	// Without voice clips, default the voice setting to off so the game doesn't look for them
	function disableVoices(modJson)
	{
		const marker = '"Variable": "mario.option.voice",';
		const i = modJson.indexOf(marker);
		if (i < 0)
			return modJson;
		const j = modJson.indexOf('"DefaultValue": "1"', i);
		if (j < 0)
			return modJson;
		return modJson.slice(0, j) + '"DefaultValue": "0"' + modJson.slice(j + '"DefaultValue": "1"'.length);
	}

	// romBytes:  Uint8Array with the ROM file contents
	// modFiles:  { "mod.json": text, "scripts/main.lemon": text, ... } (the static part of the mod)
	// options:   { voices: bool, log: function(text), progress: function(stage, done, total) }
	// Returns { zip: Uint8Array, files: [[path, content]], voices: bool }
	async function buildMod(romBytes, modFiles, options)
	{
		options = options || {};
		const log = options.log || (() => {});
		const progress = options.progress || (() => {});

		log("Checking ROM...");
		const rom = await M64.rom.loadRom(romBytes);

		log("Loading Mario's model and animations...");
		const model = new M64.model.Model(M64.rom.marioSegment(rom));
		const anims = M64.rom.loadAnimations(rom);

		log("Rendering sprites...");
		const sprites = await M64.sprites.renderAll(model, anims, (done, total) => progress("sprites", done, total));

		log("Creating icons...");
		const icons = await M64.icons.makeIcons(sprites.head, sprites.portrait);

		let voiceFiles = [];
		let voices = options.voices !== false;
		if (voices)
		{
			const encoder = await M64.audio.createEncoder();
			if (!encoder)
			{
				log("NOTE: Voice clips skipped - no Ogg Vorbis encoder available.");
				voices = false;
			}
			else
			{
				log("Extracting voice clips...");
				voiceFiles = await M64.audio.makeVoices(rom, encoder, (done, total) => progress("voices", done, total));
			}
		}

		const files = [];
		for (const path of Object.keys(modFiles).sort())
		{
			let content = modFiles[path];
			if (path === "mod.json" && !voices)
				content = disableVoices(content);
			files.push([path, content]);
		}
		files.push(...sprites.files, ...icons, ...voiceFiles);
		files.sort((a, b) => (a[0] < b[0]) ? -1 : (a[0] > b[0]) ? 1 : 0);

		log("Packing the mod...");
		const zip = M64.util.makeZip(files.map(([p, c]) => [MOD_FOLDER_NAME + "/" + p, c]));
		return { zip: zip, files: files, voices: voices };
	}

	return { MOD_FOLDER_NAME, buildMod };
})();
