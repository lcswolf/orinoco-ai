const connection = document.getElementById("connection-status");
const modelTitle = document.getElementById("model-title");
const modelDescription = document.getElementById("model-description");
const modelPill = document.getElementById("model-pill");

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

refreshStatus();
