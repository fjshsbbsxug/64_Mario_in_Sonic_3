// Mario's model straight from the ROM, and a small software renderer for it (port of builder/model.py)
//
// The model is described by F3D display lists in segment 0x04. This interprets the subset
// of F3D commands that Mario's model uses and turns it into a triangle list, which then
// gets rasterized with simple N64-like lighting.
// Matrices are 4x4 row-major arrays with SM64's row-vector convention (v' = v * M).

"use strict";
var M64 = globalThis.M64 || (globalThis.M64 = {});

M64.model = (function()
{
	// Segment 0x04 addresses of the display lists of Mario's high-poly model parts
	const DL = {
		butt: 0x0400CC98,
		torso: 0x04010370,
		eyes_front: 0x040119A0,
		eyes_half: 0x04011A90,
		eyes_closed: 0x04011B80,
		eyes_dead: 0x04012030,
		left_arm: 0x0400D1D8,
		left_forearm: 0x0400D2F8,
		left_hand_fist: 0x0400D8F0,
		left_hand_open: 0x04019CA0,
		right_arm: 0x0400DDE8,
		right_forearm: 0x0400DF08,
		right_hand_fist: 0x0400E458,
		right_hand_open: 0x0401A428,
		right_hand_peace: 0x0401BF30,
		left_thigh: 0x0400E7B0,
		left_leg: 0x0400E918,
		left_foot: 0x0400ECA0,
		right_thigh: 0x0400EFB8,
		right_leg: 0x0400F1D8,
		right_foot: 0x0400F4E8,
	};

	// Skeleton of the regular Mario model (mario_geo_body): parent, translation, part.
	// The order matches the animation channels.
	const SKELETON = [
		[-1, [0, 0, 0], null],                 // 0 root
		[0, [0, 0, 0], "butt"],                // 1
		[1, [68, 0, 0], "torso"],              // 2
		[2, [87, 0, 0], "@eyes"],              // 3 head
		[2, [67, -10, 79], null],              // 4 left shoulder
		[4, [0, 0, 0], "left_arm"],            // 5
		[5, [65, 0, 0], "left_forearm"],       // 6
		[6, [60, 0, 0], "@left_hand"],         // 7
		[2, [68, -10, -79], null],             // 8 right shoulder
		[8, [0, 0, 0], "right_arm"],           // 9
		[9, [65, 0, 0], "right_forearm"],      // 10
		[10, [60, 0, 0], "@right_hand"],       // 11
		[1, [13, -8, 42], null],               // 12 left hip
		[12, [0, 0, 0], "left_thigh"],         // 13
		[13, [89, 0, 0], "left_leg"],          // 14
		[14, [67, 0, 0], "left_foot"],         // 15
		[1, [13, -8, -42], null],              // 16 right hip
		[16, [0, 0, 0], "right_thigh"],        // 17
		[17, [89, 0, 0], "right_leg"],         // 18
		[18, [67, 0, 0], "right_foot"],        // 19
	];

	const G_CULL_BACK = 0x00002000;

	// ----------------------------------------------------------------------
	// Matrices
	// ----------------------------------------------------------------------

	function matMul(a, b)
	{
		const n = Math.round(Math.sqrt(a.length));
		const out = new Float64Array(n * n);
		for (let r = 0; r < n; ++r)
			for (let c = 0; c < n; ++c)
			{
				let s = 0;
				for (let k = 0; k < n; ++k)
					s += a[r * n + k] * b[k * n + c];
				out[r * n + c] = s;
			}
		return out;
	}

	function sins(a) { return Math.sin(a * Math.PI / 32768.0); }
	function coss(a) { return Math.cos(a * Math.PI / 32768.0); }

	function mtxRotateXYZTranslate(t, r)
	{
		const sx = sins(r[0]), cx = coss(r[0]);
		const sy = sins(r[1]), cy = coss(r[1]);
		const sz = sins(r[2]), cz = coss(r[2]);
		return Float64Array.of(
			cy * cz, cy * sz, -sy, 0,
			sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy, 0,
			cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy, 0,
			t[0], t[1], t[2], 1);
	}

	// ----------------------------------------------------------------------
	// Animation
	// ----------------------------------------------------------------------

	function animNumFrames(anim)
	{
		return Math.max(1, anim.loopEnd);
	}

	function animValue(anim, channel, frame)
	{
		const count = anim.index[channel * 2];
		const off = anim.index[channel * 2 + 1];
		return anim.values[off + Math.min(frame, count - 1)];
	}

	// World matrices of all skeleton nodes
	function poseMatrices(anim, frame)
	{
		const flags = anim.flags;
		let ch = 0;
		const mats = [];
		for (let i = 0; i < SKELETON.length; ++i)
		{
			const [parent, trans] = SKELETON[i];
			const t = trans.slice();
			if (i === 0)
			{
				// Root translation: keep only the vertical part, the sprite stays centered horizontally
				const mult = anim.ydiv ? 189.0 / anim.ydiv : 1.0;
				if (!(flags & 0x10) && !(flags & 0x40))
					t[1] += animValue(anim, ch + 1, frame) * mult;
				ch += 3;
			}
			const r = [animValue(anim, ch, frame), animValue(anim, ch + 1, frame), animValue(anim, ch + 2, frame)];
			ch += 3;
			const local = mtxRotateXYZTranslate(t, r);
			mats.push(parent < 0 ? local : matMul(local, mats[parent]));
		}
		return mats;
	}

	// ----------------------------------------------------------------------
	// Display list interpreter
	// ----------------------------------------------------------------------

	class Model
	{
		constructor(segment)
		{
			this.seg = segment;
			this.textures = new Map();
		}

		u32(addr)
		{
			return M64.rom.u32(this.seg, addr & 0x00FFFFFF);
		}

		texture(addr, w, h)
		{
			const key = addr + ":" + w + ":" + h;
			if (!this.textures.has(key))
				this.textures.set(key, M64.rom.decodeRgba16(this.seg, addr & 0x00FFFFFF, w, h));
			return this.textures.get(key);
		}
	}

	// Cycle 1 RGB inputs of G_SETCOMBINE: [a, b, c, d]
	function combiner(w0, w1)
	{
		return [(w0 >>> 20) & 0xF, (w1 >>> 28) & 0xF, (w0 >>> 15) & 0x1F, (w1 >>> 15) & 0x7];
	}

	function runDL(model, addr, matrix, state, soup)
	{
		const seg = model.seg;
		let pc = addr;
		while (true)
		{
			const o = pc & 0x00FFFFFF;
			const w0 = M64.rom.u32(seg, o);
			const w1 = M64.rom.u32(seg, o + 4);
			pc += 8;
			const op = w0 >>> 24;
			if (op === 0x06)					// G_DL
			{
				if ((w0 >>> 16) & 0xFF)
					pc = w1;					// branch
				else
					runDL(model, w1, matrix, state, soup);
			}
			else if (op === 0xB8)				// G_ENDDL
			{
				return;
			}
			else if (op === 0x03)				// G_MOVEMEM (lights)
			{
				const idx = (w0 >>> 16) & 0xFF;
				const lo = w1 & 0x00FFFFFF;
				const col = [seg[lo] / 255, seg[lo + 1] / 255, seg[lo + 2] / 255];
				if (idx === 0x86)
					state.diffuse = col;
				else if (idx === 0x88)
					state.ambient = col;
			}
			else if (op === 0xFC)				// G_SETCOMBINE
			{
				state.combine = combiner(w0, w1);
			}
			else if (op === 0xBB)				// G_TEXTURE
			{
				state.texOn = (w0 & 0xFF) !== 0;
			}
			else if (op === 0xFD)				// G_SETTIMG
			{
				state.teximg = w1;
			}
			else if (op === 0xF2)				// G_SETTILESIZE
			{
				if (((w1 >>> 24) & 0x7) === 0)
					state.texsize = [(((w1 >>> 12) & 0xFFF) >> 2) + 1, ((w1 & 0xFFF) >> 2) + 1];
			}
			else if (op === 0xB7)				// G_SETGEOMETRYMODE
			{
				if (w1 & G_CULL_BACK)
					state.cull = true;
			}
			else if (op === 0xB6)				// G_CLEARGEOMETRYMODE
			{
				if (w1 & G_CULL_BACK)
					state.cull = false;
			}
			else if (op === 0x04)				// G_VTX
			{
				const n = ((w0 >>> 20) & 0xF) + 1;
				const v0 = (w0 >>> 16) & 0xF;
				const vo = w1 & 0x00FFFFFF;
				const view = new DataView(seg.buffer, seg.byteOffset, seg.byteLength);
				for (let k = 0; k < n; ++k)
				{
					const b = vo + k * 16;
					const x = view.getInt16(b), y = view.getInt16(b + 2), z = view.getInt16(b + 4);
					const s = view.getInt16(b + 8), t = view.getInt16(b + 10);
					const nx = view.getInt8(b + 12), ny = view.getInt8(b + 13), nz = view.getInt8(b + 14);
					const p = [0, 0, 0];
					const nn = [0, 0, 0];
					for (let c = 0; c < 3; ++c)
					{
						p[c] = x * matrix[c] + y * matrix[4 + c] + z * matrix[8 + c] + matrix[12 + c];
						nn[c] = nx * matrix[c] + ny * matrix[4 + c] + nz * matrix[8 + c];
					}
					const len = Math.max(Math.sqrt(nn[0] * nn[0] + nn[1] * nn[1] + nn[2] * nn[2]), 1e-6);
					state.vbuf[v0 + k] = { p: p, n: [nn[0] / len, nn[1] / len, nn[2] / len], uv: [s / 32.0, t / 32.0] };
				}
			}
			else if (op === 0xBF)				// G_TRI1
			{
				const ids = [Math.floor(((w1 >>> 16) & 0xFF) / 10), Math.floor(((w1 >>> 8) & 0xFF) / 10), Math.floor((w1 & 0xFF) / 10)];
				const verts = ids.map(i => state.vbuf[i]);
				let tex = null;
				if (state.texOn && state.teximg)
				{
					const [w, h] = state.texsize || [32, 32];
					tex = model.texture(state.teximg, w, h);
				}
				soup.push({
					pos: verts.map(v => v.p),
					nrm: verts.map(v => v.n),
					uv: verts.map(v => v.uv),
					ambient: state.ambient,
					diffuse: state.diffuse,
					combine: state.combine || [15, 15, 31, 4],
					tex: tex,
					cull: (state.cull === undefined) ? true : state.cull,
				});
			}
			// Everything else (syncs, tiles, render modes...) doesn't matter here
		}
	}

	function buildSoup(model, mats, eyes, lhand, rhand)
	{
		const soup = [];
		const state = { ambient: [0.5, 0.5, 0.5], diffuse: [1.0, 1.0, 1.0], vbuf: new Array(16).fill(null), cull: true };
		const scale = Float64Array.of(0.25, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 1);		// GEO_SCALE in mario_geo
		for (let i = 0; i < SKELETON.length; ++i)
		{
			let part = SKELETON[i][2];
			if (part === null)
				continue;
			if (part === "@eyes")
				part = "eyes_" + (eyes || "front");
			else if (part === "@left_hand")
				part = "left_hand_" + (lhand || "fist");
			else if (part === "@right_hand")
				part = "right_hand_" + (rhand || "fist");
			runDL(model, DL[part], matMul(mats[i], scale), state, soup);
		}
		return soup;
	}

	// ----------------------------------------------------------------------
	// Rasterizer
	// ----------------------------------------------------------------------

	// Color combiner input codes: 0 = zero, 1 = one, 2 = shade, 3 = texel rgb, 4 = texel alpha
	function ccInput(sel, kind)
	{
		if (sel === 1)
			return 3;
		if (sel === 4)
			return 2;
		if (sel === 3 || sel === 5)		// primitive / environment color: white for Mario
			return 1;
		if (kind === "c")
		{
			if (sel === 8)
				return 4;
			if (sel === 10 || sel === 12)
				return 1;
			return 0;
		}
		if ((kind === "a" || kind === "d") && sel === 6)
			return 1;
		return 0;
	}

	// view:   3x3 rotation model space -> camera space (x right, y up, z towards viewer)
	// origin: output pixel position of the model origin (Mario's feet)
	// Returns { width, height, data: Float32Array RGBA } of size * ss
	function render(soup, view, size, pxPerUnit, origin, lightDir, ss)
	{
		ss = ss || 4;
		const W = size[0] * ss, H = size[1] * ss;
		const color = new Float32Array(W * H * 3);
		const alpha = new Float32Array(W * H);
		const zbuf = new Float32Array(W * H).fill(-1e9);
		const k = pxPerUnit * ss;
		const ox = origin[0] * ss, oy = origin[1] * ss;
		const ll = Math.sqrt(lightDir[0] * lightDir[0] + lightDir[1] * lightDir[1] + lightDir[2] * lightDir[2]);
		const L = [lightDir[0] / ll, lightDir[1] / ll, lightDir[2] / ll];
		const sx = [0, 0, 0], sy = [0, 0, 0], sz = [0, 0, 0];
		const shadeV = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
		const inputs = [0, 0, 0, 0];
		const vals = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]];
		const one = [1, 1, 1], zero = [0, 0, 0];

		for (const tri of soup)
		{
			for (let i = 0; i < 3; ++i)
			{
				const p = tri.pos[i];
				const cx = p[0] * view[0] + p[1] * view[3] + p[2] * view[6];
				const cy = p[0] * view[1] + p[1] * view[4] + p[2] * view[7];
				const cz = p[0] * view[2] + p[1] * view[5] + p[2] * view[8];
				sx[i] = ox + cx * k;
				sy[i] = oy - cy * k;
				sz[i] = cz;
			}
			const area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]);
			if (Math.abs(area) < 1e-9 || (tri.cull && area > 0))
				continue;
			const x0 = Math.max(Math.floor(Math.min(sx[0], sx[1], sx[2])), 0);
			const x1 = Math.min(Math.ceil(Math.max(sx[0], sx[1], sx[2])), W - 1);
			const y0 = Math.max(Math.floor(Math.min(sy[0], sy[1], sy[2])), 0);
			const y1 = Math.min(Math.ceil(Math.max(sy[0], sy[1], sy[2])), H - 1);
			if (x0 > x1 || y0 > y1)
				continue;

			// Per-vertex lighting (gouraud shading), slightly more contrast than on the N64
			for (let i = 0; i < 3; ++i)
			{
				const n = tri.nrm[i];
				const cnx = n[0] * view[0] + n[1] * view[3] + n[2] * view[6];
				const cny = n[0] * view[1] + n[1] * view[4] + n[2] * view[7];
				const cnz = n[0] * view[2] + n[1] * view[5] + n[2] * view[8];
				const d = Math.max(0.0, cnx * L[0] + cny * L[1] + cnz * L[2]);
				for (let c = 0; c < 3; ++c)
					shadeV[i][c] = Math.min(Math.max(tri.ambient[c] * 0.7 + tri.diffuse[c] * (0.15 + 0.95 * d), 0), 1);
			}

			const comb = tri.combine;
			inputs[0] = ccInput(comb[0], "a");
			inputs[1] = ccInput(comb[1], "b");
			inputs[2] = ccInput(comb[2], "c");
			inputs[3] = ccInput(comb[3], "d");
			const tex = tri.tex;
			const uv = tri.uv;

			for (let y = y0; y <= y1; ++y)
			{
				const ys = y + 0.5;
				for (let x = x0; x <= x1; ++x)
				{
					const xs = x + 0.5;
					const w0 = ((sx[1] - xs) * (sy[2] - ys) - (sx[2] - xs) * (sy[1] - ys)) / area;
					const w1 = ((sx[2] - xs) * (sy[0] - ys) - (sx[0] - xs) * (sy[2] - ys)) / area;
					const w2 = 1.0 - w0 - w1;
					if (w0 < -1e-6 || w1 < -1e-6 || w2 < -1e-6)
						continue;
					const idx = y * W + x;
					const z = w0 * sz[0] + w1 * sz[1] + w2 * sz[2];
					if (!(z > zbuf[idx]))
						continue;

					const shade = vals[2];
					for (let c = 0; c < 3; ++c)
						shade[c] = w0 * shadeV[0][c] + w1 * shadeV[1][c] + w2 * shadeV[2][c];
					let ta = 0;
					const texel = vals[3];
					if (tex)
					{
						const u = w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0];
						const v = w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1];
						const tx = Math.min(Math.max(Math.floor(u), 0), tex.width - 1);
						const ty = Math.min(Math.max(Math.floor(v), 0), tex.height - 1);
						const ti = (ty * tex.width + tx) * 4;
						texel[0] = tex.data[ti];
						texel[1] = tex.data[ti + 1];
						texel[2] = tex.data[ti + 2];
						ta = tex.data[ti + 3];
					}
					else
					{
						texel[0] = texel[1] = texel[2] = 0;
					}
					const ta3 = vals[4];
					ta3[0] = ta3[1] = ta3[2] = ta;
					vals[0] = zero;
					vals[1] = one;
					const a = vals[inputs[0]], b = vals[inputs[1]], c3 = vals[inputs[2]], d = vals[inputs[3]];
					for (let c = 0; c < 3; ++c)
					{
						const out = (a[c] - b[c]) * c3[c] + d[c];
						color[idx * 3 + c] = Math.min(Math.max(out, 0), 1);
					}
					zbuf[idx] = z;
					alpha[idx] = 1.0;
				}
			}
		}

		const data = new Float32Array(W * H * 4);
		for (let i = 0; i < W * H; ++i)
		{
			data[i * 4] = color[i * 3];
			data[i * 4 + 1] = color[i * 3 + 1];
			data[i * 4 + 2] = color[i * 3 + 2];
			data[i * 4 + 3] = alpha[i];
		}
		return { width: W, height: H, data: data };
	}

	function viewMatrix(yawDeg, pitchDeg)
	{
		const y = yawDeg * Math.PI / 180, p = (pitchDeg || 0) * Math.PI / 180;
		const ry = Float64Array.of(Math.cos(y), 0, -Math.sin(y), 0, 1, 0, Math.sin(y), 0, Math.cos(y));
		const rx = Float64Array.of(1, 0, 0, 0, Math.cos(p), Math.sin(p), 0, -Math.sin(p), Math.cos(p));
		return matMul(ry, rx);
	}

	return { DL, SKELETON, Model, animNumFrames, poseMatrices, buildSoup, render, viewMatrix };
})();
