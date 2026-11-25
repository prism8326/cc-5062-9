/* Index-painting core for the viewer window.
 *
 * This file is intentionally DOM-free so its actual index/dither operations
 * can be exercised from Node.  The UI layer only renders the resulting indices
 * and never treats the displayed RGB canvas as source data.
 */
(function attachIndexPaintCore(root) {
  "use strict";

  function entry(r, g, b, a = 255, name = "") {
    return { r, g, b, a, name };
  }

  const PALETTE_TABLES = {
    demo: [
      entry(0, 0, 0, 0, "transparent"),
      entry(30, 30, 48, 255, "ink-dark"),
      entry(70, 70, 110, 255, "ink-mid"),
      entry(120, 120, 170, 255, "ink-light"),
      entry(200, 200, 230, 255, "ink-pale"),
      entry(220, 60, 60, 255, "accent"),
      entry(30, 30, 48, 255, "ink-dark-dup"),
      entry(40, 160, 90, 255, "green"),
    ],
    grayscale: [
      entry(0, 0, 0, 0, "transparent"),
      ...[28, 64, 104, 148, 190, 224, 250].map((v, i) => entry(v, v, v, 255, `gray-${i + 1}`)),
    ],
    sepia: [
      entry(0, 0, 0, 0, "transparent"),
      ...[[43, 32, 24], [82, 58, 39], [126, 91, 58], [171, 132, 86],
          [214, 184, 139], [239, 220, 181], [255, 246, 220]]
        .map((c, i) => entry(c[0], c[1], c[2], 255, `sepia-${i + 1}`)),
    ],
    spectrum: [
      entry(0, 0, 0, 0, "transparent"),
      ...[[35, 38, 66], [67, 70, 128], [72, 123, 184], [72, 178, 163],
          [141, 205, 105], [245, 205, 82], [229, 87, 72]]
        .map((c, i) => entry(c[0], c[1], c[2], 255, `spectrum-${i + 1}`)),
    ],
  };

  const FLOYD_STEINBERG = [
    [1, 0, 7 / 16],
    [-1, 1, 3 / 16],
    [0, 1, 5 / 16],
    [1, 1, 1 / 16],
  ];

  class Ramp {
    constructor(indices) {
      this.indices = Array.from(indices);
      if (this.indices.length < 1) throw new Error("ramp needs at least one palette index");
      if (this.indices.some((i) => i < 0)) throw new Error("palette indices must be non-negative");
      if (new Set(this.indices).size !== this.indices.length) {
        throw new Error("ramp steps must be distinct indices");
      }
      this.steps = this.indices.length;
    }
    at(position) {
      const k = Math.max(0, Math.min(position, this.steps - 1));
      return this.indices[k];
    }
  }

  function bayerMatrix(order) {
    if (order < 1) throw new Error("Bayer order must be >= 1");
    let m = [[0]];
    for (let o = 0; o < order; o += 1) {
      const n = m.length;
      const next = Array.from({ length: n * 2 }, () => Array(n * 2).fill(0));
      for (let y = 0; y < n; y += 1) {
        for (let x = 0; x < n; x += 1) {
          const v = 4 * m[y][x];
          next[y][x] = v;
          next[y][x + n] = v + 2;
          next[y + n][x] = v + 3;
          next[y + n][x + n] = v + 1;
        }
      }
      m = next;
    }
    return m;
  }

  class OrderedDither {
    constructor(order = 3) {
      this.matrix = bayerMatrix(order);
      this.n = this.matrix.length;
      this.scale = 1 / (this.n * this.n);
    }
    threshold(x, y) {
      const v = this.matrix[((y % this.n) + this.n) % this.n][((x % this.n) + this.n) % this.n];
      return (v + 0.5) * this.scale;
    }
    pick(position, x, y) {
      const k = Math.floor(position);
      const f = position - k;
      return k + (f > this.threshold(x, y) ? 1 : 0);
    }
  }

  function rampPosition(pressure, ramp) {
    const p = Math.max(0, Math.min(1, pressure));
    return p * (ramp.steps - 1);
  }

  function orderedIndex(brush, position, x, y) {
    const k = brush.dither.pick(position, x, y);
    return brush.ramp.at(k);
  }

  function createBrush(options = {}) {
    const ramp = options.ramp instanceof Ramp ? options.ramp : new Ramp(options.ramp || [1, 2, 3, 4]);
    return {
      ramp,
      radius: options.radius ?? 2,
      spacing: options.spacing ?? 1,
      softEdge: options.softEdge ?? 0,
      dither: new OrderedDither(options.ditherOrder ?? 3),
      lockPolicy: options.lockPolicy || "restart",
      alphaPolicy: options.alphaPolicy || "dither",
      shape: options.shape || "disc",
    };
  }

  function isFullyCovered(brush, x, y, cx, cy) {
    const r = Math.max(brush.radius, 0.01);
    const coreR = Math.max(r * (1 - brush.softEdge), 0.5);
    if (brush.shape === "square") {
      return Math.abs(x - cx) <= coreR && Math.abs(y - cy) <= coreR;
    }
    return Math.hypot(x + 0.5 - cx, y + 0.5 - cy) <= coreR;
  }

  function stampPixels(brush, cx, cy) {
    const r = Math.max(brush.radius, 0.01);
    const x0 = Math.floor(cx - r - 0.5);
    const x1 = Math.ceil(cx + r + 0.5);
    const y0 = Math.floor(cy - r - 0.5);
    const y1 = Math.ceil(cy + r + 0.5);
    const out = [];
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        let cov = 0;
        if (brush.shape === "square") {
          if (Math.abs(x - cx) <= r && Math.abs(y - cy) <= r) cov = 1;
        } else {
          const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
          if (d > r) continue;
          if (brush.softEdge <= 0 || d <= r * (1 - brush.softEdge)) cov = 1;
          else {
            const inner = r * (1 - brush.softEdge);
            cov = Math.max(0.05, 1 - (d - inner) / Math.max(r - inner, 1e-9));
          }
        }
        if (cov > 0) out.push([x, y, cov]);
      }
    }
    return out;
  }

  function createProject(width = 48, height = 32, table = "demo", transparentIndex = 0) {
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
      throw new Error("canvas dimensions must be positive integers");
    }
    const palette = Array.isArray(table) ? table.map((e) => ({ ...e })) : PALETTE_TABLES[table]?.map((e) => ({ ...e }));
    if (!palette) throw new Error(`unknown palette table: ${table}`);
    if (!(transparentIndex >= 0 && transparentIndex < palette.length)) {
      throw new Error("transparent_index outside palette");
    }
    return {
      version: 1,
      width,
      height,
      transparent_index: transparentIndex,
      palette,
      indices: new Uint8Array(width * height),
      locked_indices: [],
      pixel_locks: [],
    };
  }

  function indexAt(project, x, y) {
    return project.indices[y * project.width + x];
  }

  function setIndex(project, x, y, value) {
    if (x < 0 || y < 0 || x >= project.width || y >= project.height) {
      throw new RangeError(`pixel coordinate (${x}, ${y}) is outside canvas`);
    }
    if (value < 0 || value >= project.palette.length) {
      throw new RangeError(`index ${value} is outside the available colour table`);
    }
    project.indices[y * project.width + x] = value;
  }

  function isLocked(project, x, y) {
    return project.locked_indices.includes(indexAt(project, x, y)) ||
      project.pixel_locks.some(([px, py]) => px === x && py === y);
  }

  function distinctIndices(project) {
    return [...new Set(project.indices)].sort((a, b) => a - b);
  }

  function buildTargets(project, points, brush) {
    const targets = new Map();
    for (const [cx, cy, pressure] of points) {
      const position = rampPosition(pressure, brush.ramp);
      for (const [x, y, cov] of stampPixels(brush, cx, cy)) {
        if (x < 0 || y < 0 || x >= project.width || y >= project.height) continue;
        const key = `${x},${y}`;
        const old = targets.get(key);
        const stronger = !old || position > old.position ||
          (position === old.position && cov > old.coverage);
        if (stronger) {
          targets.set(key, { x, y, position, coverage: cov, cx, cy });
        }
      }
    }
    return targets;
  }

  function alphaGate(project, brush, x, y, coverage, ink, centre) {
    const existing = indexAt(project, x, y);
    const full = coverage >= 1 || (centre && isFullyCovered(brush, x, y, centre[0], centre[1]));
    if (full || brush.alphaPolicy === "overwrite") return ink;
    if (brush.alphaPolicy === "keep") {
      return existing === project.transparent_index ? existing : ink;
    }
    const threshold = brush.dither.threshold(x, y);
    return coverage > threshold ? ink : existing;
  }

  function paintOrdered(project, inputPoints, brushOptions = {}) {
    const brush = createBrush(brushOptions);
    const points = inputPoints.map((p) => p.length === 3 ? p : [p.x, p.y, p.pressure ?? 1]);
    const targets = buildTargets(project, points, brush);
    const used = new Set();
    for (const target of targets.values()) {
      const { x, y, position, coverage, cx, cy } = target;
      if (isLocked(project, x, y)) continue;
      const ink = orderedIndex(brush, position, x, y);
      const chosen = alphaGate(project, brush, x, y, coverage, ink, [cx, cy]);
      setIndex(project, x, y, chosen);
      used.add(chosen);
    }
    return used;
  }

  class DiffusionCursor {
    constructor(errors = new Map(), region = null) {
      this.errors = new Map(errors);
      this.region = region;
    }
    get(x, y) { return this.errors.get(`${x},${y}`) ?? 0; }
    pop(x, y) {
      const key = `${x},${y}`;
      const value = this.errors.get(key) ?? 0;
      this.errors.delete(key);
      return value;
    }
    add(x, y, value) {
      if (!value) return;
      const key = `${x},${y}`;
      this.errors.set(key, (this.errors.get(key) ?? 0) + value);
    }
    propagate(x, y, residual, targets = null, region = this.region) {
      for (const [dx, dy, weight] of FLOYD_STEINBERG) {
        if (dy === 0 && dx <= 0) continue;
        const nx = x + dx, ny = y + dy;
        if (targets && !targets.has(`${nx},${ny}`)) continue;
        if (region) {
          const [x0, y0, x1, y1] = region;
          if (!(x0 <= nx && nx <= x1 && y0 <= ny && ny <= y1)) continue;
        }
        this.add(nx, ny, residual * weight);
      }
    }
    snapshot() {
      return {
        residuals: [...this.errors.entries()].map(([key, value]) => {
          const [x, y] = key.split(",").map(Number);
          return [x, y, value];
        }).sort((a, b) => a[1] - b[1] || a[0] - b[0]),
        region: this.region,
      };
    }
    restore(snapshot) {
      this.errors = new Map((snapshot.residuals || []).map(([x, y, v]) => [`${x},${y}`, v]));
      this.region = snapshot.region ?? null;
    }
  }

  function rampCoordinateOf(brush, index) {
    const k = brush.ramp.indices.indexOf(index);
    return k < 0 ? null : k;
  }

  function pythonRound(value) {
    if (Math.abs(value - Math.trunc(value)) === 0.5) {
      const floor = Math.floor(value);
      return floor % 2 === 0 ? floor : floor + 1;
    }
    return Math.round(value);
  }

  function processCell(project, brush, targets, x, y, cursor) {
    const residual = cursor.pop(x, y);
    const target = targets.get(`${x},${y}`);
    if (!target) {
      if (residual) cursor.propagate(x, y, residual, null);
      return;
    }
    const { position, coverage, cx, cy } = target;
    if (isLocked(project, x, y)) {
      if (brush.lockPolicy === "restart") return;
      let virtual = rampCoordinateOf(brush, indexAt(project, x, y));
      if (virtual === null) {
        virtual = Math.max(0, Math.min(pythonRound(position), brush.ramp.steps - 1));
      }
      cursor.propagate(x, y, position + residual - virtual, null);
      return;
    }
    const corrected = position + residual;
    const k = Math.max(0, Math.min(pythonRound(corrected), brush.ramp.steps - 1));
    const ink = brush.ramp.at(k);
    const chosen = alphaGate(project, brush, x, y, coverage, ink, [cx, cy]);
    setIndex(project, x, y, chosen);
    let virtual = rampCoordinateOf(brush, chosen);
    if (virtual === null) virtual = k;
    cursor.propagate(x, y, corrected - virtual, targets);
  }

  function paintErrorDiffusion(project, inputPoints, brushOptions = {}, region = null, cursor = new DiffusionCursor()) {
    const brush = createBrush(brushOptions);
    const points = inputPoints.map((p) => p.length === 3 ? p : [p.x, p.y, p.pressure ?? 1]);
    const targets = buildTargets(project, points, brush);
    if (targets.size === 0) return { used: new Set(), cursor };
    let bounds = region;
    if (!bounds) {
      const coords = [...targets.values()];
      bounds = [
        Math.min(...coords.map((t) => t.x)),
        Math.min(...coords.map((t) => t.y)),
        Math.max(...coords.map((t) => t.x)),
        Math.max(...coords.map((t) => t.y)),
      ];
    }
    cursor.region = bounds;
    const before = new Set(distinctIndices(project));
    const [x0, y0, x1, y1] = bounds;
    for (let y = y0; y <= y1; y += 1) {
      for (let x = x0; x <= x1; x += 1) {
        processCell(project, brush, targets, x, y, cursor);
      }
    }
    cursor.region = null;
    return { used: new Set(distinctIndices(project).filter((i) => !before.has(i))), cursor };
  }

  function reorderPalette(project, permutation, mode) {
    const n = project.palette.length;
    if (permutation.slice().sort((a, b) => a - b).join(",") !==
        Array.from({ length: n }, (_, i) => i).join(",")) {
      throw new Error("permutation must be a bijection over palette indices");
    }
    const oldToNew = {};
    permutation.forEach((oldIndex, newIndex) => { oldToNew[oldIndex] = newIndex; });
    const newPalette = permutation.map((oldIndex) => ({ ...project.palette[oldIndex] }));
    if (mode === "keep_appearance") {
      project.indices = project.indices.map((value) => oldToNew[value] ?? value);
      project.transparent_index = oldToNew[project.transparent_index] ?? project.transparent_index;
      project.locked_indices = project.locked_indices.map((value) => oldToNew[value] ?? value);
      project.palette = newPalette;
      return oldToNew;
    }
    if (mode === "keep_identity") {
      project.palette = newPalette;
      return {};
    }
    throw new Error("mode must be keep_appearance or keep_identity");
  }

  function snapshotProject(project) {
    return {
      width: project.width,
      height: project.height,
      transparent_index: project.transparent_index,
      indices: project.indices.slice(),
      palette: project.palette.map((e) => ({ ...e })),
      locked_indices: [...project.locked_indices],
      pixel_locks: project.pixel_locks.map((p) => [...p]),
    };
  }

  function restoreProject(project, snapshot) {
    if (snapshot.width !== project.width || snapshot.height !== project.height) {
      throw new Error("snapshot dimensions do not match project");
    }
    project.transparent_index = snapshot.transparent_index;
    project.indices = snapshot.indices.slice();
    project.palette = snapshot.palette.map((e) => ({ ...e }));
    project.locked_indices = [...snapshot.locked_indices];
    project.pixel_locks = snapshot.pixel_locks.map((p) => [...p]);
  }

  class History {
    constructor() { this.undoStack = []; }
    checkpoint(label, project, cursor = null) {
      this.undoStack.push({
        label,
        project: snapshotProject(project),
        errors: cursor ? cursor.snapshot() : null,
      });
    }
    undo(project, cursor = null) {
      const entry = this.undoStack.pop();
      if (!entry) throw new Error("nothing to undo");
      restoreProject(project, entry.project);
      if (cursor) {
        if (entry.errors) cursor.restore(entry.errors);
        else cursor.errors.clear();
      }
      return entry.label;
    }
    canUndo() { return this.undoStack.length > 0; }
  }

  function pointsOnLine(x0, y0, x1, y1, pressure0 = 0, pressure1 = 1, spacing = 0.5) {
    const length = Math.hypot(x1 - x0, y1 - y0);
    const count = Math.max(2, Math.ceil(length / spacing) + 1);
    const points = [];
    for (let i = 0; i < count; i += 1) {
      const t = i / (count - 1);
      points.push([
        x0 + (x1 - x0) * t,
        y0 + (y1 - y0) * t,
        pressure0 + (pressure1 - pressure0) * t,
      ]);
    }
    return points;
  }

  function encodeBase64Indices(indices) {
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < indices.length; i += chunk) {
      binary += String.fromCharCode(...indices.subarray(i, i + chunk));
    }
    if (typeof btoa === "function") return btoa(binary);
    return Buffer.from(binary, "binary").toString("base64");
  }

  function toSidecar(project) {
    return {
      version: project.version || 1,
      width: project.width,
      height: project.height,
      transparent_index: project.transparent_index,
      locked_indices: [...project.locked_indices],
      pixel_locks: project.pixel_locks.map(([x, y]) => [x, y]),
      palette: project.palette.map(({ r, g, b, a, name }) => ({ r, g, b, a, name })),
      indices_base64: encodeBase64Indices(project.indices),
    };
  }

  function decodeIndices(base64, count) {
    let binary;
    if (typeof atob === "function") binary = atob(base64);
    else binary = Buffer.from(base64, "base64").toString("binary");
    const out = new Uint8Array(count);
    for (let i = 0; i < count; i += 1) out[i] = binary.charCodeAt(i);
    return out;
  }

  function fromSidecar(data) {
    const project = createProject(data.width, data.height, data.palette, data.transparent_index);
    if (data.indices_base64) {
      project.indices = decodeIndices(data.indices_base64, data.width * data.height);
    } else if (data.indices) {
      project.indices = Uint8Array.from(data.indices);
    } else {
      project.indices = new Uint8Array(data.width * data.height);
    }
    if (project.indices.length !== data.width * data.height) {
      throw new Error("sidecar indices length does not match canvas dimensions");
    }
    project.locked_indices = [...(data.locked_indices || [])];
    project.pixel_locks = (data.pixel_locks || []).map((p) => Array.isArray(p) ? p : [p[0], p[1]]);
    return project;
  }

  function exportMapping(project) {
    return Object.fromEntries(project.palette.map((e, i) => [i, [e.r, e.g, e.b, e.a]]));
  }

  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function u32be(value) {
    return [
      (value >>> 24) & 255,
      (value >>> 16) & 255,
      (value >>> 8) & 255,
      value & 255,
    ];
  }

  function pngChunk(tag, data) {
    const tagBytes = [...tag].map((ch) => ch.charCodeAt(0));
    const body = new Uint8Array([...tagBytes, ...data]);
    const crc = crc32(body);
    return new Uint8Array([...u32be(data.length), ...tagBytes, ...data, ...u32be(crc)]);
  }

  function adler32(bytes) {
    let a = 1, b = 0;
    for (const value of bytes) {
      a = (a + value) % 65521;
      b = (b + a) % 65521;
    }
    return ((b << 16) | a) >>> 0;
  }

  function zlibStored(raw) {
    const blocks = [];
    for (let offset = 0; offset < raw.length; offset += 65535) {
      const len = Math.min(65535, raw.length - offset);
      const final = offset + len >= raw.length ? 1 : 0;
      blocks.push(final, len & 255, (len >>> 8) & 255, (~len) & 255, ((~len) >>> 8) & 255);
      blocks.push(...raw.subarray(offset, offset + len));
    }
    const adler = adler32(raw);
    return new Uint8Array([0x78, 0x01, ...blocks, ...u32be(adler)]);
  }

  function encodeIndexedPng(project) {
    if (project.palette.length === 0 || project.palette.length > 256) {
      throw new Error("indexed PNG requires 1..256 palette entries");
    }
    const { width: w, height: h } = project;
    const ihdr = new Uint8Array([
      ...u32be(w), ...u32be(h), 8, 3, 0, 0, 0,
    ]);
    const plte = new Uint8Array(project.palette.flatMap((e) => [e.r, e.g, e.b]));
    let trnsEnd = 0;
    project.palette.forEach((e, i) => { if (e.a !== 255) trnsEnd = i + 1; });
    const trns = new Uint8Array(project.palette.slice(0, trnsEnd).map((e) => e.a));
    const raw = new Uint8Array(h * (w + 1));
    for (let y = 0; y < h; y += 1) {
      raw[y * (w + 1)] = 0;
      raw.set(project.indices.subarray(y * w, (y + 1) * w), y * (w + 1) + 1);
    }
    const idat = zlibStored(raw);
    const signature = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    const chunks = [
      pngChunk("IHDR", ihdr),
      pngChunk("PLTE", plte),
      ...(trns.length ? [pngChunk("tRNS", trns)] : []),
      pngChunk("IDAT", idat),
      pngChunk("IEND", new Uint8Array()),
    ];
    const total = signature.length + chunks.reduce((n, c) => n + c.length, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    out.set(signature, offset); offset += signature.length;
    for (const chunk of chunks) { out.set(chunk, offset); offset += chunk.length; }
    return out;
  }

  const api = {
    PALETTE_TABLES, FLOYD_STEINBERG, Ramp, OrderedDither, DiffusionCursor, History,
    bayerMatrix, rampPosition, orderedIndex, createBrush, stampPixels, buildTargets,
    createProject, indexAt, setIndex, isLocked, distinctIndices, paintOrdered,
    paintErrorDiffusion, reorderPalette, snapshotProject, restoreProject,
    pointsOnLine, toSidecar, fromSidecar, decodeIndices, exportMapping,
    encodeIndexedPng,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.IdxPaintCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
