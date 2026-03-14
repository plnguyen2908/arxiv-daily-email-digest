const DEFAULT_API_BASE = "http://localhost:8000";

const dom = {
  apiBase: document.getElementById("apiBase"),
  saveApiBase: document.getElementById("saveApiBase"),
  datePicker: document.getElementById("datePicker"),
  fetchToday: document.getElementById("fetchToday"),
  fetchDate: document.getElementById("fetchDate"),
  loadDate: document.getElementById("loadDate"),
  statusText: document.getElementById("statusText"),
  progressText: document.getElementById("progressText"),
  topicsEditor: document.getElementById("topicsEditor"),
  saveTopics: document.getElementById("saveTopics"),
  digestContainer: document.getElementById("digestContainer"),
  topicEditorTemplate: document.getElementById("topicEditorTemplate"),
  topicBlockTemplate: document.getElementById("topicBlockTemplate"),
  paperCardTemplate: document.getElementById("paperCardTemplate"),
};

let currentTopics = [];
let currentDigest = null;

function setStatus(message, isError = false) {
  dom.statusText.textContent = message;
  dom.statusText.style.color = isError ? "#b42318" : "#4d6076";
}

function apiBase() {
  return (dom.apiBase.value || DEFAULT_API_BASE).replace(/\/$/, "");
}

async function api(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
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
  dom.digestContainer.innerHTML = "";

  const stats = payload.stats || { total: 0, done: 0, remaining: 0, cleared: true };
  dom.progressText.textContent = `Date ${payload.date} | total ${stats.total} | done ${stats.done} | remaining ${stats.remaining}`;

  if (stats.cleared) {
    const msg = document.createElement("div");
    msg.className = "cleared";
    msg.textContent = `Date ${payload.date} is clear. No remaining papers.`;
    dom.digestContainer.appendChild(msg);
  }

  (payload.topics || []).forEach((topic) => {
    const block = dom.topicBlockTemplate.content.firstElementChild.cloneNode(true);
    block.querySelector(".topic-heading").textContent = `${topic.label} (${(topic.papers || []).length})`;
    const paperList = block.querySelector(".paper-list");

    (topic.papers || []).forEach((paper) => {
      const card = dom.paperCardTemplate.content.firstElementChild.cloneNode(true);
      const checkbox = card.querySelector(".paper-check");
      checkbox.checked = !!paper.done;
      checkbox.addEventListener("change", async () => {
        try {
          await api(`/api/digest/${payload.date}/toggle`, {
            method: "POST",
            body: JSON.stringify({
              topic_key: topic.key,
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

      card.querySelector(".paper-summary").textContent = paper.summary || "No summary.";
      card.querySelector(".paper-abstract").textContent = paper.abstract || "No abstract.";
      card.querySelector(".paper-meta").textContent = `arXiv: ${paper.arxiv_id} | score: ${paper.score}`;

      paperList.appendChild(card);
    });

    dom.digestContainer.appendChild(block);
  });
}

async function loadTopics() {
  const payload = await api("/api/topics");
  currentTopics = payload.topics || [];
  renderTopicsEditor(currentTopics);
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
}

function wireEvents() {
  dom.saveApiBase.addEventListener("click", () => {
    localStorage.setItem("arxiv_api_base", dom.apiBase.value.trim() || DEFAULT_API_BASE);
    setStatus("Saved API URL.");
  });

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
  const savedApi = localStorage.getItem("arxiv_api_base") || DEFAULT_API_BASE;
  dom.apiBase.value = savedApi;
  dom.datePicker.value = todayIso();

  wireEvents();

  try {
    await loadTopics();
    setStatus("Ready. Fetch today or choose a date.");
  } catch (error) {
    setStatus(`Could not load topics: ${error.message}`, true);
  }
}

bootstrap();
