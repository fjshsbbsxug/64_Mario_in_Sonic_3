// Mario 64 for Sonic 3 A.I.R. - mod builder (JavaScript version)
// Helpers: SHA-1, CRC-32, PNG and ZIP writing

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.util = (function()
{
	function sha1Fallback(bytes)
	{
		const len = bytes.length;
		const words = new Uint32Array((((len + 8) >> 6) + 1) * 16);
		for (let i = 0; i < len; ++i)
			words[i >> 2] |= bytes[i] << (24 - (i & 3) * 8);
		words[len >> 2] |= 0x80 << (24 - (len & 3) * 8);
		words[words.length - 1] = len * 8;
		words[words.length - 2] = Math.floor(len / 0x20000000);
		let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE, h3 = 0x10325476, h4 = 0xC3D2E1F0;
		const w = new Int32Array(80);
		for (let b = 0; b < words.length; b += 16)
		{
			for (let i = 0; i < 16; ++i)
				w[i] = words[b + i];
			for (let i = 16; i < 80; ++i)
			{
				const x = w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16];
				w[i] = (x << 1) | (x >>> 31);
			}
			let a = h0, bb = h1, c = h2, d = h3, e = h4;
			for (let i = 0; i < 80; ++i)
			{
				let f, k;
				if (i < 20)      { f = (bb & c) | (~bb & d); k = 0x5A827999; }
				else if (i < 40) { f = bb ^ c ^ d; k = 0x6ED9EBA1; }
				else if (i < 60) { f = (bb & c) | (bb & d) | (c & d); k = 0x8F1BBCDC; }
				else             { f = bb ^ c ^ d; k = 0xCA62C1D6; }
				const t = (((a << 5) | (a >>> 27)) + f + e + k + w[i]) | 0;
				e = d; d = c; c = (bb << 30) | (bb >>> 2); bb = a; a = t;
			}
			h0 = (h0 + a) | 0; h1 = (h1 + bb) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0; h4 = (h4 + e) | 0;
		}
		return [h0, h1, h2, h3, h4].map(v => (v >>> 0).toString(16).padStart(8, "0")).join("");
	}

	async function sha1(bytes)
	{
		try
		{
			if (globalThis.crypto && crypto.subtle)
			{
				const digest = new Uint8Array(await crypto.subtle.digest("SHA-1", bytes));
				return Array.from(digest, b => b.toString(16).padStart(2, "0")).join("");
			}
		}
		catch (e) {}
		return sha1Fallback(bytes);
	}

	const CRC_TABLE = (function()
	{
		const t = new Int32Array(256);
		for (let n = 0; n < 256; ++n)
		{
			let c = n;
			for (let k = 0; k < 8; ++k)
				c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
			t[n] = c;
		}
		return t;
	})();

	function crc32(bytes, crc)
	{
		crc = (crc === undefined) ? -1 : ~crc;
		for (let i = 0; i < bytes.length; ++i)
			crc = CRC_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
		return ~crc >>> 0;
	}

	function adler32(bytes)
	{
		let a = 1, b = 0;
		for (let i = 0; i < bytes.length; ++i)
		{
			a = (a + bytes[i]) % 65521;
			b = (b + a) % 65521;
		}
		return ((b << 16) | a) >>> 0;
	}

	function concat(chunks)
	{
		let size = 0;
		for (const c of chunks)
			size += c.length;
		const out = new Uint8Array(size);
		let o = 0;
		for (const c of chunks)
		{
			out.set(c, o);
			o += c.length;
		}
		return out;
	}

	// zlib stream, compressed if the platform supports it, otherwise with stored blocks
	async function zlibCompress(data)
	{
		if (typeof CompressionStream !== "undefined")
		{
			try
			{
				const stream = new Blob([data]).stream().pipeThrough(new CompressionStream("deflate"));
				return new Uint8Array(await new Response(stream).arrayBuffer());
			}
			catch (e) {}
		}
		const chunks = [new Uint8Array([0x78, 0x01])];
		for (let o = 0; o < data.length || o === 0; o += 65535)
		{
			const block = data.subarray(o, Math.min(o + 65535, data.length));
			const last = (o + 65535 >= data.length) ? 1 : 0;
			const n = block.length;
			chunks.push(new Uint8Array([last, n & 0xFF, n >> 8, ~n & 0xFF, (~n >> 8) & 0xFF]), block);
			if (last)
				break;
		}
		const a = adler32(data);
		chunks.push(new Uint8Array([a >>> 24, (a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF]));
		return concat(chunks);
	}

	function u32be(v)
	{
		return new Uint8Array([v >>> 24, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF]);
	}

	function pngChunk(type, data)
	{
		const typeBytes = new TextEncoder().encode(type);
		const crc = crc32(data, crc32(typeBytes));
		return concat([u32be(data.length), typeBytes, data, u32be(crc)]);
	}

	// image: { width, height, data: Uint8Array RGBA }
	async function encodePng(image)
	{
		const w = image.width, h = image.height;
		const raw = new Uint8Array((w * 4 + 1) * h);
		for (let y = 0; y < h; ++y)
			raw.set(image.data.subarray(y * w * 4, (y + 1) * w * 4), y * (w * 4 + 1) + 1);
		const ihdr = concat([u32be(w), u32be(h), new Uint8Array([8, 6, 0, 0, 0])]);
		return concat([
			new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
			pngChunk("IHDR", ihdr),
			pngChunk("IDAT", await zlibCompress(raw)),
			pngChunk("IEND", new Uint8Array(0))]);
	}

	// ZIP archive with stored (uncompressed) entries. files: array of [path, Uint8Array or string]
	function makeZip(files)
	{
		const enc = new TextEncoder();
		const local = [];
		const central = [];
		let offset = 0;
		const now = new Date();
		const dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
		const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
		for (const [path, content] of files)
		{
			const data = (typeof content === "string") ? enc.encode(content) : content;
			const name = enc.encode(path);
			const crc = crc32(data);
			const header = new DataView(new ArrayBuffer(30));
			header.setUint32(0, 0x04034b50, true);
			header.setUint16(4, 20, true);
			header.setUint16(6, 0x0800, true);		// UTF-8 names
			header.setUint16(8, 0, true);
			header.setUint16(10, dosTime, true);
			header.setUint16(12, dosDate, true);
			header.setUint32(14, crc, true);
			header.setUint32(18, data.length, true);
			header.setUint32(22, data.length, true);
			header.setUint16(26, name.length, true);
			header.setUint16(28, 0, true);
			local.push(new Uint8Array(header.buffer), name, data);

			const cd = new DataView(new ArrayBuffer(46));
			cd.setUint32(0, 0x02014b50, true);
			cd.setUint16(4, 20, true);
			cd.setUint16(6, 20, true);
			cd.setUint16(8, 0x0800, true);
			cd.setUint16(10, 0, true);
			cd.setUint16(12, dosTime, true);
			cd.setUint16(14, dosDate, true);
			cd.setUint32(16, crc, true);
			cd.setUint32(20, data.length, true);
			cd.setUint32(24, data.length, true);
			cd.setUint16(28, name.length, true);
			cd.setUint32(42, offset, true);
			central.push(new Uint8Array(cd.buffer), name);
			offset += 30 + name.length + data.length;
		}
		let cdSize = 0;
		for (const c of central)
			cdSize += c.length;
		const end = new DataView(new ArrayBuffer(22));
		end.setUint32(0, 0x06054b50, true);
		end.setUint16(8, files.length, true);
		end.setUint16(10, files.length, true);
		end.setUint32(12, cdSize, true);
		end.setUint32(16, offset, true);
		return concat(local.concat(central, [new Uint8Array(end.buffer)]));
	}

	// Python-style round (half to even)
	function roundHalfEven(x)
	{
		const r = Math.round(x);
		return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r;
	}

	function yieldToUI()
	{
		return new Promise(resolve => setTimeout(resolve, 0));
	}

	return { sha1, crc32, concat, encodePng, makeZip, roundHalfEven, yieldToUI };
})();
