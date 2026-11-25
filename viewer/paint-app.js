/* DOM controller for the index-painting window.  All pixel decisions are made
 * by viewer/paint-core.js; this file only forwards pointer/form events.
 */
(function () {
  "use strict";

  const C = window.IdxPaintCore;
  const $ = (id) => document.getElementById(id);

  let project = C.createProject(48, 32, "demo", 0);
  let history = new C.History();
  let cursor = new C.DiffusionCursor();
  let zoom = 8;
  let selectedInk = 4;
  let drawing = null;

  const view = $("view");
  const overlay = $("overlay");
  const ctx = view.getContext("2d");
  const octx = overlay.getContext("2d");

  function clearError() {
    const box = $("error");
    if (box) {
      box.textContent = "";
      box.hidden = true;
    }
    const status = $("status");
    if (status) status.textContent = "就绪：所有颜色与抖色结果均由索引数据实际计算。";
  }

  function reportError(error) {
    console.error(error);
    const box = $("error");
    if (box) {
      box.hidden = false;
      box.textContent = `索引绘画界面异常：${error && error.message ? error.message : String(error)}`;
    }
    const status = $("status");
    if (status) status.textContent = "状态：异常已提示，索引数据未导出为 RGB 缓存。";
  }

  function guard(fn) {
    return (...args) => {
      try {
        clearError();
        return fn(...args);
      } catch (error) {
        reportError(error);
        return undefined;
      }
    };
  }

  function cssColor(entry) {
    return `rgba(${entry.r},${entry.g},${entry.b},${(entry.a / 255).toFixed(3)})`;
  }

  function brushOptions(pressure) {
    const preset = $("rampPreset") ? $("rampPreset").value : "ladder";
    let ramp;
    if (preset === "full") {
      ramp = project.palette.map((_, i) => i).filter((i) => i !== project.transparent_index);
    } else if (preset === "ink") {
      ramp = [selectedInk];
    } else if (preset === "transparent") {
      ramp = [project.transparent_index];
    } else {
      ramp = [1, 2, 3, 4].filter((i) => i < project.palette.length);
    }
    if (!ramp.length) ramp = [project.transparent_index];
    return {
      ramp,
      radius: parseFloat($("radius")?.value || "2"),
      spacing: 1,
      softEdge: parseFloat($("softEdge")?.value || "0"),
      ditherOrder: 3,
      alphaPolicy: $("alphaPolicy")?.value || "dither",
      pressure,
    };
  }

  function render() {
    const w = project.width, h = project.height;
    view.width = overlay.width = w * zoom;
    view.height = overlay.height = h * zoom;
    octx.clearRect(0, 0, overlay.width, overlay.height);

    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const idx = C.indexAt(project, x, y);
        ctx.fillStyle = cssColor(project.palette[idx]);
        ctx.fillRect(x * zoom, y * zoom, zoom, zoom);
      }
    }

    if ($("showIndex")?.checked && zoom >= 6) {
      octx.font = `${Math.max(7, Math.floor(zoom * 0.42))}px monospace`;
      octx.textAlign = "center";
      octx.textBaseline = "middle";
      for (let y = 0; y < h; y += 1) {
        for (let x = 0; x < w; x += 1) {
          const idx = C.indexAt(project, x, y);
          const e = project.palette[idx];
          const lum = (e.r + e.g + e.b) / 3;
          octx.fillStyle = lum > 140 && e.a > 128 ? "rgba(0,0,0,.75)" : "rgba(255,255,255,.85)";
          octx.fillText(idx.toString(16), x * zoom + zoom / 2, y * zoom + zoom / 2);
        }
      }
    }
    view.style.background = $("checker")?.checked ? "" : "#000";
    if ($("undo")) $("undo").disabled = !history.canUndo();
  }

  function renderPalette() {
    const table = $("palette");
    table.innerHTML = "";
    project.palette.forEach((e, i) => {
      const tr = document.createElement("tr");
      tr.dataset.index = String(i);
      tr.tabIndex = 0;
      if (i === selectedInk) tr.className = "selected-ink";
      const lock = project.locked_indices.includes(i) ? " 🔒" : "";
      const trans = i === project.transparent_index ? " (透明索引)" : "";
      tr.innerHTML =
        `<td>${i}${lock}${trans}</td>` +
        `<td><span class="swatch" style="background:${cssColor(e)}"></span></td>` +
        `<td>(${e.r}, ${e.g}, ${e.b}, ${e.a})</td>` +
        `<td>${e.name ?? ""}</td>`;
      const choose = guard(() => {
        selectedInk = i;
        if ($("rampPreset")) $("rampPreset").value = "ink";
        renderPalette();
        updateEvidence("select-ink");
      });
      tr.addEventListener("click", choose);
      tr.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") choose(ev);
      });
      table.appendChild(tr);
    });
  }

  function updateEvidence(action) {
    const box = $("evidence");
    if (!box) return;
    const evidence = {
      action,
      width: project.width,
      height: project.height,
      transparent_index: project.transparent_index,
      distinct_indices: C.distinctIndices(project),
      export_mapping: C.exportMapping(project),
    };
    box.textContent = JSON.stringify(evidence, null, 2);
  }

  function paintSegment(x0, y0, x1, y1, pressure, record = false) {
    if (record) history.checkpoint("paint", project, cursor);
    const options = brushOptions(pressure);
    const points = C.pointsOnLine(x0, y0, x1, y1, pressure, pressure, options.spacing || 1);
    const mode = $("ditherMode")?.value || "ordered";
    if (mode === "diffusion") {
      const result = C.paintErrorDiffusion(project, points, options, null, cursor);
      cursor = result.cursor;
    } else {
      C.paintOrdered(project, points, options);
    }
  }

  function paintGradient(x0, y0, x1, y1, options = {}) {
    history.checkpoint(options.label || "gradient", project, cursor);
    const brush = brushOptions(1);
    if (options.ramp) brush.ramp = new C.Ramp(options.ramp);
    const mode = options.mode || $("ditherMode")?.value || "ordered";
    const points = C.pointsOnLine(x0, y0, x1, y1, 0, 1, brush.spacing || 1);
    if (mode === "diffusion") {
      const result = C.paintErrorDiffusion(project, points, brush, options.region || null, cursor);
      cursor = result.cursor;
    } else {
      C.paintOrdered(project, points, brush);
    }
    render();
    updateEvidence(options.label || `gradient-${mode}`);
  }

  function eventPixel(ev) {
    const rect = view.getBoundingClientRect();
    const x = Math.floor((ev.clientX - rect.left) * project.width / rect.width);
    const y = Math.floor((ev.clientY - rect.top) * project.height / rect.height);
    return { x: x + 0.5, y: y + 0.5, ix: x, iy: y };
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const onPointerDown = guard((ev) => {
    ev.preventDefault();
    const p = eventPixel(ev);
    drawing = { start: p, last: p, moved: false };
    history.checkpoint("pointer-stroke", project, cursor);
    if (($("tool")?.value || "brush") === "brush") {
      const pressure = parseFloat($("pressure")?.value || "0.8");
      paintSegment(p.x, p.y, p.x, p.y, pressure);
      render();
    }
    view.setPointerCapture?.(ev.pointerId);
  });

  const onPointerMove = guard((ev) => {
    const p = eventPixel(ev);
    if (!project.in_bounds && (p.ix < 0 || p.iy < 0 || p.ix >= project.width || p.iy >= project.height)) return;

    const idx = C.indexAt(project, Math.max(0, Math.min(project.width - 1, p.ix)),
      Math.max(0, Math.min(project.height - 1, p.iy)));
    const e = project.palette[idx];
    const info = $("info");
    if (info && p.ix >= 0 && p.iy >= 0 && p.ix < project.width && p.iy < project.height) {
      info.textContent =
        `坐标 (${p.ix}, ${p.iy})\n索引: ${idx} (0x${idx.toString(16)})` +
        `${idx === project.transparent_index ? "  [透明索引]" : ""}` +
        `${project.locked_indices.includes(idx) ? "  [锁色]" : ""}\n` +
        `RGBA: (${e.r}, ${e.g}, ${e.b}, ${e.a})  名称: ${e.name ?? ""}`;
    }

    if (!drawing) return;
    drawing.moved = true;
    if (($("tool")?.value || "brush") === "brush") {
      const pressure = parseFloat($("pressure")?.value || String(ev.pressure || 0.8));
      paintSegment(drawing.last.x, drawing.last.y, p.x, p.y, pressure);
      drawing.last = p;
      render();
    } else {
      render();
      octx.strokeStyle = "#9fb4ff";
      octx.setLineDash([4, 3]);
      octx.beginPath();
      octx.moveTo(drawing.start.ix * zoom + zoom / 2, drawing.start.iy * zoom + zoom / 2);
      octx.lineTo(p.ix * zoom + zoom / 2, p.iy * zoom + zoom / 2);
      octx.stroke();
      octx.setLineDash([]);
    }
  });

  const onPointerUp = guard((ev) => {
    if (!drawing) return;
    const p = eventPixel(ev);
    if (($("tool")?.value || "brush") === "gradient") {
      paintGradient(drawing.start.x, drawing.start.y, p.x, p.y);
    } else {
      render();
      updateEvidence("pointer-brush");
    }
    drawing = null;
    if ($("undo")) $("undo").disabled = !history.canUndo();
  });

  function loadProjectData(data) {
    project = C.fromSidecar(data);
    history = new C.History();
    cursor = new C.DiffusionCursor();
    selectedInk = project.palette.length > 4 ? 4 : 1;
    render();
    renderPalette();
    updateEvidence("load-project");
  }

  function bind() {
    view.addEventListener("pointerdown", onPointerDown);
    view.addEventListener("pointermove", onPointerMove);
    view.addEventListener("pointerup", onPointerUp);
    view.addEventListener("pointercancel", () => { drawing = null; });

    $("zoom")?.addEventListener("input", guard((ev) => {
      zoom = parseInt(ev.target.value, 10);
      $("zoomLabel").textContent = `${zoom}x`;
      render();
    }));
    $("showIndex")?.addEventListener("change", render);
    $("checker")?.addEventListener("change", render);

    $("paletteTableSelect")?.addEventListener("change", guard((ev) => {
      const name = ev.target.value;
      history.checkpoint("select-palette-table", project, cursor);
      project.palette = C.PALETTE_TABLES[name].map((e) => ({ ...e }));
      renderPalette();
      render();
      updateEvidence(`select-table-${name}`);
    }));

    $("reversePalette")?.addEventListener("click", guard(() => {
      const n = project.palette.length;
      const permutation = Array.from({ length: n }, (_, i) => n - 1 - i);
      history.checkpoint("reverse-palette", project, cursor);
      const mapping = C.reorderPalette(project, permutation, "keep_appearance");
      renderPalette();
      render();
      updateEvidence("reverse-palette");
      $("status").textContent = `已按 keep_appearance 重排；映射：${JSON.stringify(mapping)}。撤销会同时还原索引与扩散残差。`;
    }));

    $("undo")?.addEventListener("click", guard(() => {
      const label = history.undo(project, cursor);
      renderPalette();
      render();
      updateEvidence(`undo-${label}`);
    }));

    $("drawGradient")?.addEventListener("click", guard(() => {
      paintGradient(1.5, project.height / 2, project.width - 2.5, project.height / 2);
    }));

    $("drawBothGradients")?.addEventListener("click", guard(() => {
      paintGradient(1.5, Math.max(2, Math.floor(project.height * 0.32)),
        project.width - 2.5, Math.max(2, Math.floor(project.height * 0.32)),
        { mode: "ordered", label: "ordered-gradient" });
      paintGradient(1.5, Math.min(project.height - 3, Math.floor(project.height * 0.68)),
        project.width - 2.5, Math.min(project.height - 3, Math.floor(project.height * 0.68)),
        { mode: "diffusion", label: "diffusion-gradient" });
      if ($("ditherMode")) $("ditherMode").value = "ordered";
    }));

    $("newCanvas")?.addEventListener("click", guard(() => {
      const w = parseInt($("newWidth").value, 10);
      const h = parseInt($("newHeight").value, 10);
      const table = $("paletteTableSelect").value;
      project = C.createProject(w, h, table, 0);
      history = new C.History();
      cursor = new C.DiffusionCursor();
      renderPalette();
      render();
      updateEvidence("new-canvas");
    }));

    $("file")?.addEventListener("change", async (ev) => {
      const file = ev.target.files[0];
      if (!file) return;
      try {
        clearError();
        loadProjectData(JSON.parse(await file.text()));
      } catch (error) {
        reportError(error);
      }
    });

    $("loadDemo")?.addEventListener("click", guard(() => {
      const demoProject = typeof DEMO_PROJECT !== "undefined" ? DEMO_PROJECT : window.DEMO_PROJECT;
      if (!demoProject) throw new Error("demo_data.js did not load DEMO_PROJECT");
      loadProjectData(demoProject);
    }));

    $("exportProject")?.addEventListener("click", guard(() => {
      const sidecar = C.toSidecar(project);
      downloadBlob(new Blob([JSON.stringify(sidecar, null, 2)], { type: "application/json" }),
        "index-painting.idx.json");
      $("status").textContent = "已从索引数组导出 .idx.json；未读取界面 RGB 缓存。";
    }));

    $("exportPng")?.addEventListener("click", guard(() => {
      const bytes = C.encodeIndexedPng(project);
      downloadBlob(new Blob([bytes], { type: "image/png" }), "index-painting.png");
      $("status").textContent = "已按当前索引和色表编码为 color-type-3 PNG。";
    }));

    $("exportMapping")?.addEventListener("click", guard(() => {
      downloadBlob(
        new Blob([JSON.stringify(C.exportMapping(project), null, 2)], { type: "application/json" }),
        "export-mapping.json",
      );
    }));
  }

  window.idxPaintApp = {
    get project() { return project; },
    get history() { return history; },
    get cursor() { return cursor; },
    paintGradient: guard((...args) => paintGradient(...args)),
    paintSegment: guard(paintSegment),
    selectTable: guard((name) => {
      if ($("paletteTableSelect")) $("paletteTableSelect").value = name;
      history.checkpoint("select-palette-table", project, cursor);
      project.palette = C.PALETTE_TABLES[name].map((e) => ({ ...e }));
      renderPalette(); render(); updateEvidence(`select-table-${name}`);
    }),
    undo: guard(() => {
      const label = history.undo(project, cursor);
      renderPalette(); render(); updateEvidence(`undo-${label}`);
      return label;
    }),
    render: guard(() => { renderPalette(); render(); }),
  };

  bind();
  renderPalette();
  render();
  updateEvidence("initial-blank");
})();
