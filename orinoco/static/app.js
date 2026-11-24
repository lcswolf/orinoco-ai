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
const chatThread = document.getElementById("chat-thread");
const chatInput = document.getElementById("chat-input");
const chatForm = document.getElementById("chat-form");
const sendButton = document.getElementById("send-message");
const chatHint = document.getElementById("chat-hint");
let currentConversationId = null;
let sendingMessage = false;

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

function showAccount(user) {
  if (user) {
    userName.textContent = user.username;
    userRole.textContent = user.role === "admin" ? "Administrator" : "Standard account";
    userAvatar.textContent = user.username.charAt(0).toUpperCase();
    accountAction.textContent = "Sign out";
    accountAction.dataset.authenticated = "true";
    newChatButton.disabled = false;
    chatInput.disabled = false;
    sendButton.disabled = false;
    chatInput.placeholder = "Message Orinoco…";
    chatHint.textContent = "Your conversation is private and saved to your account.";
  } else {
    userName.textContent = "Not signed in";
    userRole.textContent = "Your private workspace";
    userAvatar.textContent = "?";
    accountAction.textContent = "Sign in";
    delete accountAction.dataset.authenticated;
    newChatButton.disabled = true;
    chatInput.disabled = true;
    sendButton.disabled = true;
    chatInput.placeholder = "Sign in to start a private conversation…";
    chatHint.textContent = "Sign in to start a private conversation. Your chats are saved to your own account.";
    currentConversationId = null;
    clearThread();
    conversationList.replaceChildren();
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
  label.textContent = role === "user" ? "You" : "Orinoco";
  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.textContent = content;
  message.append(label, body);
  chatThread.append(message);
  chatThread.scrollTop = chatThread.scrollHeight;
  return message;
}

async function refreshConversations() {
  if (accountAction.dataset.authenticated !== "true") return;
  try {
    const response = await fetch("/api/conversations", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const result = await response.json();
    conversationList.replaceChildren();

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

newChatButton.addEventListener("click", () => {
  currentConversationId = null;
  clearThread();
  refreshConversations();
  chatInput.focus();
});

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
      }),
    });
    const result = await response.json();
    pending.remove();

    if (!response.ok) {
      if (response.status === 401) showAccount(null);
      throw new Error(result.detail || "Orinoco could not complete that request.");
    }

    currentConversationId = result.conversation_id;
    appendMessage("assistant", result.assistant_message);
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
