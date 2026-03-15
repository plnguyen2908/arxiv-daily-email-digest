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
  digestContainer: document.getElementById("digestContainer"),
  topicEditorTemplate: document.getElementById("topicEditorTemplate"),
  topicBlockTemplate: document.getElementById("topicBlockTemplate"),
  paperCardTemplate: document.getElementById("paperCardTemplate"),
  newTopicKey: document.getElementById("newTopicKey"),
  newTopicLabel: document.getElementById("newTopicLabel"),
  newTopicKeyword: document.getElementById("newTopicKeyword"),
  addTopicBtn: document.getElementById("addTopicBtn"),
};

let currentTopics = [];
let activeTopicKey = null;

function setText(el, value) {
  if (!el) {
    return;
  }
  el.textContent = value;
}

function setStatus(message, isError = false) {
  if (!dom.statusText) {
    return;
  }
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
  setText(dom.healthDataUsed, getPretty(payload, "data_used"));
  setText(dom.healthDataLimit, getPretty(payload, "max_data"));
  setText(dom.healthDiskUsed, getPretty(payload, "disk_used"));
  setText(dom.healthDiskFree, getPretty(payload, "disk_free"));
  setText(dom.healthDiskTotal, getPretty(payload, "disk_total"));
  setText(dom.healthDiskPercent, `${Number(payload.disk_used_percent || 0).toFixed(2)}%`);
}

function renderKeywordChips(container, keywords) {
  container.innerHTML = "";
  (keywords || []).forEach((kw) => {
    const chip = document.createElement("span");
    chip.className = "keyword-chip";
    chip.textContent = kw;
    container.appendChild(chip);
  });
}

async function addSubKeyword(topicKey, subkeyword, password) {
  const payload = await api(`/api/topics/${encodeURIComponent(topicKey)}/subkeyword`, {
    method: "POST",
    body: JSON.stringify({ subkeyword, password }),
  });
  currentTopics = payload.topics || [];
  renderTopicsEditor(currentTopics);
}

function renderTopicsEditor(topics) {
  if (!dom.topicsEditor || !dom.topicEditorTemplate) {
    return;
  }

  dom.topicsEditor.innerHTML = "";
  topics.forEach((topic) => {
    const node = dom.topicEditorTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.key = topic.key;
    node.querySelector(".topic-title").textContent = topic.label || topic.key;
    node.querySelector(".topic-meta").textContent = `key: ${topic.key} | categories: ${(topic.categories || []).join(", ")}`;

    const chipList = node.querySelector(".keyword-chip-list");
    renderKeywordChips(chipList, topic.keywords || []);

    const subInput = node.querySelector(".subkeyword-input");
    const passInput = node.querySelector(".subkeyword-password");
    const addBtn = node.querySelector(".add-subkeyword-btn");

    addBtn.addEventListener("click", async () => {
      const subkeyword = (subInput.value || "").trim();
      const password = (passInput.value || "").trim();
      if (!subkeyword) {
        setStatus("Enter a sub-keyword first.", true);
        return;
      }
      if (!password) {
        setStatus("Password is required to add sub-keyword.", true);
        return;
      }

      try {
        await addSubKeyword(topic.key, subkeyword, password);
        subInput.value = "";
        passInput.value = "";
        setStatus(`Added sub-keyword to ${topic.label || topic.key}.`);
      } catch (error) {
        setStatus(error.message, true);
      }
    });

    dom.topicsEditor.appendChild(node);
  });
}

function renderDigest(payload) {
  if (!dom.digestContainer) {
    return;
  }

  if (dom.digestTabs) {
    dom.digestTabs.innerHTML = "";
  }
  dom.digestContainer.innerHTML = "";

  const stats = payload.stats || { total: 0, done: 0, remaining: 0, cleared: true };
  setText(dom.progressText, `Date ${payload.date} | total ${stats.total} | done ${stats.done} | remaining ${stats.remaining}`);

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
    const unreadCount = (topic.papers || []).filter((p) => !p.done).length;
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = `digest-tab${topic.key === activeTopicKey ? " active" : ""}`;
    tab.textContent = `${topic.label} (${unreadCount})`;
    tab.addEventListener("click", () => {
      activeTopicKey = topic.key;
      renderDigest(payload);
    });
    if (dom.digestTabs) {
      dom.digestTabs.appendChild(tab);
    }
  });

  const selectedTopic = topics.find((topic) => topic.key === activeTopicKey) || topics[0];
  const unreadPapers = (selectedTopic.papers || []).filter((paper) => !paper.done);
  const block = dom.topicBlockTemplate.content.firstElementChild.cloneNode(true);
  block.querySelector(".topic-heading").textContent = `${selectedTopic.label} (${unreadPapers.length})`;
  const paperList = block.querySelector(".paper-list");

  unreadPapers.forEach((paper) => {
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

  if (unreadPapers.length === 0) {
    const msg = document.createElement("div");
    msg.className = "cleared";
    msg.textContent = `No unread papers left for ${selectedTopic.label}.`;
    paperList.appendChild(msg);
  }

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

async function addBigTopic() {
  const key = (dom.newTopicKey?.value || "").trim();
  const label = (dom.newTopicLabel?.value || "").trim();
  const firstKeyword = (dom.newTopicKeyword?.value || "").trim();

  if (!key) {
    setStatus("Big topic key is required.", true);
    return;
  }
  if (!firstKeyword) {
    setStatus("First sub-keyword is required.", true);
    return;
  }

  const payload = await api("/api/topics", {
    method: "POST",
    body: JSON.stringify({
      key,
      label,
      first_keyword: firstKeyword,
      categories: ["cs.*"],
    }),
  });

  currentTopics = payload.topics || [];
  renderTopicsEditor(currentTopics);

  if (dom.newTopicKey) dom.newTopicKey.value = "";
  if (dom.newTopicLabel) dom.newTopicLabel.value = "";
  if (dom.newTopicKeyword) dom.newTopicKeyword.value = "";

  setStatus("Added new big topic.");
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
    setStatus(`No papers found on ${payload.requested_date}. Fetched ${resolvedDate} instead (${fallback} day fallback).`);
  } else {
    setStatus(`Fetched digest for ${resolvedDate}.`);
  }

  if (dom.datePicker) {
    dom.datePicker.value = resolvedDate;
  }
  await loadHealth();
}

function wireEvents() {
  if (dom.addTopicBtn) {
    dom.addTopicBtn.addEventListener("click", async () => {
      try {
        await addBigTopic();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  }

  if (dom.fetchToday) {
    dom.fetchToday.addEventListener("click", async () => {
      try {
        await fetchDigest(todayIso());
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  }

  if (dom.fetchDate) {
    dom.fetchDate.addEventListener("click", async () => {
      try {
        const value = dom.datePicker?.value || "";
        if (!value) {
          setStatus("Select a date first.", true);
          return;
        }
        await fetchDigest(value);
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  }

  if (dom.loadDate) {
    dom.loadDate.addEventListener("click", async () => {
      try {
        const value = dom.datePicker?.value || "";
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
}

async function bootstrap() {
  if (dom.datePicker) {
    dom.datePicker.value = todayIso();
  }

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
