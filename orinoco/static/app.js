// DOM references and shared UI state. Keep element IDs in sync with static/index.html.
const connection = document.getElementById("connection-status");
const modelTitle = document.getElementById("model-title");
const modelDescription = document.getElementById("model-description");
const modelPill = document.getElementById("model-pill");
const accountAction = document.getElementById("account-action");
const userName = document.getElementById("user-name");
const userRole = document.getElementById("user-role");
const userAvatar = document.getElementById("user-avatar");
const loginDialog = document.getElementById("login-dialog");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const loginSubmit = document.getElementById("login-submit");
const newChatButton = document.getElementById("new-chat");
const conversationList = document.getElementById("conversation-list");
const mobileConversations = document.getElementById("mobile-conversations");
const chatThread = document.getElementById("chat-thread");
const chatInput = document.getElementById("chat-input");
const chatForm = document.getElementById("chat-form");
const sendButton = document.getElementById("send-message");
const webSearchToggle = document.getElementById("chat-web-search");
const chatHint = document.getElementById("chat-hint");
const settingsButton = document.getElementById("settings-button");
const settingsDialog = document.getElementById("settings-dialog");
const adminTools = document.getElementById("admin-tools");
const memoriesLink = document.getElementById("memories-link");
const documentsLink = document.getElementById("documents-link");
const chatLink = document.getElementById("chat-link");
const chatView = document.querySelector(".welcome");
const documentsView = document.getElementById("documents-view");
const researchLink = document.getElementById("research-link");
const researchView = document.getElementById("research-view");
const sharedDocumentTools = document.getElementById("shared-document-tools");
let currentUser = null;
let currentConversationId = null;
let sendingMessage = false;

// Search results are external data. Only create clickable links for absolute HTTP(S) URLs.
function safeExternalUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) return null;
    if (parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

// Service status is informational; readiness is checked by the server's /readyz endpoint.
async function refreshStatus() {
  try {
    const response = await fetch("/readyz", { headers: { Accept: "application/json" } });
    const result = await response.json();

    if (response.ok && result.status === "ready") {
      connection.className = "connection ready";
      connection.lastElementChild.textContent = "Local model ready";
      modelTitle.textContent = "Your local AI is ready";
      modelDescription.textContent = result.model + " is installed and responding.";
      modelPill.textContent = "Ready";
      modelPill.className = "status-pill ready";
      return;
    }

    if (result.status === "model_missing") {
      connection.className = "connection error";
      connection.lastElementChild.textContent = "Model not installed";
      modelTitle.textContent = "The model still needs setting up";
      modelDescription.textContent = "Orinoco is running, but " + result.model + " is not installed yet.";
      modelPill.textContent = "Model missing";
      modelPill.className = "status-pill error";
      return;
    }

    throw new Error("Local model service is not ready");
  } catch {
    connection.className = "connection error";
    connection.lastElementChild.textContent = "Model service unavailable";
    modelTitle.textContent = "Still getting things ready";
    modelDescription.textContent = "Orinoco cannot reach its local model service yet.";
    modelPill.textContent = "Offline";
    modelPill.className = "status-pill error";
  }
}

// Apply the authenticated/anonymous UI state and clear account-specific content on sign-out.
function showAccount(user) {
  currentUser = user;
  if (user) {
    settingsButton.disabled = false;
    adminTools.hidden = user.role !== "admin";
    sharedDocumentTools.hidden = user.role !== "admin";
    memoriesLink.classList.remove("unavailable");
    memoriesLink.setAttribute("aria-disabled", "false");
    documentsLink.classList.remove("unavailable");
    documentsLink.setAttribute("aria-disabled", "false");
    researchLink.classList.remove("unavailable");
    researchLink.setAttribute("aria-disabled", "false");
    userName.textContent = user.username;
    userRole.textContent = user.role === "admin" ? "Administrator" : "Standard account";
    userAvatar.textContent = user.username.charAt(0).toUpperCase();
    accountAction.textContent = "Sign out";
    accountAction.dataset.authenticated = "true";
    newChatButton.disabled = false;
    chatInput.disabled = false;
    sendButton.disabled = false;
    webSearchToggle.disabled = false;
    chatInput.placeholder = "Message Orinoco…";
    chatHint.textContent = "Your conversation is private and saved to your account.";
  } else {
    settingsButton.disabled = true;
    adminTools.hidden = true;
    sharedDocumentTools.hidden = true;
    memoriesLink.classList.add("unavailable");
    memoriesLink.setAttribute("aria-disabled", "true");
    documentsLink.classList.add("unavailable");
    documentsLink.setAttribute("aria-disabled", "true");
    researchLink.classList.add("unavailable");
    researchLink.setAttribute("aria-disabled", "true");
    userName.textContent = "Not signed in";
    userRole.textContent = "Your private workspace";
    userAvatar.textContent = "?";
    accountAction.textContent = "Sign in";
    delete accountAction.dataset.authenticated;
    newChatButton.disabled = true;
    chatInput.disabled = true;
    sendButton.disabled = true;
    webSearchToggle.disabled = true;
    webSearchToggle.checked = false;
    chatInput.placeholder = "Sign in to start a private conversation…";
    chatHint.textContent = "Sign in to start a private conversation. Your chats are saved to your own account.";
    currentConversationId = null;
    showChatView();
    clearThread();
    conversationList.replaceChildren();
    mobileConversations.replaceChildren(new Option("Recent chats", ""));
    document.getElementById("private-document-list").replaceChildren();
    document.getElementById("shared-document-list").replaceChildren();
  }
}

function clearThread() {
  chatThread.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "chat-empty";
  const spark = document.createElement("span");
  spark.className = "empty-spark";
  spark.textContent = "✳";
  spark.setAttribute("aria-hidden", "true");
  const heading = document.createElement("strong");
  heading.textContent = "Your next idea starts here.";
  const description = document.createElement("span");
  description.textContent = "Ask Orinoco a question, or just say hello.";
  empty.append(spark, heading, description);
  chatThread.append(empty);
}

function appendMessage(role, content, state = "") {
  const empty = chatThread.querySelector(".chat-empty");
  if (empty) empty.remove();

  const message = document.createElement("div");
  message.className = "chat-message " + role + (state ? " " + state : "");
  const label = document.createElement("span");
  label.className = "chat-message-role";
  label.textContent = state === "notice" ? "MEMORY" : (role === "user" ? "You" : "Orinoco");
  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.textContent = content;
  message.append(label, body);
  chatThread.append(message);
  chatThread.scrollTop = chatThread.scrollHeight;
  return message;
}

// Conversation list and history are always fetched from account-scoped API endpoints.
async function refreshConversations() {
  if (accountAction.dataset.authenticated !== "true") return;
  try {
    const response = await fetch("/api/conversations", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const result = await response.json();
    conversationList.replaceChildren();
    mobileConversations.replaceChildren(new Option("Recent chats", ""));

    if (!result.conversations.length) {
      const empty = document.createElement("div");
      empty.className = "conversation-empty";
      empty.textContent = "No saved chats yet.";
      conversationList.append(empty);
      return;
    }

    for (const item of result.conversations) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "conversation-item" +
        (item.id === currentConversationId ? " active" : "");
      button.textContent = item.title;
      button.title = item.title;
      button.addEventListener("click", () => loadConversation(item.id));
      conversationList.append(button);
      const option = new Option(item.title, String(item.id));
      if (item.id === currentConversationId) option.selected = true;
      mobileConversations.add(option);
    }
  } catch {
    conversationList.replaceChildren();
  }
}

async function loadConversation(id) {
  try {
    const response = await fetch("/api/conversations/" + encodeURIComponent(id), {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("Could not load that conversation.");
    const conversation = await response.json();
    currentConversationId = conversation.id;
    chatThread.replaceChildren();
    for (const message of conversation.messages) {
      appendMessage(message.role, message.content);
    }
    if (!conversation.messages.length) clearThread();
    await refreshConversations();
  } catch (error) {
    appendMessage("assistant", error.message || "Could not load that conversation.", "error");
  }
}

// All browser mutations obtain a session-bound CSRF token before sending a request.
async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Could not start a secure session. Refresh and try again.");
  const result = await response.json();
  return result.csrf_token;
}

async function refreshAccount() {
  try {
    const response = await fetch("/api/auth/me", { headers: { Accept: "application/json" } });
    const result = await response.json();
    showAccount(result.authenticated ? result.user : null);
    if (result.authenticated) await refreshConversations();
  } catch {
    showAccount(null);
  }
}

// Sign-in and sign-out flows. The server remains authoritative for session validity.
accountAction.addEventListener("click", async () => {
  if (accountAction.dataset.authenticated === "true") {
    try {
      const csrf = await getCsrfToken();
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!response.ok) throw new Error("Sign-out failed");
      showAccount(null);
    } catch {
      window.alert("Orinoco could not sign you out. Please refresh and try again.");
    }
    return;
  }

  loginError.hidden = true;
  loginError.textContent = "";
  loginForm.reset();
  loginDialog.showModal();
  document.getElementById("login-username").focus();
});

document.getElementById("login-cancel").addEventListener("click", () => loginDialog.close());

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.hidden = true;
  loginSubmit.disabled = true;
  loginSubmit.textContent = "Signing in…";

  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
      },
      body: JSON.stringify({
        username: document.getElementById("login-username").value,
        password: document.getElementById("login-password").value,
      }),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Sign-in failed. Please try again.");
    }

    showAccount(result.user);
    loginForm.reset();
    loginDialog.close();
    await refreshConversations();
  } catch (error) {
    loginError.textContent = error.message || "Sign-in failed. Please try again.";
    loginError.hidden = false;
  } finally {
    loginSubmit.disabled = false;
    loginSubmit.textContent = "Sign in";
  }
});

mobileConversations.addEventListener("change", () => {
  const id = Number(mobileConversations.value);
  if (id > 0) loadConversation(id);
});

newChatButton.addEventListener("click", () => {
  showChatView();
  currentConversationId = null;
  clearThread();
  refreshConversations();
  chatInput.focus();
});

// Chat submission is single-flight in this UI; server-side ownership checks remain mandatory.
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message || sendingMessage || accountAction.dataset.authenticated !== "true") return;

  sendingMessage = true;
  sendButton.disabled = true;
  chatInput.disabled = true;
  appendMessage("user", message);
  chatInput.value = "";
  const pending = appendMessage("assistant", "Orinoco is thinking…", "pending");

  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
      },
      body: JSON.stringify({
        message,
        conversation_id: currentConversationId,
        web_search: webSearchToggle.checked,
      }),
    });
    const result = await response.json();
    pending.remove();

    if (!response.ok) {
      if (response.status === 401) showAccount(null);
      throw new Error(result.detail || "Orinoco could not complete that request.");
    }

    currentConversationId = result.conversation_id;
    const sourceText = Array.isArray(result.web_sources) && result.web_sources.length
      ? "\n\nSources:\n" + result.web_sources.map((source, index) => "[" + (index + 1) + "] " + source.title + " — " + source.url).join("\n")
      : "";
    appendMessage("assistant", result.assistant_message + sourceText);
    if (Array.isArray(result.saved_memories) && result.saved_memories.length) {
      appendMessage("assistant", "I saved a useful note to your personal memories. You can review or delete it in My memories.", "notice");
    }
    await refreshConversations();
  } catch (error) {
    pending.remove();
    appendMessage("assistant", error.message || "Something went wrong. Please try again.", "error");
  } finally {
    sendingMessage = false;
    chatInput.disabled = accountAction.dataset.authenticated !== "true";
    sendButton.disabled = chatInput.disabled;
    chatInput.focus();
  }
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

clearThread();
refreshStatus();
refreshAccount();



// Main workspace navigation and document-library rendering/upload helpers.
function setActiveNavigation(activeLink) {
  for (const link of [chatLink, documentsLink]) {
    link.classList.toggle("active", link === activeLink);
    if (link === activeLink) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

function showChatView() {
  chatView.hidden = false;
  documentsView.hidden = true;
  researchView.hidden = true;
  setActiveNavigation(chatLink);
}

function showDocumentsView() {
  if (!currentUser) {
    loginDialog.showModal();
    return;
  }
  chatView.hidden = true;
  documentsView.hidden = false;
  researchView.hidden = true;
  setActiveNavigation(documentsLink);
  loadDocuments();
}

function showResearchView() {
  if (!currentUser) {
    loginDialog.showModal();
    return;
  }
  chatView.hidden = true;
  documentsView.hidden = true;
  researchView.hidden = false;
  setActiveNavigation(researchLink);
}

function setDocumentFeedback(id, message, isError = false) {
  const element = document.getElementById(id);
  element.textContent = message;
  element.className = "settings-feedback" + (isError ? " error" : "");
  element.hidden = false;
}

function renderDocumentList(element, documents, shared = false) {
  element.replaceChildren();
  if (!documents.length) {
    const empty = document.createElement("p");
    empty.className = "conversation-empty";
    empty.textContent = "No documents here yet.";
    element.append(empty);
    return;
  }

  for (const documentInfo of documents) {
    const item = document.createElement("article");
    item.className = "document-item";
    const details = document.createElement("div");
    details.className = "document-copy";
    const name = document.createElement("strong");
    name.textContent = documentInfo.original_name;
    const meta = document.createElement("span");
    const size = Number(documentInfo.size_bytes || 0);
    meta.textContent = (documentInfo.scope === "shared" ? "Shared library" : "Private to you") +
      " · " + documentInfo.file_type.toUpperCase() +
      " · " + (size < 1024 * 1024 ? Math.max(1, Math.round(size / 1024)) + " KB" : (size / (1024 * 1024)).toFixed(1) + " MB");
    details.append(name, meta);
    const actions = document.createElement("div");
    actions.className = "document-actions";
    const download = document.createElement("a");
    download.href = "/api/documents/" + encodeURIComponent(documentInfo.id) + "/download";
    download.textContent = "Download";
    download.className = "document-download";
    actions.append(download);

    if (documentInfo.scope === "private" || (shared && currentUser && currentUser.role === "admin")) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "document-delete";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        if (!window.confirm("Delete " + documentInfo.original_name + "?")) return;
        remove.disabled = true;
        try {
          const csrf = await getCsrfToken();
          const endpoint = documentInfo.scope === "shared"
            ? "/api/admin/shared-documents/" + encodeURIComponent(documentInfo.id)
            : "/api/documents/" + encodeURIComponent(documentInfo.id);
          const response = await fetch(endpoint, { method: "DELETE", headers: { "X-CSRF-Token": csrf } });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || "Could not delete this document.");
          await loadDocuments();
        } catch (error) {
          window.alert(error.message || "Could not delete this document.");
          remove.disabled = false;
        }
      });
      actions.append(remove);
    }
    item.append(details, actions);
    element.append(item);
  }
}

// The API returns only this user's private files plus the authorised shared library.
async function loadDocuments() {
  if (!currentUser) return;
  const privateList = document.getElementById("private-document-list");
  const sharedList = document.getElementById("shared-document-list");
  privateList.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "conversation-empty";
  loading.textContent = "Loading your documents…";
  privateList.append(loading);
  try {
    const response = await fetch("/api/documents", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not load documents.");
    const privateDocs = result.documents.filter(item => item.scope === "private");
    const sharedDocs = result.documents.filter(item => item.scope === "shared");
    renderDocumentList(privateList, privateDocs);
    renderDocumentList(sharedList, sharedDocs, true);
  } catch (error) {
    privateList.replaceChildren();
    const message = document.createElement("p");
    message.className = "settings-feedback error";
    message.textContent = error.message || "Could not load documents.";
    privateList.append(message);
  }
}

async function uploadDocument(formId, inputId, feedbackId, endpoint) {
  const form = document.getElementById(formId);
  const input = document.getElementById(inputId);
  const button = form.querySelector("button[type=submit]");
  const file = input.files && input.files[0];
  if (!file) {
    setDocumentFeedback(feedbackId, "Choose a document first.", true);
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    setDocumentFeedback(feedbackId, "That file is larger than the 10 MiB limit.", true);
    return;
  }
  button.disabled = true;
  try {
    const csrf = await getCsrfToken();
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(endpoint, { method: "POST", headers: { "X-CSRF-Token": csrf }, body: data });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not upload this document.");
    form.reset();
    setDocumentFeedback(feedbackId, "Document uploaded and indexed for Orinoco's document search.");
    await loadDocuments();
  } catch (error) {
    setDocumentFeedback(feedbackId, error.message || "Could not upload this document.", true);
  } finally {
    button.disabled = false;
  }
}

documentsLink.addEventListener("click", event => {
  event.preventDefault();
  showDocumentsView();
});
researchLink.addEventListener("click", event => {
  event.preventDefault();
  showResearchView();
});
chatLink.addEventListener("click", event => {
  event.preventDefault();
  showChatView();
});
document.getElementById("documents-refresh").addEventListener("click", loadDocuments);
document.getElementById("private-document-form").addEventListener("submit", event => {
  event.preventDefault();
  uploadDocument("private-document-form", "private-document-file", "private-document-feedback", "/api/documents");
});
document.getElementById("shared-document-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!currentUser || currentUser.role !== "admin") return;
  uploadDocument("shared-document-form", "shared-document-file", "shared-document-feedback", "/api/admin/shared-documents");
});

// Account settings, administrator account management and personal-memory controls.
function showFeedback(element, message, isError = false) {
  element.textContent = message;
  element.className = "settings-feedback" + (isError ? " error" : "");
  element.hidden = false;
}

async function loadAdminUsers() {
  const list = document.getElementById("admin-user-list");
  list.replaceChildren();
  try {
    const response = await fetch("/api/admin/users", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not load accounts.");

    for (const user of result.users) {
      const item = document.createElement("div");
      item.className = "admin-user";
      const copy = document.createElement("div");
      copy.className = "admin-user-copy";
      const name = document.createElement("strong");
      name.textContent = user.username + (currentUser && user.id === currentUser.id ? " (you)" : "");
      const detail = document.createElement("span");
      detail.textContent = user.role + " · " + (user.active ? "Active" : "Suspended");
      copy.append(name, detail);
      item.append(copy);

      if (!currentUser || user.id !== currentUser.id) {
        const action = document.createElement("button");
        action.type = "button";
        action.textContent = user.active ? "Suspend" : "Reactivate";
        if (user.active) action.classList.add("suspend");
        action.addEventListener("click", async () => {
          action.disabled = true;
          try {
            const csrf = await getCsrfToken();
            const update = await fetch("/api/admin/users/" + user.id, {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
              },
              body: JSON.stringify({ active: !user.active }),
            });
            const payload = await update.json();
            if (!update.ok) throw new Error(payload.detail || "Could not update account.");
            await loadAdminUsers();
          } catch (error) {
            window.alert(error.message || "Could not update account.");
            action.disabled = false;
          }
        });
        item.append(action);
      }
      list.append(item);
    }
  } catch (error) {
    const message = document.createElement("p");
    message.className = "settings-feedback error";
    message.textContent = error.message || "Could not load accounts.";
    list.append(message);
  }
}

settingsButton.addEventListener("click", async () => {
  if (!currentUser) return;
  document.getElementById("password-feedback").hidden = true;
  document.getElementById("user-feedback").hidden = true;
  document.getElementById("password-form").reset();
  document.getElementById("create-user-form").reset();
  settingsDialog.showModal();
  await loadMemories();
  await loadDocuments();
  if (currentUser.role === "admin") {
    await loadAdminUsers();
  }
});

document.getElementById("settings-close").addEventListener("click", () => settingsDialog.close());

document.getElementById("password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const feedback = document.getElementById("password-feedback");
  const currentPassword = document.getElementById("current-password").value;
  const newPassword = document.getElementById("new-password").value;
  const confirmation = document.getElementById("confirm-password").value;
  if (newPassword !== confirmation) {
    showFeedback(feedback, "The new passwords do not match.", true);
    return;
  }

  const button = document.getElementById("password-submit");
  button.disabled = true;
  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not update password.");
    document.getElementById("password-form").reset();
    showFeedback(feedback, "Your password has been updated.");
  } catch (error) {
    showFeedback(feedback, error.message || "Could not update password.", true);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("create-user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const feedback = document.getElementById("user-feedback");
  const button = document.getElementById("create-user-submit");
  button.disabled = true;
  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({
        username: document.getElementById("new-username").value,
        password: document.getElementById("new-user-password").value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not create account.");
    document.getElementById("create-user-form").reset();
    showFeedback(feedback, "Account created. Share the temporary password securely.");
    await loadAdminUsers();
  } catch (error) {
    showFeedback(feedback, error.message || "Could not create account.", true);
  } finally {
    button.disabled = false;
  }
});


async function loadMemories() {
  const list = document.getElementById("memory-list");
  list.replaceChildren();
  try {
    const response = await fetch("/api/memories", { headers: { Accept: "application/json" } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not load memories.");

    if (!result.memories.length) {
      const empty = document.createElement("p");
      empty.className = "conversation-empty";
      empty.textContent = "No memories saved yet.";
      list.append(empty);
      return;
    }

    for (const memory of result.memories) {
      const item = document.createElement("div");
      item.className = "admin-user memory-item";
      const copy = document.createElement("div");
      copy.className = "admin-user-copy";
      const body = document.createElement("span");
      body.textContent = memory.content;
      const source = document.createElement("span");
      source.className = "memory-source";
      source.textContent = memory.source === "automatic" ? "Saved by Orinoco" : "Added by you";
      copy.append(body, source);

      const edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = "Edit";
      edit.addEventListener("click", async () => {
        const revised = window.prompt("Edit this memory", memory.content);
        if (revised === null || !revised.trim() || revised.trim() === memory.content) return;
        try {
          const csrf = await getCsrfToken();
          const update = await fetch("/api/memories/" + memory.id, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
            body: JSON.stringify({ content: revised }),
          });
          const payload = await update.json();
          if (!update.ok) throw new Error(payload.detail || "Could not update memory.");
          await loadMemories();
        } catch (error) {
          window.alert(error.message || "Could not update memory.");
        }
      });

      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Delete";
      remove.className = "suspend";
      remove.addEventListener("click", async () => {
        if (!window.confirm("Delete this memory?")) return;
        try {
          const csrf = await getCsrfToken();
          const deletion = await fetch("/api/memories/" + memory.id, {
            method: "DELETE",
            headers: { "X-CSRF-Token": csrf },
          });
          const payload = await deletion.json();
          if (!deletion.ok) throw new Error(payload.detail || "Could not delete memory.");
          await loadMemories();
        } catch (error) {
          window.alert(error.message || "Could not delete memory.");
        }
      });

      item.append(copy, edit, remove);
      list.append(item);
    }
  } catch (error) {
    const message = document.createElement("p");
    message.className = "settings-feedback error";
    message.textContent = error.message || "Could not load memories.";
    list.append(message);
  }
}

memoriesLink.addEventListener("click", async (event) => {
  event.preventDefault();
  if (!currentUser) return;
  document.getElementById("password-feedback").hidden = true;
  document.getElementById("user-feedback").hidden = true;
  settingsDialog.showModal();
  document.getElementById("personal-memories").scrollIntoView({ block: "start" });
  await loadMemories();
});

document.getElementById("memory-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const feedback = document.getElementById("memory-feedback");
  const button = document.getElementById("memory-submit");
  button.disabled = true;
  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ content: document.getElementById("memory-content").value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not save memory.");
    document.getElementById("memory-form").reset();
    showFeedback(feedback, "Memory saved to your private account.");
    await loadMemories();
  } catch (error) {
    showFeedback(feedback, error.message || "Could not save memory.", true);
  } finally {
    button.disabled = false;
  }
});



document.getElementById("research-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentUser) {
    loginDialog.showModal();
    return;
  }
  const query = document.getElementById("research-query").value.trim();
  const feedback = document.getElementById("research-feedback");
  const results = document.getElementById("research-results");
  const button = document.getElementById("research-submit");
  if (query.length < 3) return;
  button.disabled = true;
  button.textContent = "Searching…";
  feedback.hidden = true;
  results.replaceChildren();
  try {
    const response = await fetch("/api/research/search?q=" + encodeURIComponent(query), {
      headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Web search is unavailable.");
    if (!payload.results.length) {
      showFeedback(feedback, "No results were returned for that search.", true);
      return;
    }
    for (const result of payload.results) {
      const card = document.createElement("article");
      card.className = "research-result";
      const heading = document.createElement("h2");
      const link = document.createElement("a");
      link.href = result.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = result.title;
      heading.append(link);
      const summary = document.createElement("p");
      summary.textContent = result.content || "No summary was provided by the search service.";
      const url = document.createElement("div");
      url.className = "result-url";
      url.textContent = safeUrl;
      card.append(heading, summary, url);
      results.append(card);
    }
  } catch (error) {
    showFeedback(feedback, error.message || "Web search is unavailable.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Search";
  }
});


document.getElementById("summary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentUser) {
    loginDialog.showModal();
    return;
  }
  const url = document.getElementById("summary-url").value.trim();
  const button = document.getElementById("summary-submit");
  const feedback = document.getElementById("summary-feedback");
  const resultCard = document.getElementById("summary-result");
  button.disabled = true;
  button.textContent = "Fetching…";
  feedback.hidden = true;
  resultCard.hidden = true;

  try {
    const csrf = await getCsrfToken();
    const response = await fetch("/api/research/summarise", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
      },
      body: JSON.stringify({ url }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Could not summarise that webpage.");
    document.getElementById("summary-title").textContent = payload.title;
    const source = document.getElementById("summary-source");
    const safeSourceUrl = safeExternalUrl(payload.url);
    source.hidden = !safeSourceUrl;
    if (safeSourceUrl) source.href = safeSourceUrl;
    else source.removeAttribute("href");
    document.getElementById("summary-text").textContent = payload.summary;
    resultCard.hidden = false;
  } catch (error) {
    showFeedback(feedback, error.message || "Could not summarise that webpage.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Summarise";
  }
});
