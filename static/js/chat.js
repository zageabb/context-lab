const chatContext = JSON.parse(document.body.dataset.chatContext || "{}");
const chatHistory = document.getElementById("chat-history");
const chatForm = document.getElementById("chat-form");
const uploadForm = document.getElementById("chat-upload-form");
const clearButton = document.getElementById("chat-clear-button");
let historyLoaded = false;

function buildChatContext() {
  const context = { ...chatContext };
  const selectedIds = Array.from(document.querySelectorAll(".extraction-document-checkbox:checked"))
    .map((checkbox) => Number(checkbox.value))
    .filter((value) => Number.isFinite(value));
  if (selectedIds.length) {
    context.selected_document_ids = selectedIds;
  } else {
    delete context.selected_document_ids;
  }
  return context;
}

function appendMessage(role, text, steps = []) {
  if (!chatHistory) return;
  const node = document.createElement("div");
  node.className = `chat-message ${role}`;
  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.innerHTML = renderMarkdown(text);
  node.appendChild(body);
  if (steps.length) {
    if (role === "assistant") {
      const thinking = document.createElement("details");
      thinking.className = "chat-thinking";
      thinking.open = true;
      const summary = document.createElement("summary");
      summary.textContent = "Thinking";
      thinking.appendChild(summary);
      const detail = document.createElement("div");
      detail.className = "chat-steps";
      detail.innerHTML = renderMarkdown(steps.map((step) => `- ${step}`).join("\n"));
      thinking.appendChild(detail);
      node.appendChild(thinking);
    } else {
      const detail = document.createElement("div");
      detail.className = "chat-steps";
      detail.innerHTML = renderMarkdown(steps.map((step) => `- ${step}`).join("\n"));
      node.appendChild(detail);
    }
  }
  chatHistory.appendChild(node);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatInlineMarkdown(value) {
  let formatted = escapeHtml(value);
  formatted = formatted.replace(/`([^`]+)`/g, "<code>$1</code>");
  formatted = formatted.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  formatted = formatted.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  formatted = formatted.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return formatted;
}

function renderMarkdown(text) {
  const source = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!source) return "";

  const lines = source.split("\n");
  const html = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];
  let inCodeBlock = false;
  let codeLines = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push(`<p>${paragraph.map((line) => formatInlineMarkdown(line)).join("<br>")}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listType || !listItems.length) return;
    html.push(`<${listType}>${listItems.map((item) => `<li>${formatInlineMarkdown(item)}</li>`).join("")}</${listType}>`);
    listType = null;
    listItems = [];
  }

  function flushCodeBlock() {
    if (!inCodeBlock) return;
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    inCodeBlock = false;
    codeLines = [];
  }

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      if (inCodeBlock) {
        flushCodeBlock();
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.*)$/);
    const orderedMatch = line.match(/^\s*\d+\.\s+(.*)$/);

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    if (unorderedMatch) {
      flushParagraph();
      if (listType && listType !== "ul") flushList();
      listType = "ul";
      listItems.push(unorderedMatch[1]);
      continue;
    }

    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") flushList();
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  flushCodeBlock();

  return html.join("");
}

async function loadHistory() {
  if (!chatHistory || historyLoaded) return;
  const response = await fetch("/chat/history", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context: buildChatContext() }),
  });
  const payload = await response.json();
  if (payload.messages?.length) {
    chatHistory.innerHTML = "";
    payload.messages.forEach((message) => appendMessage(message.role, message.message_text, message.intermediate_steps || []));
  }
  historyLoaded = true;
}

loadHistory();

if (clearButton) {
  clearButton.addEventListener("click", async () => {
    const confirmed = window.confirm("Clear this saved chat history for the current context?");
    if (!confirmed) return;
    const response = await fetch("/chat/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: buildChatContext() }),
    });
    const payload = await response.json();
    chatHistory.innerHTML = "";
    appendMessage("assistant", payload.message || "Chat cleared.");
    historyLoaded = false;
  });
}

if (chatForm) {
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const messageField = document.getElementById("chat-message");
    const submitButton = chatForm.querySelector("button[type='submit']");
    const message = messageField.value.trim();
    if (!message) return;
    appendMessage("user", message);
    appendMessage("system", "Working through the current instructions, selected documents, and retrieval context.");
    messageField.value = "";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.dataset.originalText = submitButton.textContent;
      submitButton.textContent = "Working...";
    }
    const response = await fetch("/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context: buildChatContext() }),
    });
    const payload = await response.json();
    appendMessage("assistant", payload.message || "No response.", payload.intermediate_steps || []);
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = submitButton.dataset.originalText || "Send";
    }
  });
}

if (uploadForm) {
  uploadForm.addEventListener("change", async () => {
    const input = document.getElementById("chat-file-input");
    if (!input.files.length) return;
    const formData = new FormData();
    formData.append("file", input.files[0]);
    formData.append("context", JSON.stringify(buildChatContext()));
    const response = await fetch("/chat/upload", { method: "POST", body: formData });
    const payload = await response.json();
    appendMessage("assistant", payload.message || "Upload finished.");
    input.value = "";
  });
}

document.querySelector("[data-chat-toggle]")?.addEventListener("click", () => {
  document.querySelector(".chat-panel")?.classList.toggle("is-collapsed");
});
