// HUD lives icon, results screen nameplate, Data Select portrait and mod icons (port of builder/icons.py)
//
// Images here are 8-bit: { width, height, data: Uint8Array RGBA }.

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.icons = (function()
{
	function newImage(w, h)
	{
		return { width: w, height: h, data: new Uint8Array(w * h * 4) };
	}

	function getPx(img, x, y)
	{
		const i = (y * img.width + x) * 4;
		return [img.data[i], img.data[i + 1], img.data[i + 2], img.data[i + 3]];
	}

	function setPx(img, x, y, c)
	{
		const i = (y * img.width + x) * 4;
		img.data[i] = c[0];
		img.data[i + 1] = c[1];
		img.data[i + 2] = c[2];
		img.data[i + 3] = c[3];
	}

	function cropImage(img, x0, y0, x1, y1)
	{
		const out = newImage(x1 - x0, y1 - y0);
		for (let y = y0; y < y1; ++y)
			for (let x = x0; x < x1; ++x)
				if (x >= 0 && y >= 0 && x < img.width && y < img.height)
					setPx(out, x - x0, y - y0, getPx(img, x, y));
		return out;
	}

	// Bounding box of the non-transparent pixels: [x0, y0, x1, y1]
	function alphaBBox(img)
	{
		let x0 = img.width, y0 = img.height, x1 = 0, y1 = 0;
		for (let y = 0; y < img.height; ++y)
			for (let x = 0; x < img.width; ++x)
				if (img.data[(y * img.width + x) * 4 + 3])
				{
					x0 = Math.min(x0, x);
					y0 = Math.min(y0, y);
					x1 = Math.max(x1, x + 1);
					y1 = Math.max(y1, y + 1);
				}
		return (x1 > x0) ? [x0, y0, x1, y1] : [0, 0, img.width, img.height];
	}

	// Lanczos (a = 3) resize with premultiplied alpha
	function resizeLanczos(img, dw, dh)
	{
		const lanczos = x =>
		{
			if (x === 0)
				return 1;
			if (x <= -3 || x >= 3)
				return 0;
			const px = Math.PI * x;
			return 3 * Math.sin(px) * Math.sin(px / 3) / (px * px);
		};
		const resample1D = (src, sw, sh, outW, horizontal) =>
		{
			// src: Float64Array premultiplied RGBA (sw x sh); resample along one axis
			const inLen = horizontal ? sw : sh;
			const outLen = outW;
			const scale = inLen / outLen;
			const support = 3 * Math.max(scale, 1);
			const filterScale = Math.max(scale, 1);
			const ow = horizontal ? outLen : sw, oh = horizontal ? sh : outLen;
			const out = new Float64Array(ow * oh * 4);
			for (let o = 0; o < outLen; ++o)
			{
				const center = (o + 0.5) * scale;
				const lo = Math.max(0, Math.floor(center - support));
				const hi = Math.min(inLen, Math.ceil(center + support));
				const weights = [];
				let wsum = 0;
				for (let i = lo; i < hi; ++i)
				{
					const w = lanczos((i + 0.5 - center) / filterScale);
					weights.push(w);
					wsum += w;
				}
				const lines = horizontal ? sh : sw;
				for (let l = 0; l < lines; ++l)
				{
					const acc = [0, 0, 0, 0];
					for (let i = lo; i < hi; ++i)
					{
						const w = weights[i - lo] / wsum;
						const si = horizontal ? (l * sw + i) * 4 : (i * sw + l) * 4;
						for (let c = 0; c < 4; ++c)
							acc[c] += src[si + c] * w;
					}
					const di = horizontal ? (l * ow + o) * 4 : (o * ow + l) * 4;
					for (let c = 0; c < 4; ++c)
						out[di + c] = acc[c];
				}
			}
			return out;
		};

		const pre = new Float64Array(img.data.length);
		for (let i = 0; i < img.width * img.height; ++i)
		{
			const a = img.data[i * 4 + 3] / 255;
			pre[i * 4] = img.data[i * 4] * a;
			pre[i * 4 + 1] = img.data[i * 4 + 1] * a;
			pre[i * 4 + 2] = img.data[i * 4 + 2] * a;
			pre[i * 4 + 3] = img.data[i * 4 + 3];
		}
		const horiz = resample1D(pre, img.width, img.height, dw, true);
		const both = resample1D(horiz, dw, img.height, dh, false);
		const out = newImage(dw, dh);
		for (let i = 0; i < dw * dh; ++i)
		{
			const a = Math.min(Math.max(both[i * 4 + 3], 0), 255);
			for (let c = 0; c < 3; ++c)
				out.data[i * 4 + c] = (a > 0) ? Math.round(Math.min(Math.max(both[i * 4 + c] / (a / 255), 0), 255)) : 0;
			out.data[i * 4 + 3] = Math.round(a);
		}
		return out;
	}

	function resizeNearest(img, dw, dh)
	{
		const out = newImage(dw, dh);
		for (let y = 0; y < dh; ++y)
			for (let x = 0; x < dw; ++x)
			{
				const sx = Math.min(Math.floor((x + 0.5) * img.width / dw), img.width - 1);
				const sy = Math.min(Math.floor((y + 0.5) * img.height / dh), img.height - 1);
				setPx(out, x, y, getPx(img, sx, sy));
			}
		return out;
	}

	// Draws the non-transparent pixels of src onto dst at (ox, oy)
	function paste(dst, src, ox, oy)
	{
		for (let y = 0; y < src.height; ++y)
			for (let x = 0; x < src.width; ++x)
			{
				const p = getPx(src, x, y);
				if (p[3] > 0 && x + ox >= 0 && y + oy >= 0 && x + ox < dst.width && y + oy < dst.height)
					setPx(dst, x + ox, y + oy, p);
			}
	}

	// ----------------------------------------------------------------------
	// Lives icon: 16x16 head portrait + "MARIO" + small "x" (48x16 like the originals)
	// ----------------------------------------------------------------------

	const HUD_FONT = {
		M: ["10001", "11011", "10101", "10001", "10001", "10001"],
		A: ["0110", "1001", "1001", "1111", "1001", "1001"],
		R: ["1110", "1001", "1001", "1110", "1010", "1001"],
		I: ["11", "11", "11", "11", "11", "11"],
		O: ["0110", "1001", "1001", "1001", "1001", "0110"],
		x: ["101", "010", "101"],
	};

	const HUD_YELLOW = [252, 252, 0, 255];
	const HUD_WHITE = [252, 252, 252, 255];
	const HUD_SHADOW = [72, 72, 108, 255];
	const HUD_FRAME = [36, 36, 36, 255];

	function hudGlyph(rows, colors)
	{
		const h = rows.length, w = rows[0].length;
		const out = newImage(w + 1, h + 1);
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < w; ++x)
				if (rows[y][x] === "1")
					setPx(out, x, y, colors(y));
		for (let y = 0; y <= h; ++y)
			for (let x = 0; x <= w; ++x)
				if (getPx(out, x, y)[3] === 0)
				{
					const left = x > 0 && y < h && rows[y][x - 1] === "1";
					const up = y > 0 && x < w && rows[y - 1][x] === "1";
					if (left || up)
						setPx(out, x, y, HUD_SHADOW);
				}
		return out;
	}

	function makeLivesIcon(head)
	{
		const icon = newImage(48, 16);

		// Portrait: white background framed by dark lines at top and bottom
		for (let x = 0; x < 16; ++x)
		{
			setPx(icon, x, 0, HUD_FRAME);
			setPx(icon, x, 15, HUD_FRAME);
			for (let y = 1; y < 15; ++y)
				setPx(icon, x, y, HUD_WHITE);
		}
		let hb = cropImage(head, 0, 0, head.width, Math.floor(head.height * 0.40));
		const bb = alphaBBox(hb);
		hb = cropImage(hb, bb[0], bb[1], bb[2], bb[3]);
		const scale = Math.min(16.0 / hb.width, 14.0 / hb.height);
		const rnd = M64.util.roundHalfEven;
		const hs = resizeLanczos(hb, Math.max(1, rnd(hb.width * scale)), Math.max(1, rnd(hb.height * scale)));
		const oy = 1 + 14 - hs.height, ox = Math.floor((16 - hs.width) / 2);
		const headOnly = newImage(16, 14);
		for (let y = 0; y < hs.height; ++y)
			for (let x = 0; x < hs.width; ++x)
			{
				const p = getPx(hs, x, y);
				const tx = ox + x, ty = oy - 1 + y;
				if (p[3] >= 128 && tx >= 0 && ty >= 0 && tx < 16 && ty < 14)
					setPx(headOnly, tx, ty, [p[0], p[1], p[2], 255]);
			}
		paste(icon, headOnly, 0, 1);

		// "MARIO"
		const letters = "MARIO".split("").map(c => hudGlyph(HUD_FONT[c], y => (y === 2 || y === 3) ? HUD_WHITE : HUD_YELLOW));
		let x = 17 + Math.max(0, Math.floor((31 - letters.reduce((s, g) => s + g.width, 0)) / 2));
		for (const g of letters)
		{
			paste(icon, g, x, 1);
			x += g.width;
		}

		// "x"
		paste(icon, hudGlyph(HUD_FONT.x, () => HUD_WHITE), 22, 10);
		return { lives: icon, headSmall: headOnly };
	}

	// ----------------------------------------------------------------------
	// Results screen nameplate ("MARIO GOT THROUGH")
	// ----------------------------------------------------------------------

	const PLATE_FONT = {
		M: ["1111.....1111",
		    "11111...11111",
		    "111111.111111",
		    "1111111111111",
		    "1111.111.1111",
		    "1111..1..1111",
		    "1111.....1111",
		    "1111.....1111",
		    "1111.....1111",
		    "1111.....1111",
		    "1111.....1111",
		    "1111.....1111"],
		A: ["...111111...",
		    "..11111111..",
		    ".1111..1111.",
		    "1111....1111",
		    "1111....1111",
		    "111111111111",
		    "111111111111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111"],
		R: ["111111111...",
		    "1111111111..",
		    "1111...1111.",
		    "1111....1111",
		    "1111...1111.",
		    "1111111111..",
		    "111111111...",
		    "1111..1111..",
		    "1111...1111.",
		    "1111...1111.",
		    "1111....1111",
		    "1111....1111"],
		I: new Array(12).fill("1111"),
		O: ["...111111...",
		    ".1111111111.",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    "1111....1111",
		    ".1111111111.",
		    "...111111..."],
	};

	const PLATE_BODY = [36, 72, 216, 255];
	const PLATE_LIGHT = [108, 108, 252, 255];
	const PLATE_DARK = [36, 36, 144, 255];
	const PLATE_OUTLINE = [252, 180, 0, 255];
	const PLATE_OUTER = [252, 144, 0, 255];

	function makeNameplate(text)
	{
		text = text || "MARIO";
		const gap = 3;
		const widths = text.split("").map(c => PLATE_FONT[c][0].length);
		const w = widths.reduce((s, v) => s + v, 0) + gap * (text.length - 1) + 4;
		const h = 16;
		const body = (x, y) => x >= 0 && y >= 0 && x < w && y < h && bodyMask[y * w + x];
		const bodyMask = new Uint8Array(w * h);
		let x = 2;
		text.split("").forEach((c, n) =>
		{
			PLATE_FONT[c].forEach((row, y) =>
			{
				for (let i = 0; i < row.length; ++i)
					if (row[i] === "1")
						bodyMask[(2 + y) * w + x + i] = 1;
			});
			x += widths[n] + gap;
		});

		const img = newImage(w, h);
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < w; ++x)
			{
				// shifted(a, dy, dx)[y][x] == a[y - dy][x - dx]
				const sh = (dy, dx) => body(x - dx, y - dy);
				if (body(x, y))
				{
					const light = !sh(1, 0) || !sh(0, 1);		// top / left edges
					const dark = !sh(-1, 0) || !sh(0, -1);		// bottom / right edges
					setPx(img, x, y, light ? PLATE_LIGHT : dark ? PLATE_DARK : PLATE_BODY);
				}
				else
				{
					const ortho = sh(1, 0) || sh(-1, 0) || sh(0, 1) || sh(0, -1);
					const diag = sh(1, 1) || sh(-1, -1) || sh(1, -1) || sh(-1, 1);
					if (ortho)
						setPx(img, x, y, PLATE_OUTLINE);
					else if (diag)
						setPx(img, x, y, PLATE_OUTER);
				}
			}
		return img;
	}

	// ----------------------------------------------------------------------

	// Returns [[path, content]] relative to the mod folder
	async function makeIcons(head, portrait)
	{
		const png = M64.util.encodePng;
		const { lives, headSmall } = makeLivesIcon(head);
		const plate = makeNameplate();
		const files = [
			["sprites/hud_mario.png", await png(lives)],
			["sprites/hud_mario.json", '{\n\t"hud_lives_icon_mario": { "File": "hud_mario.png", "Rect": "0,0,48,16" }\n}\n'],
			["sprites/result_mario.png", await png(plate)],
			["sprites/result_mario.json", '{\n\t"result_nameplate_mario": { "File": "result_mario.png", "Rect": "0,0,' + plate.width + ',16", "Center": "-1,0" }\n}\n'],
			// Data Select portrait, anchored at the bottom center
			["sprites/dataselect_mario.png", await png(portrait)],
			["sprites/dataselect_mario.json", '{\n\t"mario_dataselect": { "File": "dataselect_mario.png", "Rect": "0,0,' + portrait.width + "," + portrait.height +
				'", "Center": "' + (Math.floor(portrait.width / 2) + 2) + "," + portrait.height + '" }\n}\n'],
		];

		// Mod icons
		const icon = newImage(64, 64);
		const s = 64 / Math.max(portrait.width, portrait.height);
		const p2 = resizeNearest(portrait, Math.floor(portrait.width * s), Math.floor(portrait.height * s));
		paste(icon, p2, Math.floor((64 - p2.width) / 2), 64 - p2.height);
		const iconPng = await png(icon);
		files.push(["icon.png", iconPng], ["icon-64px.png", iconPng]);
		const icon16 = newImage(16, 16);
		paste(icon16, headSmall, 0, 1);
		files.push(["icon-16px.png", await png(icon16)]);
		return files;
	}

	return { makeIcons, makeLivesIcon, makeNameplate, resizeLanczos };
})();
