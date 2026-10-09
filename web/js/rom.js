// Access to the data inside a Super Mario 64 (USA) ROM (port of builder/rom.py)

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.rom = (function()
{
	const SM64_US_SHA1 = "9bef1128717f958171a4afac3ed78ee2bb4e86ce";

	const MARIO_SEGMENT_MIO0 = 0x114750;		// Segment 0x04: Mario's model data (MIO0 compressed)
	const MARIO_ANIMS_TABLE = 0x4EC000;			// Mario's animation table (uncompressed)

	class RomError extends Error {}

	function normalizeRom(data)
	{
		const h = data.subarray(0, 4);
		if (h[0] === 0x80 && h[1] === 0x37 && h[2] === 0x12 && h[3] === 0x40)
			return data;
		const out = new Uint8Array(data.length);
		if (h[0] === 0x37 && h[1] === 0x80 && h[2] === 0x40 && h[3] === 0x12)
		{
			// .v64: byte swapped
			for (let i = 0; i + 1 < data.length; i += 2)
			{
				out[i] = data[i + 1];
				out[i + 1] = data[i];
			}
			return out;
		}
		if (h[0] === 0x40 && h[1] === 0x12 && h[2] === 0x37 && h[3] === 0x80)
		{
			// .n64: little endian
			for (let i = 0; i + 3 < data.length; i += 4)
			{
				out[i] = data[i + 3];
				out[i + 1] = data[i + 2];
				out[i + 2] = data[i + 1];
				out[i + 3] = data[i];
			}
			return out;
		}
		throw new RomError("This file does not look like a Nintendo 64 ROM.");
	}

	// ROMs are often kept in .zip files: use the N64 ROM inside
	async function unpackArchive(bytes)
	{
		const b = bytes;
		if (b[0] === 0x37 && b[1] === 0x7A && b[2] === 0xBC && b[3] === 0xAF)
			throw new RomError("This is a .7z archive. Please extract the ROM from it first (e.g. with ZArchiver or 7-Zip), then choose the .z64 file.");
		if (b[0] === 0x52 && b[1] === 0x61 && b[2] === 0x72 && b[3] === 0x21)
			throw new RomError("This is a .rar archive. Please extract the ROM from it first (e.g. with ZArchiver or 7-Zip), then choose the .z64 file.");
		if (!(b[0] === 0x50 && b[1] === 0x4B && b[2] === 0x03 && b[3] === 0x04))
			return bytes;

		// Find the central directory
		const view = new DataView(b.buffer, b.byteOffset, b.byteLength);
		let eocd = -1;
		for (let i = b.length - 22; i >= Math.max(0, b.length - 65557); --i)
		{
			if (view.getUint32(i, true) === 0x06054b50)
			{
				eocd = i;
				break;
			}
		}
		if (eocd < 0)
			throw new RomError("This .zip file seems to be damaged.");
		const count = view.getUint16(eocd + 10, true);
		let o = view.getUint32(eocd + 16, true);
		let best = null;
		for (let n = 0; n < count; ++n)
		{
			if (view.getUint32(o, true) !== 0x02014b50)
				break;
			const method = view.getUint16(o + 10, true);
			const compSize = view.getUint32(o + 20, true);
			const size = view.getUint32(o + 24, true);
			const nameLen = view.getUint16(o + 28, true), extraLen = view.getUint16(o + 30, true), commentLen = view.getUint16(o + 32, true);
			const localOffset = view.getUint32(o + 42, true);
			const name = new TextDecoder().decode(b.subarray(o + 46, o + 46 + nameLen));
			const isRom = /\.(z64|n64|v64|rom|bin)$/i.test(name);
			if (size >= 0x400000 && (!best || (isRom && !best.isRom) || (isRom === best.isRom && size > best.size)))
				best = { name, method, compSize, size, localOffset, isRom };
			o += 46 + nameLen + extraLen + commentLen;
		}
		if (!best)
			throw new RomError("No N64 ROM found inside this .zip file.");

		const lo = best.localOffset;
		const start = lo + 30 + view.getUint16(lo + 26, true) + view.getUint16(lo + 28, true);
		const comp = b.subarray(start, start + best.compSize);
		if (best.method === 0)
			return comp.slice();
		if (best.method !== 8 || typeof DecompressionStream === "undefined")
			throw new RomError("Can't unpack this .zip file in this browser. Please extract the ROM from it first, then choose the .z64 file.");
		const stream = new Blob([comp]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
		return new Uint8Array(await new Response(stream).arrayBuffer());
	}

	async function loadRom(bytes)
	{
		const data = normalizeRom(await unpackArchive(bytes));
		const sha1 = await M64.util.sha1(data);
		if (sha1 !== SM64_US_SHA1)
		{
			const name = String.fromCharCode(...data.subarray(0x20, 0x34)).trim();
			const region = data.length > 0x3E ? String.fromCharCode(data[0x3E]) : "?";
			const regions = { E: "USA", P: "Europe", J: "Japan", U: "Australia" };
			let hint = "Please use an unmodified Super Mario 64 (USA) ROM.";
			if (name.toUpperCase().indexOf("MARIO 64") >= 0 && region !== "E")
				hint = "This is the " + (regions[region] || region) + " version of Super Mario 64, but only the USA version is supported.";
			else if (name.toUpperCase().indexOf("MARIO 64") >= 0)
				hint = "This USA ROM is modified (e.g. a hack, patch or bad dump). Please use an unmodified one.";
			throw new RomError(hint + "\n(ROM: '" + name + "', region '" + region + "', SHA-1 " + sha1 + ")");
		}
		return data;
	}

	function u32(data, o)
	{
		return ((data[o] << 24) | (data[o + 1] << 16) | (data[o + 2] << 8) | data[o + 3]) >>> 0;
	}

	function u16(data, o)
	{
		return (data[o] << 8) | data[o + 1];
	}

	function s16(data, o)
	{
		const v = u16(data, o);
		return (v >= 0x8000) ? v - 0x10000 : v;
	}

	function mio0Decompress(data, offset)
	{
		if (String.fromCharCode(...data.subarray(offset, offset + 4)) !== "MIO0")
			throw new RomError("No MIO0 block at 0x" + offset.toString(16));
		const destSize = u32(data, offset + 4);
		let comp = offset + u32(data, offset + 8);
		let uncomp = offset + u32(data, offset + 12);
		let layout = offset + 16;
		const out = new Uint8Array(destSize);
		let pos = 0;
		let bitIdx = 0;
		let cur = 0;
		while (pos < destSize)
		{
			if (bitIdx === 0)
			{
				cur = u32(data, layout);
				layout += 4;
				bitIdx = 32;
			}
			--bitIdx;
			if ((cur >>> bitIdx) & 1)
			{
				out[pos++] = data[uncomp++];
			}
			else
			{
				const v = u16(data, comp);
				comp += 2;
				const length = (v >> 12) + 3;
				const start = pos - ((v & 0xFFF) + 1);
				for (let i = 0; i < length && pos < destSize; ++i)
					out[pos++] = out[start + i];
			}
		}
		return out;
	}

	// RGBA16 texture -> Float32Array RGBA (0..1)
	function decodeRgba16(raw, offset, w, h)
	{
		const out = new Float32Array(w * h * 4);
		for (let i = 0; i < w * h; ++i)
		{
			const px = u16(raw, offset + i * 2);
			out[i * 4]     = Math.floor(((px >> 11) & 0x1F) * 255 / 31) / 255;
			out[i * 4 + 1] = Math.floor(((px >> 6) & 0x1F) * 255 / 31) / 255;
			out[i * 4 + 2] = Math.floor(((px >> 1) & 0x1F) * 255 / 31) / 255;
			out[i * 4 + 3] = (px & 1);
		}
		return { width: w, height: h, data: out };
	}

	function marioSegment(rom)
	{
		return mio0Decompress(rom, MARIO_SEGMENT_MIO0);
	}

	// Animation index -> animation (same layout as SM64's struct Animation)
	function loadAnimations(rom)
	{
		const count = u32(rom, MARIO_ANIMS_TABLE);
		const anims = {};
		for (let i = 0; i < count; ++i)
		{
			const off = u32(rom, MARIO_ANIMS_TABLE + 8 + i * 8);
			const base = MARIO_ANIMS_TABLE + off;
			const flags = u16(rom, base);
			const ydiv = s16(rom, base + 2);
			const start = s16(rom, base + 4);
			const loopStart = s16(rom, base + 6);
			const loopEnd = s16(rom, base + 8);
			const valuesOff = u32(rom, base + 12);
			const indexOff = u32(rom, base + 16);
			const length = u32(rom, base + 20);
			const numIndex = (valuesOff - indexOff) >> 1;
			const index = new Int32Array(numIndex);
			for (let k = 0; k < numIndex; ++k)
				index[k] = u16(rom, base + indexOff + k * 2);
			const numValues = (length - valuesOff) >> 1;
			const values = new Int32Array(numValues);
			for (let k = 0; k < numValues; ++k)
				values[k] = s16(rom, base + valuesOff + k * 2);
			anims[i] = { flags: flags, ydiv: ydiv, start: start, loopStart: loopStart, loopEnd: loopEnd, values: values, index: index };
		}
		return anims;
	}

	// ----------------------------------------------------------------------
	// Voice samples (VADPCM in the sound sample table)
	// ----------------------------------------------------------------------

	// name -> [ROM offset of the ADPCM data, size in bytes, ROM offset of the codebook]
	const VOICE_SAMPLES = {
		"mario_hoo":      [6323856, 1881, 5764528],
		"mario_wah":      [6325744, 2052, 5764656],
		"mario_yah":      [6327808, 2691, 5764784],
		"mario_haha":     [6330512, 6912, 5764912],
		"mario_yahoo":    [6337424, 8523, 5765040],
		"mario_uh":       [6345952, 2808, 5765168],
		"mario_whoa":     [6355952, 8334, 5765552],
		"mario_attacked": [6370736, 5643, 5765808],
		"mario_ooof":     [6376384, 5544, 5765936],
		"mario_herewego": [6381936, 12807, 5766064],
		"mario_doh":      [6420768, 5139, 5766576],
		"mario_waha":     [6580640, 9693, 5767600],
		"mario_yippee":   [6590336, 9018, 5767728],
		"mario_waaaooow": [6651552, 24768, 5770320],
		"mario_hoohoo":   [6676320, 5598, 5770448],
		"mario_mammamia": [6687168, 15786, 5770704],
		"mario_punchyah": [6742976, 2205, 5771344],
		"mario_punchhoo": [6745184, 5724, 5771472],
	};
	const VOICE_SAMPLE_RATE = 16000;

	// Expand an order 2 / 2 predictor codebook into 8x10 predictor tables (as in N64 aifc decoders)
	function vadpcmTables(book)
	{
		const order = 2, npred = 2;
		const tables = [];
		for (let p = 0; p < npred; ++p)
		{
			const t = [];
			for (let k = 0; k < 8; ++k)
				t.push(new Array(order + 8).fill(0));
			for (let j = 0; j < order; ++j)
				for (let k = 0; k < 8; ++k)
					t[k][j] = book[p * 16 + j * 8 + k];
			for (let k = 1; k < 8; ++k)
				t[k][order] = t[k - 1][order - 1];
			t[0][order] = 1 << 11;
			for (let k = 1; k < 8; ++k)
				for (let j = 0; j < 8; ++j)
					t[j][k + order] = (j < k) ? 0 : t[j - k][order];
			tables.push(t);
		}
		return tables;
	}

	function decodeVadpcm(data, book)
	{
		const tables = vadpcmTables(book);
		const order = 2;
		const state = new Array(16).fill(0);
		const nframes = Math.floor(data.length / 9);
		const out = new Int16Array(nframes * 16);
		const ix = new Array(16);
		const inVec = new Array(16);
		for (let f = 0; f < nframes; ++f)
		{
			const header = data[f * 9];
			const scale = 1 << (header >> 4);
			const table = tables[header & 0x0F];
			for (let b = 0; b < 8; ++b)
			{
				const byte = data[f * 9 + 1 + b];
				const hi = byte >> 4, lo = byte & 0x0F;
				ix[b * 2] = (hi >= 8 ? hi - 16 : hi) * scale;
				ix[b * 2 + 1] = (lo >= 8 ? lo - 16 : lo) * scale;
			}
			for (let j = 0; j < 2; ++j)
			{
				inVec.fill(0);
				for (let i = 0; i < order; ++i)
					inVec[i] = (j === 0) ? state[16 - order + i] : state[8 - order + i];
				for (let i = 0; i < 8; ++i)
				{
					const ind = j * 8 + i;
					inVec[order + i] = ix[ind];
					let acc = 0;
					for (let k = 0; k < order + i; ++k)
						acc += table[i][k] * inVec[k];
					state[ind] = Math.floor(acc / 2048) + ix[ind];
				}
			}
			for (let i = 0; i < 16; ++i)
				out[f * 16 + i] = Math.max(-32768, Math.min(32767, state[i]));
		}
		return out;
	}

	function loadVoice(rom, name)
	{
		const [dataOff, sizeIn, bookOff] = VOICE_SAMPLES[name];
		const view = new DataView(rom.buffer, rom.byteOffset, rom.byteLength);
		const order = view.getInt32(bookOff), npred = view.getInt32(bookOff + 4);
		if (order !== 2 || npred !== 2)
			throw new RomError("Unexpected codebook for " + name);
		const book = [];
		for (let i = 0; i < 32; ++i)
			book.push(view.getInt16(bookOff + 8 + i * 2));
		const size = sizeIn - sizeIn % 9;
		return decodeVadpcm(rom.subarray(dataOff, dataOff + size), book);
	}

	return { RomError, loadRom, marioSegment, loadAnimations, decodeRgba16, u32, u16, s16,
	         VOICE_SAMPLES, VOICE_SAMPLE_RATE, loadVoice };
})();
