// Mario's voice clips: decoded from the ROM and written as Ogg Vorbis files (port of builder/audio.py)
//
// Encoding uses libvorbis compiled to WebAssembly (the "wasm-media-encoders" package, see vendor/).

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.audio = (function()
{
	const OUTPUT_RATE = 48000;

	// Linear interpolation, like numpy.interp
	function resample(samples, rateIn, rateOut)
	{
		const nOut = M64.util.roundHalfEven(samples.length * rateOut / rateIn);
		const out = new Float32Array(nOut);
		for (let i = 0; i < nOut; ++i)
		{
			const pos = i * rateIn / rateOut;
			const i0 = Math.floor(pos);
			if (i0 >= samples.length - 1)
			{
				out[i] = samples[samples.length - 1];
				continue;
			}
			const f = pos - i0;
			out[i] = samples[i0] * (1 - f) + samples[i0 + 1] * f;
		}
		return out;
	}

	function base64ToBytes(b64)
	{
		if (typeof atob === "function")
		{
			const s = atob(b64);
			const out = new Uint8Array(s.length);
			for (let i = 0; i < s.length; ++i)
				out[i] = s.charCodeAt(i);
			return out;
		}
		return new Uint8Array(Buffer.from(b64, "base64"));
	}

	// Returns an encoder function (Float32Array pcm at OUTPUT_RATE, -32768..32767) -> Promise<Uint8Array ogg>, or null
	async function createEncoder()
	{
		const lib = globalThis.WasmMediaEncoder;
		const wasm = globalThis.M64_OGG_WASM_BASE64;
		if (!lib || !wasm || typeof WebAssembly === "undefined")
			return null;
		let encoder;
		try
		{
			encoder = await lib.createEncoder("audio/ogg", base64ToBytes(wasm));
		}
		catch (e)
		{
			console.log("Ogg encoder not available: " + e);
			return null;
		}
		return async function(pcm)
		{
			encoder.configure({ sampleRate: OUTPUT_RATE, channels: 1, vbrQuality: 5, oggSerialNo: 0x4D363421 });
			const input = new Float32Array(pcm.length);
			for (let i = 0; i < pcm.length; ++i)
				input[i] = pcm[i] / 32768.0;
			const chunks = [];
			const blockSize = 4096;
			for (let o = 0; o < input.length; o += blockSize)
				chunks.push(encoder.encode([input.subarray(o, Math.min(o + blockSize, input.length))]).slice());
			chunks.push(encoder.finalize().slice());
			return M64.util.concat(chunks);
		};
	}

	// Returns [[path, content]] relative to the mod folder
	async function makeVoices(rom, encoder, progress)
	{
		const names = Object.keys(M64.rom.VOICE_SAMPLES).sort();
		const files = [];
		for (let i = 0; i < names.length; ++i)
		{
			const pcm = M64.rom.loadVoice(rom, names[i]);
			const resampled = resample(pcm, M64.rom.VOICE_SAMPLE_RATE, OUTPUT_RATE);
			files.push(["audio/" + names[i] + ".ogg", await encoder(resampled)]);
			if (progress)
				progress(i + 1, names.length);
			await M64.util.yieldToUI();
		}
		files.push(["audio/audio_replacements.json",
			"{\n" + names.map(n => '\t"' + n + '": { "File": "' + n + '.ogg", "Type": "Sound" }').join(",\n") + "\n}\n"]);
		return files;
	}

	return { createEncoder, makeVoices };
})();
