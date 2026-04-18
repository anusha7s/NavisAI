let isRunning = false;

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start');
    const stopBtn = document.getElementById('stop');
    const taskInput = document.getElementById('task');
    const statusDiv = document.getElementById('status');
    const logsDiv = document.getElementById('logs');
    const errorDiv = document.getElementById('error-message');

    // Restore state
    chrome.storage.local.get(['currentTask', 'isRunning', 'lastLogs'], (res) => {
        if (res.currentTask) taskInput.value = res.currentTask;
        if (res.isRunning) {
            setRunningUI(true);
            statusDiv.textContent = "Agent is working...";
        }
        if (res.lastLogs) {
            logsDiv.innerHTML = res.lastLogs;
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
    });

    startBtn.addEventListener('click', async () => {
        const task = taskInput.value.trim();
        if (!task) {
            showError("Please enter a task.");
            return;
        }

        setRunningUI(true);
        hideError();
        logsDiv.innerHTML = "";
        log("Sending task to backend...", "info");
        statusDiv.textContent = "Planning initial action...";
        chrome.storage.local.set({ currentTask: task, isRunning: true, lastLogs: "" });

        try {
            const response = await fetch('http://127.0.0.1:8000/start_task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ task: task })
            });
            
            if (!response.ok) {
                let errText = await response.text();
                throw new Error(`HTTP ${response.status} - ${errText}`);
            }

            const data = await response.json();
            log(`Initial plan: ${data.plan.action_type}`, "success");
            
            statusDiv.textContent = "Executing...";
            chrome.runtime.sendMessage({ 
                type: "START_AGENT", 
                task: task, 
                initialPlan: data.plan 
            });

        } catch (e) {
            console.error("Popup Error:", e);
            showError(`Failed to connect to backend: ${e.message}`);
            setRunningUI(false);
            log(`Connection Error: ${e.message}`, "error");
        }
    });

    stopBtn.addEventListener('click', () => {
        setRunningUI(false);
        statusDiv.textContent = "Agent stopped.";
        chrome.runtime.sendMessage({ type: "STOP_AGENT" });
        chrome.storage.local.set({ isRunning: false });
        log("Manually stopped.", "error");
    });

    chrome.runtime.onMessage.addListener((msg) => {
        if (msg.type === "AGENT_STEP") {
            log(msg.text, "info");
            statusDiv.textContent = msg.text.substring(0, 40) + "...";
        }
        else if (msg.type === "AGENT_ERROR") {
            showError(msg.error);
            log(msg.error, "error");
            setRunningUI(false);
            statusDiv.textContent = "Error occurred.";
        }
        else if (msg.type === "AGENT_DONE") {
            log(msg.text, "success");
            setRunningUI(false);
            statusDiv.textContent = "Task Completed!";
            statusDiv.className = "success";
        }
    });

    function log(message, type="info") {
        const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        const p = document.createElement("div");
        p.className = `log-line flex`;
        p.innerHTML = `<span style="color:#64748b; margin-right:8px">[${time}]</span> <span style="color:${type === 'error' ? '#f87171' : type === 'success' ? '#34d399' : '#cbd5e1'}">${message}</span>`;
        logsDiv.appendChild(p);
        logsDiv.scrollTop = logsDiv.scrollHeight;
        chrome.storage.local.set({ lastLogs: logsDiv.innerHTML });
    }

    function setRunningUI(running) {
        isRunning = running;
        if (running) {
            document.body.classList.add('is-running');
            startBtn.disabled = true;
            startBtn.style.opacity = "0.5";
            statusDiv.className = "info";
        } else {
            document.body.classList.remove('is-running');
            startBtn.disabled = false;
            startBtn.style.opacity = "1";
            chrome.storage.local.set({ isRunning: false });
        }
    }

    function showError(msg) {
        errorDiv.textContent = msg;
        errorDiv.style.display = 'block';
    }

    function hideError() {
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
    }
});