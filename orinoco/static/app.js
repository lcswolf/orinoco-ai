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
  } else {
    userName.textContent = "Not signed in";
    userRole.textContent = "Your private workspace";
    userAvatar.textContent = "?";
    accountAction.textContent = "Sign in";
    delete accountAction.dataset.authenticated;
  }
}

async function refreshAccount() {
  try {
    const response = await fetch("/api/auth/me", { headers: { Accept: "application/json" } });
    const result = await response.json();
    showAccount(result.authenticated ? result.user : null);
  } catch {
    showAccount(null);
  }
}

async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Could not start a secure sign-in session.");
  const result = await response.json();
  return result.csrf_token;
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
  } catch (error) {
    loginError.textContent = error.message || "Sign-in failed. Please try again.";
    loginError.hidden = false;
  } finally {
    loginSubmit.disabled = false;
    loginSubmit.textContent = "Sign in";
  }
});

refreshStatus();
refreshAccount();
