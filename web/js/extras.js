// Mario versions of the other character graphics: signpost, end pose, Blue Sphere,
// continue screen and Tornado (port of builder/extras.py)
//
// Float images here are { width, height, data: Float32Array RGBA (0..1) }.

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.extras = (function()
{
	const BACK_YAW = 188;		// seen from behind (Blue Sphere)
	const FRONT_YAW = 40;		// turned towards the camera
	const RUN = 0x72;
	const IDLE = 0xC5;
	const STAR_DANCE = 0xCD;
	const SPIN = 0x6F;			// forward somersault
	const rnd = x => M64.util.roundHalfEven(x);

	function newImage(w, h)
	{
		return { width: w, height: h, data: new Float32Array(w * h * 4) };
	}

	// Renders a pose; returns the trimmed image and the feet position inside it
	function render(model, anims, anim, frame, opts, pxPerUnit, canvas, anchor)
	{
		canvas = canvas || 96;
		opts = Object.assign({}, opts);
		if (opts.anchor === undefined)
			opts.anchor = (anchor === undefined) ? Math.floor(canvas / 2) - 4 : anchor;
		const r = M64.sprites.renderSprite(model, anims, anim, frame, opts, pxPerUnit, canvas);
		const feet = [r.center[0], r.center[1] + opts.anchor];
		const t = M64.sprites.trim(r.img, feet);
		return { img: t.img, feet: t.center };
	}

	// Puts an image into a fixed-size frame so that the feet end up at the given position
	function place(img, feet, size, center)
	{
		const [w, h] = size;
		const out = newImage(w, h);
		const ox = center[0] - feet[0], oy = center[1] - feet[1];
		for (let y = 0; y < img.height; ++y)
		{
			const ty = oy + y;
			if (ty < 0 || ty >= h)
				continue;
			for (let x = Math.max(0, -ox); x < Math.min(img.width, w - ox); ++x)
				for (let c = 0; c < 4; ++c)
					out.data[(ty * w + ox + x) * 4 + c] = img.data[(y * img.width + x) * 4 + c];
		}
		return out;
	}

	// Frame of the given size with the image centered horizontally, standing on the bottom edge
	function fitBottom(r, size, margin)
	{
		margin = (margin === undefined) ? 1 : margin;
		const [w, h] = size;
		return place(r.img, r.feet, size, [Math.floor(w / 2) + (r.feet[0] - Math.floor(r.img.width / 2)), h - margin - (r.img.height - r.feet[1])]);
	}

	function setPx(img, x, y, c)
	{
		const i = (y * img.width + x) * 4;
		img.data[i] = c[0];
		img.data[i + 1] = c[1];
		img.data[i + 2] = c[2];
		img.data[i + 3] = c[3];
	}

	// Crops Mario's head (top part) out of a full body render (8-bit image), like the lives icon
	function headOnly(body)
	{
		const h = Math.floor(body.height * 0.42);
		let x0 = body.width, y0 = h, x1 = -1, y1 = -1;
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < body.width; ++x)
				if (body.data[(y * body.width + x) * 4 + 3] > 0)
				{
					x0 = Math.min(x0, x); x1 = Math.max(x1, x);
					y0 = Math.min(y0, y); y1 = Math.max(y1, y);
				}
		const out = { width: x1 - x0 + 1, height: y1 - y0 + 1, data: new Uint8Array((x1 - x0 + 1) * (y1 - y0 + 1) * 4) };
		for (let y = y0; y <= y1; ++y)
			out.data.set(body.data.subarray((y * body.width + x0) * 4, (y * body.width + x1 + 1) * 4), (y - y0) * out.width * 4);
		return out;
	}

	// 8-bit image resized with Lanczos -> float image
	function resized(img8, w, h)
	{
		const r = M64.icons.resizeLanczos(img8, w, h);
		const out = newImage(w, h);
		for (let i = 0; i < r.data.length; ++i)
			out.data[i] = r.data[i] / 255;
		return out;
	}

	// 48x32 signpost face: Mario's head on a sky-blue panel with a dark border
	function signpost(head)
	{
		const w = 48, h = 32;
		const out = newImage(w, h);
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < w; ++x)
			{
				const inner = (x >= 2 && x < w - 2 && y >= 2 && y < h - 2);
				setPx(out, x, y, !inner ? [0.10, 0.10, 0.35, 1] : (y < 4) ? [0.70, 0.86, 1, 1] : [0.42, 0.71, 0.99, 1]);
			}
		const scale = Math.min(28 / head.height, 40 / head.width);
		const small = resized(head, Math.max(1, rnd(head.width * scale)), Math.max(1, rnd(head.height * scale)));
		const ox = Math.floor((w - small.width) / 2), oy = h - 2 - small.height;
		for (let y = 0; y < small.height; ++y)
			for (let x = 0; x < small.width; ++x)
			{
				const i = (y * small.width + x) * 4;
				if (small.data[i + 3] >= 0.5)
				{
					const o = ((oy + y) * w + ox + x) * 4;
					out.data[o] = small.data[i];
					out.data[o + 1] = small.data[i + 1];
					out.data[o + 2] = small.data[i + 2];
				}
			}
		return out;
	}

	// Returns an array of { key, img, center }
	function renderExtras(model, anims, body)
	{
		const head = headOnly(body);
		const out = [];
		const add = (key, img, center) => out.push({ key: key, img: img, center: center });

		// Signpost
		add("signpost_mario", signpost(head), [24, 16]);

		// End pose after the credits: Mario's star dance pose, small and big
		const pose = { yaw: FRONT_YAW, pitch: 5, lhand: "open", rhand: "peace" };
		add("endpose_mario_0x00", fitBottom(render(model, anims, STAR_DANCE, 28, pose, 0.42, 96), [48, 72]), [24, 36]);
		add("endpose_mario_0x01", fitBottom(render(model, anims, STAR_DANCE, 28, pose, 0.72, 160, 74), [88, 128]), [44, 64]);

		// Blue Sphere: seen from behind; 0x01 standing, 0x02 - 0x08 running, 0x09 - 0x0b jumping
		const bsScale = 0.30;
		const bsOpts = { yaw: BACK_YAW, pitch: 22 };
		add("bluesphere_mario_0x01", fitBottom(render(model, anims, IDLE, 0, bsOpts, bsScale), [32, 40]), [16, 35]);
		const loopEnd = Math.max(1, anims[RUN].loopEnd);
		for (let i = 0; i < 7; ++i)
			add("bluesphere_mario_0x" + (i + 2).toString(16).padStart(2, "0"),
				fitBottom(render(model, anims, RUN, Math.floor(i * loopEnd / 7), bsOpts, bsScale), [32, 56], 4), [16, 43]);
		const spinEnd = Math.max(1, anims[SPIN].loopEnd);
		for (let i = 0; i < 3; ++i)
		{
			const r = render(model, anims, SPIN, 2 + Math.floor(i * spinEnd / 4), Object.assign({}, bsOpts, { lhand: "open", rhand: "open" }), bsScale * 0.8);
			const frame = newImage(32, 32);
			const oy = Math.max(0, Math.floor((32 - r.img.height) / 2)), ox = Math.max(0, Math.floor((32 - r.img.width) / 2));
			for (let y = 0; y < Math.min(r.img.height, 32); ++y)
				for (let x = 0; x < Math.min(r.img.width, 32); ++x)
				{
					if (oy + y >= 32 || ox + x >= 32)
						continue;
					for (let c = 0; c < 4; ++c)
						frame.data[((oy + y) * 32 + ox + x) * 4 + c] = r.img.data[(y * r.img.width + x) * 4 + c];
				}
			add("bluesphere_mario_0x" + (i + 9).toString(16).padStart(2, "0"), frame, [16, 38]);
		}

		// Continue screen: Mario waiting (two frames), and the small icons
		const idleEnd = Math.max(1, anims[IDLE].loopEnd);
		const front = { yaw: FRONT_YAW, pitch: 5 };
		for (let i = 0; i < 2; ++i)
		{
			const f = Math.floor(i * idleEnd / 2);
			add("character_mario_continue_0x0" + i, fitBottom(render(model, anims, IDLE, f, front, 0.26), [24, 40]), [12, 20]);
			add("continue_icon_mario_wait_0x0" + i, fitBottom(render(model, anims, IDLE, f, front, 0.15), [24, 24]), [12, 12]);
		}
		add("continue_icon_mario", fitBottom(render(model, anims, IDLE, 0, front, 0.15), [20, 24], 0), [12, 24]);

		// Tornado: Mario as pilot (head above the cockpit) and standing on the wings
		for (const [key, size, center] of [["tornado_mario_pilot", [32, 16], [20, 8]], ["tornado_mario_pilot_small", [16, 8], [8, 4]]])
		{
			const [w, h] = size;
			const scale = Math.min(h / (head.height * 0.75), w / head.width);
			const small = resized(head, Math.max(1, rnd(head.width * scale)), Math.max(1, rnd(head.height * scale)));
			const frame = newImage(w, h);
			const ox = Math.max(0, center[0] - Math.floor(small.width / 2));
			for (let y = 0; y < Math.min(small.height, h); ++y)
				for (let x = 0; x < Math.min(small.width, w - ox); ++x)
				{
					const i = (y * small.width + x) * 4, o = (y * w + ox + x) * 4;
					frame.data[o] = small.data[i];
					frame.data[o + 1] = small.data[i + 1];
					frame.data[o + 2] = small.data[i + 2];
					frame.data[o + 3] = (small.data[i + 3] >= 0.5) ? 1 : 0;
				}
			add(key, frame, center);
		}
		add("tornado_mario_small", fitBottom(render(model, anims, IDLE, 0, front, 0.15), [16, 24], 0), [8, 12]);
		return out;
	}

	// Returns [[path, content]] relative to the mod folder (colors snapped to 5 bits per channel)
	async function makeExtras(model, anims, body)
	{
		const sprites = renderExtras(model, anims, body).map(s =>
		{
			const img = newImage(s.img.width, s.img.height);
			for (let i = 0; i < s.img.width * s.img.height; ++i)
			{
				for (let c = 0; c < 3; ++c)
					img.data[i * 4 + c] = rnd(Math.fround(s.img.data[i * 4 + c]) * 31) / 31;
				img.data[i * 4 + 3] = (s.img.data[i * 4 + 3] >= 0.5) ? 1 : 0;
			}
			return { key: s.key, img: img, center: s.center };
		});
		const packed = M64.sprites.pack(sprites, 256);
		return [
			["sprites/mario_extra.png", await M64.util.encodePng(M64.sprites.toBytes(packed.sheet))],
			["sprites/mario_extra.json", M64.sprites.sheetJson(packed.placed, "mario_extra.png")],
		];
	}

	return { makeExtras };
})();
