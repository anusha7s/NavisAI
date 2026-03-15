// ... your existing code ...

const statusEl = document.getElementById('status');
const startBtn = document.getElementById('start');
const stopBtn = document.getElementById('stop');

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
    log("Please enter a task", "error");
    return;
  }

  setLoading(true);
  log(`Starting task: ${task}`);

  try {
    // your existing fetch code...
    const res = await fetch('http://127.0.0.1:8000/start_task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    log(`Initial plan received (confidence: ${data.plan?.confidence || '?'})`, "success");
    chrome.runtime.sendMessage({ type: "START_AGENT", task, initialPlan: data.plan });

  } catch (err) {
    log(`Error: ${err.message}`, "error");
    statusEl.textContent = "Failed – check logs";
    statusEl.className = 'error';
  } finally {
    // keep loading until agent finishes or user stops
    // you can setLoading(false) when you detect "done" in logs if you want
  }
};

// Stop button
document.getElementById('stop').onclick = () => {
  chrome.runtime.sendMessage({ type: "STOP_AGENT" });
  setLoading(false);
  log("Agent stopped by user", "error");
  statusEl.textContent = "Stopped";
  statusEl.className = 'error';
};

// Optional: listen for messages from background to update status when done
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "AGENT_DONE") {
    setLoading(false);
    log("Task completed!", "success");
    statusEl.textContent = "Task completed";
    statusEl.className = 'success';
  }
});