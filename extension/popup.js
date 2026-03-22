// ... your existing code ...

const statusEl = document.getElementById('status');
const logsEl = document.getElementById('logs');
const startBtn = document.getElementById('start');
const stopBtn = document.getElementById('stop');
const errorEl = document.getElementById('error-message');
const lastActionEl = document.getElementById('last-action');

// Auto-detect theme
if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
  document.documentElement.setAttribute('data-theme', 'light');
}

function log(message, type = 'info') {
  const div = document.createElement('div');
  div.className = 'log-line';
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  div.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;

  if (type === 'error') div.style.color = 'var(--error)';
  if (type === 'success') div.style.color = 'var(--success)';

  logsEl.appendChild(div);
  logsEl.scrollTop = logsEl.scrollHeight;
}

function setLoading(isLoading) {
  startBtn.disabled = isLoading;
  startBtn.innerHTML = isLoading ? '<span class="loading"></span> Running...' : 'Start Agent';
  statusEl.innerHTML = isLoading
    ? '<span class="loading"></span> Agent is working...'
    : '';
  statusEl.className = isLoading ? '' : 'success';
}

// Start button
document.getElementById('start').onclick = async () => {
  const task = document.getElementById('task').value.trim();
  if (!task) {
    showError("Please enter a task");
    return;
  }

  logsEl.innerHTML = '';
  lastActionEl.style.display = 'none';
  errorEl.style.display = 'none';
  
  setStatus("loading", "Initializing agent...");
  log(`Starting task: ${task}`);

  try {
    const res = await fetch('http://127.0.0.1:8000/start_task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    log(`Initial plan received (confidence: ${data.plan?.confidence || '?'})`, "success");
    chrome.runtime.sendMessage({ type: "START_AGENT", task, initialPlan: data.plan });
    
    setStatus("running", "Waiting for page...");
  } catch (err) {
    showError(err.message || "Failed to start");
  }
};

// Stop button
document.getElementById('stop').onclick = () => {
  chrome.runtime.sendMessage({ type: "STOP_AGENT" });
  setStatus("idle", "Agent stopped by user");
  log("Agent stopped by user", "error");
};

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "AGENT_DONE") {
    log(msg.text || "Task completed!", "success");
    stopLoading();
    statusEl.textContent = "Task completed!";
  } else if (msg.type === "AGENT_ERROR") {
    showError(msg.error || "Unknown error occurred!");
  } else if (msg.type === "AGENT_STEP") {
    log(msg.text); // log intermediate steps without stopping the UI
    updateLastAction(msg.text);
    setStatus("running", "Executing steps...");
  }
});