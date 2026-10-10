// Renders Mario's in-game sprite sheet for the Sonic 3 A.I.R. mod (port of builder/sprites.py)
//
// Images here are { width, height, data: Float32Array RGBA (0..1) }.

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.sprites = (function()
{
	const SS = 4;					// supersampling factor
	const CANVAS = 64;				// sprite canvas size before trimming
	const PX_PER_UNIT = 0.255;		// Mario ends up ~38 px tall, like Sonic
	const YAW = 62;					// mostly side view, slightly turned towards the camera
	const PITCH = 8;
	const LIGHT = [0.45, 0.75, 0.65];

	// Distance from the character's center to the floor, in pixels.
	// Mario always uses the upright hitbox, which has 19 px below the center.
	const UPRIGHT = 19;

	// SM64 animations used by the mod: [animation id, render every n-th frame, options]
	// Sprite keys are "mario_<anim id hex>_<index>", sprite i shows SM64 frame i * step.
	const OPEN = { lhand: "open", rhand: "open" };
	const ANIMS = [
		[0xC3, 5, {}], [0xC4, 5, {}], [0xC5, 5, {}],          // idle (head left / right / center)
		[0x48, 5, {}], [0x72, 5, {}],                         // walking, running
		[0xCA, 5, {}], [0x92, 10, {}],                        // start tiptoe, tiptoe
		[0x0F, 1, {}], [0x10, 3, {}],                         // skid, stop skid
		[0xBC, 1, {}], [0xBD, 3, {}],                         // turning around part 1 / 2
		[0x97, 2, {}], [0x98, 15, {}], [0x96, 2, {}],         // start crouching, crouching, stop crouching
		[0x9B, 2, {}], [0x99, 8, {}], [0x9A, 2, {}],          // start crawling, crawling, stop crawling
		[0x4D, 2, OPEN], [0x4E, 4, {}],                       // single jump, landing
		[0x50, 2, OPEN], [0x4C, 3, OPEN], [0x4B, 3, {}],      // double jump rise / fall, landing
		[0xC1, 3, {}], [0xC0, 4, {}],                         // triple jump, landing
		[0x04, 3, {}],                                        // backflip
		[0xBF, 3, OPEN], [0xBE, 2, {}],                       // side flip, landing
		[0x13, 3, {}], [0x14, 3, {}], [0x11, 3, {}], [0x12, 3, {}],  // long jump fast / slow, landings
		[0x56, 1, OPEN], [0x57, 4, {}],                       // general fall, general land
		[0x88, 4, OPEN], [0x5A, 4, OPEN],                     // dive, slow land from dive
		[0x6F, 2, {}],                                        // forward spinning (rollout)
		[0x8C, 2, {}], [0x8D, 3, {}], [0x53, 5, OPEN],        // slide kick, crouch from slide kick, fall from slide kick
		[0xCB, 3, OPEN], [0xCC, 1, OPEN],                     // wall kick, start wall kick
		[0x4F, 3, {}],                                        // air kick
		[0x67, 1, {}], [0x69, 2, {}], [0x68, 1, {}], [0x6A, 3, {}], [0x66, 3, {}],  // punches, ground kick
		[0x3C, 2, {}], [0x3D, 2, {}], [0x3A, 2, {}],          // ground pound start / fall / landing
		[0x91, 2, OPEN], [0x8F, 4, OPEN], [0x90, 3, OPEN],    // butt slide, stop slide, fall from slide
		[0x6C, 3, {}],                                        // pushing
		[0x02, 1, OPEN], [0x7B, 5, OPEN], [0x8A, 5, OPEN],    // backward air knockback, backward ground knockback, ground bonk
		[0xCD, 6, { rhand: "open" }],                         // star dance (act clear)
		[0x35, 9, OPEN], [0x0D, 28, OPEN], [0x94, 1, OPEN],   // hang on ceiling, idle on pole, twirl
		[0x2B, 10, OPEN], [0x2D, 1, OPEN], [0x58, 5, OPEN],   // hanging on owl (carried), air forward kb, being grabbed
		[0xAA, 3, OPEN], [0xAB, 2, OPEN], [0xAC, 4, OPEN], [0xB2, 5, OPEN], [0xAD, 5, OPEN],  // swimming
		[0xB0, 1, OPEN], [0xAF, 3, OPEN],                     // water punch
	];

	// Extra sprite sets with ids that don't exist in SM64: [id, anim id, frames, options]
	const EXTRA = [
		[0xE0, 0x02, [4], { eyes: "dead", lhand: "open", rhand: "open", yaw: 8 }],      // death
		[0xE1, 0xA5, [20], { eyes: "dead", lhand: "open", rhand: "open", yaw: 20 }],    // drowned
		[0xE2, 0xC5, [10], { eyes: "closed" }],                                          // idle blink
		[0xE3, 0x02, [4], { eyes: "half", lhand: "open", rhand: "open" }],              // hurt
	];

	// ICZ 1 snowboarding: Mario on a snowboard, one sprite for each of Sonic's snowboarding frames
	// ("mario_sb_<frame>"). Board angle (degrees, clockwise) and board center relative to the
	// sprite center follow Sonic's frames, so Mario lines up with the game's animation.
	// Mario leans with the board by "lean" (0..1). In the trick frames he isn't standing on the
	// board, so his feet position is given instead.
	//   [frame, board angle, board x, board y, SM64 animation, lean, feet position or null]
	const SNOWBOARD = [
		[0x01, 47, 1, 2, 0x4A, 0.4, null],          // trick frames (in the air)
		[0x02, 85, -1, 14, 0x4A, 0.0, [0, 15]],
		[0x03, -48, -2, 11, 0x4A, 0.0, [-3, 10]],
		[0x04, -53, -1, 15, 0x4A, 0.0, [2, 12]],
		[0x05, 59, 0, 12, 0x4A, 0.0, [0, 12]],
		[0x06, 0, -3, 12, 0x47, 1.0, null],         // riding
		[0x07, -6, -1, 12, 0x47, 1.0, null],
		[0x08, -11, -2, 11, 0x47, 1.0, null],
		[0x09, 62, -9, 5, 0x47, 0.4, null],         // steep slopes
		[0x0A, 38, -6, 6, 0x47, 0.6, null],
		[0x0B, 8, -2, 10, 0x47, 1.0, null],
		[0x0C, 22, -2, 9, 0x47, 1.0, null],
	];
	// AIZ 1 hollow tree: Mario running around the trunk, seen from 8 directions ("mario_tree_<dir>_<frame>").
	// Direction 0 runs to the right, 2 away from the camera, 4 to the left, 6 towards the camera.
	const TREE_DIRECTIONS = 8;
	const TREE_FRAMES = 4;
	const TREE_ANIM = 0x72;		// running

	function treeSpriteJobs(anims)
	{
		const loopEnd = Math.max(1, anims[TREE_ANIM].loopEnd);
		const jobs = [];
		for (let d = 0; d < TREE_DIRECTIONS; ++d)
			for (let f = 0; f < TREE_FRAMES; ++f)
				jobs.push(["mario_tree_" + d + "_" + f, TREE_ANIM, Math.floor(f * loopEnd / TREE_FRAMES), { yaw: YAW + 45 + d * 45 }]);
		return jobs;
	}

	// Twirling (HCZ fans, updrafts and the like): Mario's twirl pose turning around ("mario_twirl_<n>")
	const TWIRL_FRAMES = 8;
	const TWIRL_ANIM = 0x94;

	function twirlSpriteJobs()
	{
		const jobs = [];
		for (let i = 0; i < TWIRL_FRAMES; ++i)
			jobs.push(["mario_twirl_" + i, TWIRL_ANIM, 0, Object.assign({}, OPEN, { yaw: YAW + Math.floor(i * 360 / TWIRL_FRAMES) })]);
		return jobs;
	}

	const SNOWBOARD_CANVAS = 96;
	const BOARD_LENGTH = 46;
	const BOARD_THICKNESS = 4;
	const BOARD_COLORS = [[248, 96, 72], [200, 24, 24], [40, 24, 56]];		// top, bottom, outline

	// Draws the snowboard (a red capsule) into a supersampled image, behind what's there
	function drawBoard(hi, cx, cy, angleDeg, ss)
	{
		const a = angleDeg * Math.PI / 180;
		const ux = Math.cos(a), uy = Math.sin(a);
		const nx = Math.sin(a), ny = -Math.cos(a);		// board's "up"
		const half = BOARD_LENGTH / 2 - BOARD_THICKNESS / 2;
		const colors = BOARD_COLORS.map(c => c.map(v => Math.fround(v / 255)));
		for (let y = 0; y < hi.height; ++y)
			for (let x = 0; x < hi.width; ++x)
			{
				const i = (y * hi.width + x) * 4;
				if (hi.data[i + 3] !== 0)
					continue;
				const px = (x + 0.5) / ss - cx, py = (y + 0.5) / ss - cy;
				const along = px * ux + py * uy;
				const across = px * nx + py * ny;
				const dist = Math.hypot(Math.max(Math.abs(along) - half, 0), across);
				if (dist > BOARD_THICKNESS / 2)
					continue;
				const col = (dist > BOARD_THICKNESS / 2 - 1) ? colors[2] : (across > 0) ? colors[0] : colors[1];
				hi.data[i] = col[0];
				hi.data[i + 1] = col[1];
				hi.data[i + 2] = col[2];
				hi.data[i + 3] = 1;
			}
	}

	function renderSnowboard(model, anims, def)
	{
		const [, angle, bx, by, animId, lean, feetPos] = def;
		const mats = M64.model.poseMatrices(anims[animId], 0);
		const soup = M64.model.buildSoup(model, mats, "front", "open", "open");
		const view = M64.model.viewMatrix(YAW, PITCH, -angle * lean);
		const c = Math.floor(SNOWBOARD_CANVAS / 2);
		const a = angle * Math.PI / 180;
		const board = [c + bx, c + by];
		const feet = feetPos ? [c + feetPos[0], c + feetPos[1]] :
			[board[0] + Math.sin(a) * BOARD_THICKNESS / 2, board[1] - Math.cos(a) * BOARD_THICKNESS / 2];
		const hi = M64.model.render(soup, view, [SNOWBOARD_CANVAS, SNOWBOARD_CANVAS], PX_PER_UNIT, feet, LIGHT, SS);
		drawBoard(hi, board[0], board[1], angle, SS);
		return { img: downsample(hi, SS), center: [c, c] };
	}

	function animSpriteFrames(anim, step)
	{
		const frames = [];
		for (let f = 0; f < M64.model.animNumFrames(anim); f += step)
			frames.push(f);
		return frames;
	}

	function downsample(img, ss)
	{
		const w = img.width / ss, h = img.height / ss;
		const out = new Float32Array(w * h * 4);
		const n = ss * ss;
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < w; ++x)
			{
				let asum = 0, r = 0, g = 0, b = 0;
				for (let dy = 0; dy < ss; ++dy)
					for (let dx = 0; dx < ss; ++dx)
					{
						const i = ((y * ss + dy) * img.width + x * ss + dx) * 4;
						const a = img.data[i + 3];
						asum += a;
						r += img.data[i] * a;
						g += img.data[i + 1] * a;
						b += img.data[i + 2] * a;
					}
				const wsum = Math.max(asum, 1e-6);
				const o = (y * w + x) * 4;
				out[o] = r / wsum;
				out[o + 1] = g / wsum;
				out[o + 2] = b / wsum;
				out[o + 3] = (asum / n >= 0.45) ? 1 : 0;
			}

		// Darken the silhouette edge a bit, like hand-drawn Genesis sprites
		const opaque = (x, y) => x >= 0 && y >= 0 && x < w && y < h && out[(y * w + x) * 4 + 3] > 0;
		const edge = [];
		for (let y = 0; y < h; ++y)
			for (let x = 0; x < w; ++x)
				if (opaque(x, y) && !(opaque(x, y - 1) && opaque(x, y + 1) && opaque(x - 1, y) && opaque(x + 1, y)))
					edge.push((y * w + x) * 4);
		for (const o of edge)
		{
			out[o] *= 0.72;
			out[o + 1] *= 0.72;
			out[o + 2] *= 0.72;
		}
		return { width: w, height: h, data: out };
	}

	function renderSprite(model, anims, animId, frame, opts, pxPerUnit, canvas)
	{
		pxPerUnit = pxPerUnit || PX_PER_UNIT;
		canvas = canvas || CANVAS;
		const anim = anims[animId];
		const mats = M64.model.poseMatrices(anim, frame);
		const soup = M64.model.buildSoup(model, mats, opts.eyes, opts.lhand, opts.rhand);
		const view = M64.model.viewMatrix(opts.yaw !== undefined ? opts.yaw : YAW, opts.pitch !== undefined ? opts.pitch : PITCH);
		const anchor = (opts.anchor !== undefined) ? opts.anchor : UPRIGHT;
		const center = Math.floor(canvas / 2);
		const hi = M64.model.render(soup, view, [canvas, canvas], pxPerUnit, [center, center + anchor], LIGHT, SS);
		return { img: downsample(hi, SS), center: [center, center] };
	}

	// Median cut quantization over the color histogram
	function medianCut(hist, ncolors)
	{
		// hist: array of [r, g, b, count]
		let boxes = [hist];
		const total = box => box.reduce((s, c) => s + c[3], 0);
		while (boxes.length < ncolors)
		{
			// Split the box with the most pixels that still has more than one color
			let best = -1, bestCount = -1;
			for (let i = 0; i < boxes.length; ++i)
			{
				if (boxes[i].length < 2)
					continue;
				const t = total(boxes[i]);
				if (t > bestCount)
				{
					bestCount = t;
					best = i;
				}
			}
			if (best < 0)
				break;
			const box = boxes[best];
			let axis = 0, bestRange = -1;
			for (let a = 0; a < 3; ++a)
			{
				let lo = 255, hi = 0;
				for (const c of box)
				{
					lo = Math.min(lo, c[a]);
					hi = Math.max(hi, c[a]);
				}
				if (hi - lo > bestRange)
				{
					bestRange = hi - lo;
					axis = a;
				}
			}
			box.sort((p, q) => p[axis] - q[axis]);
			const half = bestCount / 2;
			let acc = 0, cut = 1;
			for (let i = 0; i < box.length - 1; ++i)
			{
				acc += box[i][3];
				cut = i + 1;
				if (acc >= half)
					break;
			}
			boxes.splice(best, 1, box.slice(0, cut), box.slice(cut));
		}
		return boxes.map(box =>
		{
			let r = 0, g = 0, b = 0, n = 0;
			for (const c of box)
			{
				r += c[0] * c[3];
				g += c[1] * c[3];
				b += c[2] * c[3];
				n += c[3];
			}
			return [Math.round(r / n), Math.round(g / n), Math.round(b / n)];
		});
	}

	// Shared palette for all sprites, so the sheet looks consistent
	function buildPalette(images, ncolors)
	{
		const counts = new Map();
		for (const im of images)
			for (let i = 0; i < im.width * im.height; ++i)
			{
				if (im.data[i * 4 + 3] <= 0)
					continue;
				const r = Math.floor(im.data[i * 4] * 255), g = Math.floor(im.data[i * 4 + 1] * 255), b = Math.floor(im.data[i * 4 + 2] * 255);
				const key = (r << 16) | (g << 8) | b;
				counts.set(key, (counts.get(key) || 0) + 1);
			}
		const hist = [];
		for (const [key, n] of counts)
			hist.push([(key >> 16) & 0xFF, (key >> 8) & 0xFF, key & 0xFF, n]);
		// Snap to the 5 bits per channel that S3AIR supports
		return medianCut(hist, ncolors).map(c => c.map(v => Math.round(Math.fround(v / 255) * 31) / 31));
	}

	function applyPalette(img, pal)
	{
		const out = new Float32Array(img.data.length);
		const n = img.width * img.height;
		const palF = pal.map(c => c.map(v => Math.fround(v)));
		for (let i = 0; i < n; ++i)
		{
			const r = img.data[i * 4], g = img.data[i * 4 + 1], b = img.data[i * 4 + 2];
			let best = 0, bestD = Infinity;
			for (let p = 0; p < palF.length; ++p)
			{
				const dr = r - palF[p][0], dg = g - palF[p][1], db = b - palF[p][2];
				const d = dr * dr + dg * dg + db * db;
				if (d < bestD)
				{
					bestD = d;
					best = p;
				}
			}
			out[i * 4] = palF[best][0];
			out[i * 4 + 1] = palF[best][1];
			out[i * 4 + 2] = palF[best][2];
			out[i * 4 + 3] = img.data[i * 4 + 3];
		}
		return { width: img.width, height: img.height, data: out };
	}

	function crop(img, x0, y0, w, h)
	{
		const out = new Float32Array(w * h * 4);
		for (let y = 0; y < h; ++y)
			out.set(img.data.subarray(((y0 + y) * img.width + x0) * 4, ((y0 + y) * img.width + x0 + w) * 4), y * w * 4);
		return { width: w, height: h, data: out };
	}

	function trim(img, center)
	{
		let x0 = Infinity, y0 = Infinity, x1 = -1, y1 = -1;
		for (let y = 0; y < img.height; ++y)
			for (let x = 0; x < img.width; ++x)
				if (img.data[(y * img.width + x) * 4 + 3] > 0)
				{
					x0 = Math.min(x0, x);
					x1 = Math.max(x1, x);
					y0 = Math.min(y0, y);
					y1 = Math.max(y1, y);
				}
		if (x1 < 0)
			return { img: crop(img, 0, 0, 1, 1), center: [0, 0] };
		return { img: crop(img, x0, y0, x1 - x0 + 1, y1 - y0 + 1), center: [center[0] - x0, center[1] - y0] };
	}

	// Simple shelf packer. sprites: array of { key, img, center }
	function pack(sprites, sheetWidth, pad)
	{
		pad = (pad === undefined) ? 2 : pad;
		let x = pad, y = pad, shelf = 0;
		const placed = [];
		for (const s of sprites)
		{
			const w = s.img.width, h = s.img.height;
			if (x + w + pad > sheetWidth)
			{
				x = pad;
				y += shelf + pad;
				shelf = 0;
			}
			placed.push({ key: s.key, x: x, y: y, img: s.img, center: s.center });
			x += w + pad;
			shelf = Math.max(shelf, h);
		}
		const height = y + shelf + pad;
		const sheet = { width: sheetWidth, height: height, data: new Float32Array(sheetWidth * height * 4) };
		for (const p of placed)
			for (let row = 0; row < p.img.height; ++row)
				sheet.data.set(p.img.data.subarray(row * p.img.width * 4, (row + 1) * p.img.width * 4), ((p.y + row) * sheetWidth + p.x) * 4);
		return { sheet: sheet, placed: placed };
	}

	// Float image -> 8-bit RGBA image
	function toBytes(img)
	{
		const out = new Uint8Array(img.data.length);
		for (let i = 0; i < img.data.length; ++i)
			out[i] = Math.round(Math.min(Math.max(img.data[i], 0), 1) * 255);
		return { width: img.width, height: img.height, data: out };
	}

	function sheetJson(placed, fname)
	{
		const lines = placed.map(p => '\t"' + p.key + '": { "File": "' + fname + '", "Rect": "' + p.x + "," + p.y + "," + p.img.width + "," + p.img.height +
			'", "Center": "' + p.center[0] + "," + p.center[1] + '" }');
		return "{\n" + lines.join(",\n") + "\n}\n";
	}

	function hex2(v)
	{
		return v.toString(16).padStart(2, "0");
	}

	// Renders the sprite sheet and writes the animation data script.
	// Returns { files: [[path, content]], head, portrait } (head and portrait are 8-bit images for the icons).
	async function renderAll(model, anims, progress)
	{
		const jobs = [];
		for (const [aid, step, opts] of ANIMS)
			animSpriteFrames(anims[aid], step).forEach((f, i) => jobs.push(["mario_" + hex2(aid) + "_" + i, aid, f, opts]));
		for (const [xid, aid, frames, opts] of EXTRA)
			frames.forEach((f, i) => jobs.push(["mario_" + hex2(xid) + "_" + i, aid, f, opts]));
		jobs.push(...treeSpriteJobs(anims));
		jobs.push(...twirlSpriteJobs());

		const rendered = [];
		for (const [key, aid, f, opts] of jobs)
		{
			const r = renderSprite(model, anims, aid, f, opts);
			rendered.push({ key: key, img: r.img, center: r.center });
			if (progress && (rendered.length % 4 === 0 || rendered.length === jobs.length))
			{
				progress(rendered.length, jobs.length);
				await M64.util.yieldToUI();
			}
		}

		for (const def of SNOWBOARD)
		{
			const r = renderSnowboard(model, anims, def);
			rendered.push({ key: "mario_sb_" + hex2(def[0]), img: r.img, center: r.center });
		}

		const head = renderSprite(model, anims, 0xC5, 0, { yaw: 35, pitch: 5, anchor: 40 }, 0.36, 96).img;
		const portrait = renderSprite(model, anims, 0xC5, 0, { yaw: 40, pitch: 5 }, 0.255).img;

		const pal = buildPalette(rendered.map(r => r.img), 26);
		const final = rendered.map(r =>
		{
			const t = trim(applyPalette(r.img, pal), r.center);
			return { key: r.key, img: t.img, center: t.center };
		});
		const packed = pack(final, 1024);
		const files = [
			["sprites/character_mario.png", await M64.util.encodePng(toBytes(packed.sheet))],
			["sprites/character_mario.json", sheetJson(packed.placed, "character_mario.png")],
			["scripts/mario_animdata.lemon", animScript(anims)],
		];
		const toImage = img => toBytes(trim(applyPalette(img, pal), [0, 0]).img);
		return { files: files, head: toImage(head), portrait: toImage(portrait) };
	}

	// Lemon script with the SM64 animation timing data, indexed by animation id
	function animScript(anims)
	{
		const step = new Array(256).fill(0);
		const count = new Array(256).fill(0);
		const start = new Array(256).fill(0);
		const loopStart = new Array(256).fill(0);
		const loopEnd = new Array(256).fill(1);
		const noloop = new Array(256).fill(1);
		for (const [aid, st] of ANIMS)
		{
			const a = anims[aid];
			step[aid] = st;
			count[aid] = animSpriteFrames(a, st).length;
			start[aid] = Math.max(0, a.start);
			loopStart[aid] = Math.max(0, a.loopStart);
			loopEnd[aid] = Math.max(1, a.loopEnd);
			noloop[aid] = (a.flags & 0x01) ? 1 : 0;
		}
		for (const [xid, , frames] of EXTRA)
		{
			step[xid] = 1;
			count[xid] = frames.length;
		}

		const arr = (name, typ, values) =>
		{
			const rows = [];
			for (let i = 0; i < 256; i += 16)
				rows.push("\t" + values.slice(i, i + 16).join(", "));
			return "constant array<" + typ + "> " + name + " =\n{\n" + rows.join(",\n") + "\n}\n";
		};

		return "// Generated by the mod builder from the Super Mario 64 ROM - do not edit\n" +
			"// Timing data of Mario's animations, indexed by SM64 animation id\n\n" +
			arr("MarioAnim.SPRITE_STEP", "u8", step) + "\n" +
			arr("MarioAnim.SPRITE_COUNT", "u8", count) + "\n" +
			arr("MarioAnim.START", "u16", start) + "\n" +
			arr("MarioAnim.LOOP_START", "u16", loopStart) + "\n" +
			arr("MarioAnim.LOOP_END", "u16", loopEnd) + "\n" +
			arr("MarioAnim.NO_LOOP", "u8", noloop);
	}

	return { ANIMS, EXTRA, renderAll, renderSprite, toBytes, trim, pack, sheetJson };
})();
