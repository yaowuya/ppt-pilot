"use strict";

(() => {
  const POLL_INTERVAL = 1000;
  const REQUEST_TIMEOUT = 6000;
  const STAGES = [
    ["brief", "需求整理"], ["research", "资料解析"], ["outline", "内容大纲"],
    ["storyboard", "逐页故事板"], ["manuscript_review", "文稿确认"],
    ["theme", "视觉风格"], ["anchor", "样张确认"], ["production", "页面生成"],
    ["qa", "质量检查"], ["complete", "制作完成"]
  ];
  const STAGE_ALIASES = {
    brief_approved: "brief", research_approved: "research", outline_approved: "outline",
    storyboard_approved: "storyboard", manuscript_approved: "manuscript_review",
    manuscript_blocked: "manuscript_review", review_unavailable: "manuscript_review",
    theme_approved: "theme", anchor_approved: "anchor", qa_approved: "qa"
  };
  const STATUS_NAMES = {
    waiting: "等待确认", pending: "尚未开始", running: "进行中", generating: "生成中",
    blocked: "已阻断", failed: "生成失败", complete: "已完成", completed: "已完成",
    ready: "已产出", unknown: "状态未知", dirty: "待更新", candidate_written: "候选已产出",
    validated: "候选已校验", accepted: "已接受", sample: "样张已产出"
  };
  const KIND_NAMES = { final: "正式页", sample: "样张 · 非正式页", candidate: "候选 · 非正式页" };
  const element = (id) => document.getElementById(id);
  const text = (value, fallback = "") => typeof value === "string" ? value : fallback;
  const setText = (id, value) => { const node = element(id); if (node.textContent !== value) node.textContent = value; };
  const ui = {
    state: null, revision: null, selectedId: null, timer: null, inFlight: false,
    connected: false, lastSuccess: null, failures: 0, previewUrl: null, dialogUrl: null,
    failedPreviewUrl: null, failedDialogUrl: null, thumbnailFailures: new Set()
  };

  function makeNode(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function styleStatus(status) {
    if (["complete", "completed", "ready", "accepted"].includes(status)) return "complete";
    if (["running", "generating", "candidate_written", "validated"].includes(status)) return "running";
    if (["failed", "blocked"].includes(status)) return "blocked";
    return ["waiting", "pending", "dirty"].includes(status) ? status : "unknown";
  }

  function currentStageId(stage) {
    return Object.hasOwn(STAGE_ALIASES, stage) ? STAGE_ALIASES[stage] : stage;
  }

  function checkpointLabel(stage) {
    if (!Object.hasOwn(STAGE_ALIASES, stage)) return "";
    if (stage.endsWith("_approved")) return "已批准";
    return stage === "manuscript_blocked" ? "审查阻断" : "审查暂不可用";
  }

  function oldFinalPreview(slide) {
    return slide.dirty && slide.preview_kind === "final";
  }

  function slideStatus(slide) {
    const status = text(slide.status, "unknown");
    if (slide.dirty) {
      const current = status === "running" || status === "generating" ? "重新生成中" : status === "blocked" || status === "failed" ? "重新生成受阻" : status === "waiting" ? "更新等待确认" : "待重新生成";
      const previewLabel = oldFinalPreview(slide) ? "旧版预览" : slide.preview_kind === "candidate" ? "候选预览" : slide.preview_kind === "sample" ? "样张预览" : "";
      return { key: ["running", "generating", "blocked", "failed"].includes(status) ? styleStatus(status) : "dirty", label: current + (slide.preview_path && previewLabel ? " · " + previewLabel : "") };
    }
    if (["blocked", "failed"].includes(status)) return { key: "blocked", label: STATUS_NAMES[status] };
    if (status === "waiting") return { key: "waiting", label: slide.preview_kind === "sample" ? "样张等待确认" : "等待确认" };
    if (slide.preview_kind === "final" && ["ready", "complete", "completed", "accepted"].includes(status)) {
      return { key: "complete", label: "正式页已产出" };
    }
    // A preview by itself never declares that generation or quality gates passed.
    if (slide.preview_kind === "candidate") return { key: styleStatus(status) === "complete" ? "running" : styleStatus(status), label: "候选已产出" };
    if (slide.preview_kind === "sample") return { key: styleStatus(status) === "complete" ? "waiting" : styleStatus(status), label: "样张可预览" };
    return { key: styleStatus(status), label: STATUS_NAMES[status] || "状态未知" };
  }

  function previewUrl(slide) {
    if (!slide || !text(slide.preview_path) || !Object.hasOwn(KIND_NAMES, slide.preview_kind)) return null;
    return "/api/preview?path=" + encodeURIComponent(slide.preview_path) + "&v=" + encodeURIComponent(text(slide.version));
  }

  function formatTime(value) {
    if (!value) return "尚无记录";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "时间未知" : new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
    }).format(date);
  }

  function normalizedState(data) {
    if (!data || typeof data !== "object" || data.schema_version !== 1 || typeof data.revision !== "string" || !Array.isArray(data.tasks) || !Array.isArray(data.slides)) {
      throw new Error("状态接口格式不兼容");
    }
    const slides = [];
    const seen = new Set();
    for (const slide of data.slides) {
      if (!slide || typeof slide !== "object" || typeof slide.id !== "string" || seen.has(slide.id)) continue;
      seen.add(slide.id);
      slides.push(slide);
    }
    return { ...data, slides, tasks: data.tasks.filter((task) => task && typeof task === "object"), warnings: Array.isArray(data.warnings) ? data.warnings.filter((warning) => typeof warning === "string") : [] };
  }

  function renderStages(state) {
    const list = element("stage-list");
    const byId = new Map(state.tasks.map((task) => [task.id, task]));
    const currentId = currentStageId(state.stage);
    const fragment = document.createDocumentFragment();
    for (const [index, [id, label]] of STAGES.entries()) {
      const task = byId.get(id);
      const rawStatus = task ? text(task.status, "unknown") : "pending";
      const status = styleStatus(rawStatus);
      const item = makeNode("li", "stage-item");
      item.dataset.stageId = id;
      item.dataset.status = status;
      if (currentId === id) item.setAttribute("aria-current", "step");
      const statusLabel = STATUS_NAMES[rawStatus] || "状态未知";
      item.setAttribute("aria-label", label + "：" + statusLabel);
      const marker = makeNode("span", "stage-marker", status === "complete" ? "✓" : String(index + 1).padStart(2, "0"));
      marker.setAttribute("aria-hidden", "true");
      const copy = makeNode("div", "stage-item-copy");
      const heading = makeNode("div", "stage-heading");
      heading.append(makeNode("span", "stage-name", task ? text(task.label, label) : label), makeNode("span", "stage-status", statusLabel));
      copy.append(heading);
      const detail = task ? text(task.detail, "等待读取此步骤的运行信息。") : "等待读取此步骤的运行信息。";
      copy.append(makeNode("span", "stage-detail", detail));
      item.title = [label, statusLabel, detail].filter(Boolean).join(" · ");
      item.append(marker, copy);
      fragment.append(item);
    }
    list.replaceChildren(fragment);
  }

  function renderOverview(state) {
    const status = text(state.status, "unknown");
    const mode = { guided: "引导模式", auto: "自动模式" }[state.mode];
    setText("deck-id", text(state.deck_id, "等待运行初始化") || "等待运行初始化");
    setText("page-title", status === "complete" ? "演示文稿已完成" : status === "blocked" ? "制作流程需要处理" : status === "waiting" ? "等待你的确认" : status === "running" ? "演示文稿制作中" : "演示文稿工作台");
    setText("run-status", STATUS_NAMES[status] || "状态未知");
    element("run-status").dataset.status = styleStatus(status);
    const currentId = currentStageId(state.stage);
    const currentTask = state.tasks.find((task) => task.id === currentId);
    const stageLabel = currentTask ? text(currentTask.label) : (STAGES.find(([id]) => id === currentId) || [null, "等待运行初始化"])[1];
    const stageDetail = currentTask ? text(currentTask.detail) : "";
    const description = [mode, stageLabel, checkpointLabel(state.stage), stageDetail].filter(Boolean).join(" · ");
    setText("stage-summary", description || "运行目录已连接，等待生成流程写入状态。");
    const progress = state.progress && typeof state.progress === "object" ? state.progress : {};
    const total = Number.isInteger(progress.total) && progress.total >= 0 ? progress.total : 0;
    const done = Number.isInteger(progress.done) && progress.done >= 0 ? Math.min(progress.done, total) : 0;
    setText("progress-done", String(done));
    setText("progress-total", total ? String(total) : "—");
    element("progress-fill").style.width = (total ? Math.min(100, done / total * 100) : 0) + "%";
    const track = element("progress-track");
    track.setAttribute("aria-valuenow", String(done));
    track.setAttribute("aria-valuemax", String(total || 1));
    track.setAttribute("aria-valuetext", total ? `已产出 ${done} / ${total} 张非脏正式页，不代表耗时进度` : "等待页面任务");
    setText("slide-count", state.slides.length ? `${state.slides.length} 个页面任务` : "等待页面");
    setText("page-task-count", String(state.slides.length));
    setText("updated-at", state.updated_at ? "产物更新时间 " + formatTime(state.updated_at) : "尚未读取到产物");
    element("updated-at").title = text(state.updated_at);
  }

  function renderNotice(state) {
    const notice = state.notice && typeof state.notice === "object" ? state.notice : null;
    const panel = element("notice-panel");
    const message = notice ? text(notice.message) : "";
    panel.hidden = !message;
    if (message) {
      const kind = text(notice.kind, "warning");
      const waiting = state.status === "waiting" || /waiting|pending|confirmation|interaction/.test(kind);
      panel.dataset.kind = kind;
      setText("notice-title", waiting ? "有一个节点等待你确认" : state.status === "blocked" || kind === "blocked" ? "流程已暂停，需要处理" : kind === "error" ? "运行状态暂时无法读取" : "需要关注");
      setText("notice-message", message);
      element("notice-help").hidden = !waiting;
    }
    element("warnings-section").hidden = !state.warnings.length;
    const fragment = document.createDocumentFragment();
    for (const warning of state.warnings) fragment.append(makeNode("li", "", warning));
    element("warnings-list").replaceChildren(fragment);
  }

  function renderSlideList(state) {
    const list = element("slide-list");
    const existing = new Map(Array.from(list.children).map((node) => [node.dataset.slideId, node]));
    const fragment = document.createDocumentFragment();
    for (const slide of state.slides) {
      const signature = JSON.stringify(slide);
      let card = existing.get(slide.id);
      if (!card || card.dataset.signature !== signature) {
        card = makeNode("button", "slide-card");
        card.type = "button";
        card.dataset.slideId = slide.id;
        card.dataset.signature = signature;
        const status = slideStatus(slide);
        card.setAttribute("aria-label", `${slide.id} ${text(slide.title, "未命名页面")}，${status.label}`);
        const thumbnail = makeNode("div", "slide-thumbnail");
        const url = previewUrl(slide);
        const placeholder = makeNode("span", "slide-thumbnail-placeholder", slide.id);
        placeholder.setAttribute("aria-hidden", "true");
        thumbnail.append(placeholder);
        if (url) {
          const img = makeNode("img");
          img.alt = "";
          img.loading = "lazy";
          img.decoding = "async";
          img.dataset.previewUrl = url;
          img.addEventListener("load", () => { ui.thumbnailFailures.delete(url); img.hidden = false; placeholder.hidden = true; });
          img.addEventListener("error", () => { ui.thumbnailFailures.add(url); img.hidden = true; placeholder.hidden = false; });
          img.src = url;
          thumbnail.append(img);
          placeholder.hidden = true;
        }
        if (url && (oldFinalPreview(slide) || slide.preview_kind !== "final")) thumbnail.append(makeNode("span", "thumbnail-kind", oldFinalPreview(slide) ? "旧版" : slide.preview_kind === "sample" ? "样张" : "候选"));
        const copy = makeNode("div", "slide-card-copy");
        copy.dataset.status = status.key;
        const title = makeNode("div", "slide-card-title");
        title.append(makeNode("span", "slide-card-id", slide.id), makeNode("span", "slide-card-name", text(slide.title, "未命名页面") || "未命名页面"));
        copy.append(title, makeNode("span", "slide-card-status", status.label));
        card.append(thumbnail, copy);
        card.addEventListener("click", () => selectSlide(slide.id));
      }
      card.setAttribute("aria-pressed", String(slide.id === ui.selectedId));
      fragment.append(card);
    }
    list.replaceChildren(fragment);
    element("slide-list-empty").hidden = state.slides.length > 0;
  }

  function selectedSlide() {
    return ui.state ? ui.state.slides.find((slide) => slide.id === ui.selectedId) || null : null;
  }

  function showPreviewFailure(url) {
    if (ui.previewUrl !== url) return;
    ui.failedPreviewUrl = url;
    element("slide-preview").hidden = true;
    element("preview-empty").hidden = false;
    setText("preview-empty-title", "预览暂时无法读取");
    setText("preview-empty-message", "文件可能正在更新。面板会自动重试，其他运行信息仍会继续刷新。");
    element("zoom-button").disabled = true;
  }

  function renderSelected() {
    const slide = selectedSlide();
    const slides = ui.state ? ui.state.slides : [];
    const index = slide ? slides.indexOf(slide) : -1;
    const status = slide ? slideStatus(slide) : { key: "unknown", label: "等待页面" };
    setText("selected-slide-id", slide ? slide.id : "—");
    setText("selected-slide-title", slide ? text(slide.title, "未命名页面") : "等待第一张幻灯片");
    setText("selected-slide-status", status.label);
    element("selected-slide-status").dataset.status = status.key;
    setText("selected-slide-detail", slide ? text(slide.detail) || "预览仅代表文件已产出，不代表质量检查已通过。" : "预览仅代表文件已产出，不代表质量检查已通过。");
    setText("selection-position", index < 0 ? "— / —" : `${index + 1} / ${slides.length}`);
    element("previous-slide").disabled = index <= 0;
    element("next-slide").disabled = index < 0 || index >= slides.length - 1;
    const url = previewUrl(slide);
    const image = element("slide-preview");
    image.alt = slide ? `${slide.id} ${text(slide.title, "幻灯片")} · ${KIND_NAMES[slide.preview_kind] || "预览"}${oldFinalPreview(slide) ? " · 旧版" : ""}` : "";
    element("zoom-button").disabled = !url;
    element("preview-empty").hidden = Boolean(url);
    image.hidden = !url;
    element("preview-kind").hidden = !url;
    setText("preview-kind", url ? KIND_NAMES[slide.preview_kind] : "");
    element("preview-dirty").hidden = !(url && slide.dirty);
    if (url && slide.dirty) setText("preview-dirty", oldFinalPreview(slide) ? "旧版预览 · 等待重新生成" : slide.preview_kind === "candidate" ? "新候选预览 · 正式页仍待更新" : "样张预览 · 正式页仍待更新");
    if (url !== ui.previewUrl) {
      ui.previewUrl = url;
      ui.failedPreviewUrl = null;
      if (url) image.src = url;
      else image.removeAttribute("src");
    }
    if (ui.failedPreviewUrl === url && url) showPreviewFailure(url);
    if (!url) {
      setText("preview-empty-title", slide ? "这一页正在准备" : "好内容，正在成形");
      setText("preview-empty-message", slide ? "当前尚无可预览的 SVG。完成安全写入后会自动显示。" : "当前尚无可预览的 SVG。产物写入后会自动出现在这里。");
    }
    if (element("preview-dialog").open) renderDialog();
  }

  function renderDialog() {
    const slide = selectedSlide();
    const slides = ui.state ? ui.state.slides : [];
    const index = slide ? slides.indexOf(slide) : -1;
    const url = previewUrl(slide);
    setText("dialog-title", slide ? `${slide.id} · ${text(slide.title, "未命名页面")}` : "等待页面");
    setText("dialog-detail", slide ? `${slideStatus(slide).label}${slide.updated_at ? " · " + formatTime(slide.updated_at) : ""}` : "");
    setText("dialog-position", index < 0 ? "— / —" : `${index + 1} / ${slides.length}`);
    element("dialog-previous").disabled = index <= 0;
    element("dialog-next").disabled = index < 0 || index >= slides.length - 1;
    const image = element("dialog-preview");
    image.hidden = !url;
    element("dialog-empty").hidden = Boolean(url);
    image.alt = slide ? `${slide.id} ${text(slide.title, "幻灯片")} · ${KIND_NAMES[slide.preview_kind] || "预览"}${oldFinalPreview(slide) ? " · 旧版" : ""}` : "";
    if (url !== ui.dialogUrl) {
      ui.dialogUrl = url;
      ui.failedDialogUrl = null;
      if (url) image.src = url;
      else image.removeAttribute("src");
    }
    if (ui.failedDialogUrl === url && url) {
      image.hidden = true;
      element("dialog-empty").hidden = false;
    } else if (!url) setText("dialog-empty", "此页尚无可预览的 SVG。");
  }

  function selectSlide(id, focusCard = false) {
    if (!ui.state || !ui.state.slides.some((slide) => slide.id === id)) return;
    ui.selectedId = id;
    for (const card of element("slide-list").children) {
      const active = card.dataset.slideId === id;
      card.setAttribute("aria-pressed", String(active));
      if (active && focusCard && !element("preview-dialog").open) {
        card.focus({ preventScroll: true });
        card.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    }
    renderSelected();
  }

  function navigate(offset) {
    if (!ui.state) return;
    const index = ui.state.slides.findIndex((slide) => slide.id === ui.selectedId);
    const next = ui.state.slides[index + offset];
    if (next) selectSlide(next.id, document.activeElement.classList.contains("slide-card"));
  }

  function applyState(state) {
    if (state.revision === ui.revision) return;
    const focused = document.activeElement;
    const focusedSlide = focused && focused.classList.contains("slide-card") ? focused.dataset.slideId : null;
    const list = element("slide-list");
    const stageList = element("stage-list");
    const scroll = { x: window.scrollX, y: window.scrollY, top: list.scrollTop, left: list.scrollLeft, stageTop: stageList.scrollTop, stageLeft: stageList.scrollLeft };
    ui.state = state;
    ui.revision = state.revision;
    if (!state.slides.some((slide) => slide.id === ui.selectedId)) ui.selectedId = state.slides.length ? state.slides[0].id : null;
    renderOverview(state);
    renderStages(state);
    renderNotice(state);
    renderSlideList(state);
    renderSelected();
    if (focusedSlide) {
      const replacement = Array.from(list.children).find((card) => card.dataset.slideId === focusedSlide);
      if (replacement) replacement.focus({ preventScroll: true });
    }
    list.scrollTop = scroll.top;
    list.scrollLeft = scroll.left;
    stageList.scrollTop = scroll.stageTop;
    stageList.scrollLeft = scroll.stageLeft;
    window.scrollTo(scroll.x, scroll.y);
    setText("live-announcement", `${STATUS_NAMES[state.status] || "状态已更新"}，已产出 ${element("progress-done").textContent} 张正式页。`);
  }

  function setConnection(connected, reason = "") {
    ui.connected = connected;
    const indicator = element("connection-status");
    indicator.dataset.state = connected ? "connected" : "disconnected";
    setText("connection-label", connected ? "本地服务已连接" : "连接中断 · 重试中");
    element("connection-alert").hidden = connected;
    if (!connected) {
      const previous = ui.lastSuccess ? "最近成功读取 " + formatTime(ui.lastSuccess) + "。" : "尚未成功读取运行状态。";
      setText("connection-message", previous + "正在自动重连，保留已显示内容。" + (reason ? " " + reason : ""));
    }
  }

  function retryFailedPreview() {
    if (ui.failedPreviewUrl && ui.failedPreviewUrl === ui.previewUrl) {
      const image = element("slide-preview");
      image.removeAttribute("src");
      image.src = ui.previewUrl;
    }
    if (ui.failedDialogUrl && ui.failedDialogUrl === ui.dialogUrl && element("preview-dialog").open) {
      const image = element("dialog-preview");
      image.removeAttribute("src");
      image.src = ui.dialogUrl;
    }
    if (ui.thumbnailFailures.size) {
      for (const image of element("slide-list").querySelectorAll("img")) {
        if (ui.thumbnailFailures.has(image.dataset.previewUrl)) {
          image.removeAttribute("src");
          image.src = image.dataset.previewUrl;
        }
      }
    }
  }

  async function poll() {
    if (ui.inFlight) return;
    window.clearTimeout(ui.timer);
    ui.inFlight = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    try {
      const response = await fetch("/api/state", { cache: "no-store", credentials: "same-origin", signal: controller.signal });
      if (!response.ok) throw new Error(`服务返回 HTTP ${response.status}`);
      const state = normalizedState(await response.json());
      ui.lastSuccess = new Date().toISOString();
      ui.failures = 0;
      setConnection(true);
      applyState(state);
      retryFailedPreview();
    } catch (error) {
      ui.failures += 1;
      const reason = error && error.name === "AbortError" ? "本次读取超时。" : "请确认本地面板服务仍在运行。";
      setConnection(false, reason);
    } finally {
      window.clearTimeout(timeout);
      ui.inFlight = false;
      // Serial requests prevent stale responses from overwriting newer revisions.
      ui.timer = window.setTimeout(poll, POLL_INTERVAL);
    }
  }

  const preview = element("slide-preview");
  preview.addEventListener("error", () => { if (ui.previewUrl) showPreviewFailure(ui.previewUrl); });
  preview.addEventListener("load", () => {
    if (!ui.previewUrl) return;
    ui.failedPreviewUrl = null;
    preview.hidden = false;
    element("preview-empty").hidden = true;
    element("zoom-button").disabled = false;
  });
  element("dialog-preview").addEventListener("error", () => {
    ui.failedDialogUrl = ui.dialogUrl;
    element("dialog-preview").hidden = true;
    element("dialog-empty").hidden = false;
    setText("dialog-empty", "预览暂时无法读取，文件可能正在更新。");
  });
  element("dialog-preview").addEventListener("load", () => {
    ui.failedDialogUrl = null;
    element("dialog-preview").hidden = false;
    element("dialog-empty").hidden = true;
  });
  element("previous-slide").addEventListener("click", () => navigate(-1));
  element("next-slide").addEventListener("click", () => navigate(1));
  element("dialog-previous").addEventListener("click", () => navigate(-1));
  element("dialog-next").addEventListener("click", () => navigate(1));
  element("zoom-button").addEventListener("click", () => {
    const dialog = element("preview-dialog");
    if (!previewUrl(selectedSlide()) || dialog.open) return;
    renderDialog();
    dialog.showModal();
    element("close-dialog").focus();
  });
  element("close-dialog").addEventListener("click", () => element("preview-dialog").close());
  element("preview-dialog").addEventListener("click", (event) => {
    if (event.target !== element("preview-dialog")) return;
    const rect = event.target.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
  });
  element("retry-button").addEventListener("click", poll);
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target.matches("input, textarea, select, [contenteditable='true']")) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      navigate(event.key === "ArrowLeft" ? -1 : 1);
    }
    if (event.key === "Escape" && element("preview-dialog").open) {
      event.preventDefault();
      element("preview-dialog").close();
    }
  });
  window.addEventListener("online", poll);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  renderStages({ tasks: [], stage: null });
  poll();
})();
