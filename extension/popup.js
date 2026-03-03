// popup.js - Updated for agent loop visualization

const startBtn = document.getElementById('startBtn');
const taskInput = document.getElementById('taskInput');
const statusDiv = document.getElementById('status');
const logDiv = document.getElementById('log');

let isRunning = false;

// Listen for log updates from background.js
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'updateLog') {
    appendToLog(message.log);
  } else if (message.action === 'updateStatus') {
    statusDiv.textContent = message.status;
  } else if (message.action === 'agentFinished') {
    statusDiv.textContent = message.status || 'Agent finished';
    startBtn.disabled = false;
    isRunning = false;
  }
});

// Helper to append log lines and auto-scroll
function appendToLog(text) {
  const line = document.createElement('div');
  line.textContent = text;
  logDiv.appendChild(line);
  logDiv.scrollTop = logDiv.scrollHeight; // Auto-scroll to bottom
}

startBtn.addEventListener('click', async () => {
  if (isRunning) return;

  const task = taskInput.value.trim();
  if (!task) {
    statusDiv.textContent = 'Please enter a task.';
    return;
  }

  // Reset UI
  logDiv.innerHTML = '';
  statusDiv.textContent = 'Starting agent...';
  startBtn.disabled = true;
  isRunning = true;

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'startAgent',
      task: task
    });

    if (response?.error) {
      statusDiv.textContent = 'Error: ' + response.error;
      startBtn.disabled = false;
      isRunning = false;
      return;
    }

    statusDiv.textContent = 'Agent running... (see log below)';
    // The background will now send updateLog messages

  } catch (err) {
    statusDiv.textContent = 'Connection error: ' + err.message;
    startBtn.disabled = false;
    isRunning = false;
  }
});

// Optional: Clear log when popup opens (or keep history - your choice)
// window.addEventListener('load', () => {
//   logDiv.innerHTML = '';
// });