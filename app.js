const API_BASE = "https://136.113.34.120.sslip.io";

const dom = {
  datePicker: document.getElementById("datePicker"),
  fetchToday: document.getElementById("fetchToday"),
  fetchDate: document.getElementById("fetchDate"),
  loadDate: document.getElementById("loadDate"),
  statusText: document.getElementById("statusText"),
  healthDataUsed: document.getElementById("healthDataUsed"),
  healthDataLimit: document.getElementById("healthDataLimit"),
  healthDiskUsed: document.getElementById("healthDiskUsed"),
  healthDiskFree: document.getElementById("healthDiskFree"),
  healthDiskTotal: document.getElementById("healthDiskTotal"),
  healthDiskPercent: document.getElementById("healthDiskPercent"),
  progressText: document.getElementById("progressText"),
  digestTabs: document.getElementById("digestTabs"),
  topicsEditor: document.getElementById("topicsEditor"),
  saveTopics: document.getElementById("saveTopics"),
  digestContainer: document.getElementById("digestContainer"),
  topicEditorTemplate: document.getElementById("topicEditorTemplate"),
  topicBlockTemplate: document.getElementById("topicBlockTemplate"),
  paperCardTemplate: document.getElementById("paperCardTemplate"),
};

let currentTopics = [];
let currentDigest = null;
let activeTopicKey = null;

function setStatus(message, isError = false) {
  dom.statusText.textContent = message;
  dom.statusText.style.color = isError ? "#b42318" : "#4d6076";
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return payload;
}

function todayIso() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function toPrettyBytes(value) {
  const size = Math.max(0, Number(value || 0));
  if (size >= 1024 ** 3) {
    return `${(size / 1024 ** 3).toFixed(2)} GB`;
  }
  if (size >= 1024 ** 2) {
    return `${(size / 1024 ** 2).toFixed(2)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(2)} KB`;
  }
  return `${Math.round(size)} B`;
}

function getPretty(payload, keyPrefix) {
  if (payload[`${keyPrefix}_pretty`]) {
    return payload[`${keyPrefix}_pretty`];
  }
  return toPrettyBytes(payload[`${keyPrefix}_bytes`]);
}

function renderHealth(payload) {
  dom.healthDataUsed.textContent = getPretty(payload, "data_used");
  dom.healthDataLimit.textContent = getPretty(payload, "max_data");
  dom.healthDiskUsed.textContent = getPretty(payload, "disk_used");
  dom.healthDiskFree.textContent = getPretty(payload, "disk_free");
  dom.healthDiskTotal.textContent = getPretty(payload, "disk_total");
  dom.healthDiskPercent.textContent = `${Number(payload.disk_used_percent || 0).toFixed(2)}%`;
}

function renderTopicsEditor(topics) {
  dom.topicsEditor.innerHTML = "";
  topics.forEach((topic) => {
    const node = dom.topicEditorTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.key = topic.key;
    node.querySelector(".topic-title").textContent = topic.label || topic.key;
    node.querySelector(".topic-meta").textContent = `key: ${topic.key} | categories: ${(topic.categories || []).join(", ")}`;
    node.querySelector(".keywords-input").value = (topic.keywords || []).join(", ");
    dom.topicsEditor.appendChild(node);
  });
}

function editorTopicsPayload() {
  return Array.from(dom.topicsEditor.querySelectorAll(".topic-edit-card")).map((card) => {
    const key = card.dataset.key;
    const current = currentTopics.find((t) => t.key === key) || {};
    const raw = card.querySelector(".keywords-input").value;
    const keywords = raw
      .split(",")
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean);

    return {
      key,
      label: current.label || key,
      keywords,
      categories: current.categories || ["cs.*"],
      must_have_phrases: current.must_have_phrases || [],
      exclude_keywords: current.exclude_keywords || [],
    };
  });
}

function renderDigest(payload) {
  currentDigest = payload;
  dom.digestTabs.innerHTML = "";
  dom.digestContainer.innerHTML = "";

  const stats = payload.stats || { total: 0, done: 0, remaining: 0, cleared: true };
  dom.progressText.textContent = `Date ${payload.date} | total ${stats.total} | done ${stats.done} | remaining ${stats.remaining}`;

  if (stats.cleared) {
    const msg = document.createElement("div");
    msg.className = "cleared";
    msg.textContent = `Date ${payload.date} is clear. No remaining papers.`;
    dom.digestContainer.appendChild(msg);
    activeTopicKey = null;
    return;
  }

  const topics = payload.topics || [];
  if (topics.length === 0) {
    const msg = document.createElement("div");
    msg.className = "cleared";
    msg.textContent = `No topics found for ${payload.date}.`;
    dom.digestContainer.appendChild(msg);
    activeTopicKey = null;
    return;
  }

  if (!activeTopicKey || !topics.some((t) => t.key === activeTopicKey)) {
    activeTopicKey = topics[0].key;
  }

  topics.forEach((topic) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `digest-tab${topic.key === activeTopicKey ? " active" : ""}`;
    tab.textContent = `${topic.label} (${(topic.papers || []).length})`;
    tab.addEventListener("click", () => {
      activeTopicKey = topic.key;
      renderDigest(payload);
    });
    dom.digestTabs.appendChild(tab);
  });

  const selectedTopic = topics.find((topic) => topic.key === activeTopicKey) || topics[0];
  const block = dom.topicBlockTemplate.content.firstElementChild.cloneNode(true);
  block.querySelector(".topic-heading").textContent = `${selectedTopic.label} (${(selectedTopic.papers || []).length})`;
  const paperList = block.querySelector(".paper-list");

  (selectedTopic.papers || []).forEach((paper) => {
    const card = dom.paperCardTemplate.content.firstElementChild.cloneNode(true);
    const checkbox = card.querySelector(".paper-check");
    checkbox.checked = !!paper.done;
    checkbox.addEventListener("change", async () => {
      try {
        await api(`/api/digest/${payload.date}/toggle`, {
          method: "POST",
          body: JSON.stringify({
            topic_key: selectedTopic.key,
            arxiv_id: paper.arxiv_id,
            done: checkbox.checked,
          }),
        });
        await loadDigest(payload.date);
      } catch (error) {
        checkbox.checked = !checkbox.checked;
        setStatus(error.message, true);
      }
    });

    const titleLink = card.querySelector(".paper-title");
    titleLink.textContent = paper.title;
    titleLink.href = paper.paper_url;

    card.querySelector(".paper-abstract").textContent = paper.abstract || "No abstract.";
    card.querySelector(".paper-meta").textContent = `arXiv: ${paper.arxiv_id} | score: ${paper.score}`;

    paperList.appendChild(card);
  });

  dom.digestContainer.appendChild(block);
}

async function loadTopics() {
  const payload = await api("/api/topics");
  currentTopics = payload.topics || [];
  renderTopicsEditor(currentTopics);
}

async function loadHealth() {
  const payload = await api("/api/health");
  renderHealth(payload);
}

async function saveTopics() {
  const topics = editorTopicsPayload();
  const payload = await api("/api/topics", {
    method: "PUT",
    body: JSON.stringify({ topics }),
  });
  currentTopics = payload.topics || [];
  renderTopicsEditor(currentTopics);
  setStatus("Keywords updated.");
}

async function loadDigest(digestDate) {
  const payload = await api(`/api/digest/${digestDate}`);
  renderDigest(payload);
  setStatus(`Loaded digest for ${digestDate}.`);
}

async function fetchDigest(requestDate = null) {
  const requestPayload = {
    date: requestDate,
    force: true,
  };
  const payload = await api("/api/fetch", {
    method: "POST",
    body: JSON.stringify(requestPayload),
  });

  const resolvedDate = payload.resolved_date;
  renderDigest(payload.digest);

  const fallback = Number(payload.fallback_days || 0);
  if (fallback > 0) {
    setStatus(
      `No papers found on ${payload.requested_date}. Fetched ${resolvedDate} instead (${fallback} day fallback).`
    );
  } else {
    setStatus(`Fetched digest for ${resolvedDate}.`);
  }

  dom.datePicker.value = resolvedDate;
  await loadHealth();
}

function wireEvents() {
  dom.saveTopics.addEventListener("click", async () => {
    try {
      await saveTopics();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  dom.fetchToday.addEventListener("click", async () => {
    try {
      await fetchDigest(todayIso());
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  dom.fetchDate.addEventListener("click", async () => {
    try {
      const value = dom.datePicker.value;
      if (!value) {
        setStatus("Select a date first.", true);
        return;
      }
      await fetchDigest(value);
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  dom.loadDate.addEventListener("click", async () => {
    try {
      const value = dom.datePicker.value;
      if (!value) {
        setStatus("Select a date first.", true);
        return;
      }
      await loadDigest(value);
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

async function bootstrap() {
  dom.datePicker.value = todayIso();

  wireEvents();

  try {
    await loadTopics();
    await loadHealth();
    setStatus("Ready. Fetch today or choose a date.");
  } catch (error) {
    setStatus(`Could not load topics: ${error.message}`, true);
  }
}

bootstrap();
