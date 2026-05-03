document.addEventListener('DOMContentLoaded', () => {
  const taskInput = document.getElementById('task-input');
  const micBtn = document.getElementById('mic-btn');
  const sendBtn = document.getElementById('send-btn');
  const stopBtn = document.getElementById('stop-btn');
  const chatContainer = document.getElementById('chat');
  const confBar = document.getElementById('confidence-bar');
  const confFill = document.getElementById('confidence-fill');

  // Initialize Speech
  if (window.SpeechHandler) {
    new window.SpeechHandler(taskInput, micBtn);
  }

  let eventSource = null;
  let currentTaskBlock = null;
  let currentStepsUl = null;

  function appendAgentMessage(text) {
    const div = document.createElement('div');
    div.className = 'message msg-agent';
    div.textContent = text;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message msg-user';
    div.textContent = text;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function createStepTracker() {
    const div = document.createElement('div');
    div.className = 'message msg-agent';
    div.style.background = 'rgba(15, 23, 42, 0.5)';
    div.style.border = '1px solid var(--accent)';
    
    const title = document.createElement('strong');
    title.textContent = 'Execution Plan';
    div.appendChild(title);

    currentStepsUl = document.createElement('div');
    currentStepsUl.className = 'step-tracker';
    div.appendChild(currentStepsUl);

    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    currentTaskBlock = div;
  }

  function updateStep(stepId, text, status) {
    if (!currentStepsUl) return;
    
    let stepEl = currentStepsUl.querySelector(`[data-step-id="${stepId}"]`);
    if (!stepEl) {
      stepEl = document.createElement('div');
      stepEl.className = 'step';
      stepEl.setAttribute('data-step-id', stepId);
      stepEl.innerHTML = `<div class="step-icon"></div><div class="step-text">${text}</div>`;
      currentStepsUl.appendChild(stepEl);
    } else {
      stepEl.querySelector('.step-text').textContent = text;
    }

    stepEl.className = `step step-${status}`; // pending, active, done, fail
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function updateConfidence(score) {
    confBar.style.display = 'block';
    confFill.style.width = `${Math.round(score * 100)}%`;
  }

  let waitingForUser = false;
  let pendingTaskName = "";
  let activeTaskPrompt = "";

  function handleSSEMessage(event) {
      const data = JSON.parse(event.data);
      const taskText = activeTaskPrompt;
      
      if (data.type === 'plan') {
        updateStep('planning', 'Plan generated.', 'done');
      } 
      else if (data.type === 'step_update') {
        updateStep(data.step_id, data.text, data.status);
        if (data.confidence !== undefined) updateConfidence(data.confidence);
      }
      else if (data.type === 'ask_user') {
        appendAgentMessage(data.text);
        stopBtn.style.display = 'none';
        waitingForUser = true;
        pendingTaskName = taskText;
        taskInput.placeholder = "Reply to agent...";
        eventSource.close(); // Wait for user reply
      }
      else if (data.type === 'done') {
        updateStep(data.step_id, 'Task Completed Successfully!', 'done');
        stopBtn.style.display = 'none';
        eventSource.close();
      }
      else if (data.type === 'get_observation') {
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
          if (!tabs || tabs.length === 0) {
              fetch(`http://127.0.0.1:8000/observation_result`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ task: taskText, success: false })
              });
              return;
          }
          chrome.tabs.sendMessage(tabs[0].id, { type: "GET_OBSERVATION" }, (resp) => {
              if (chrome.runtime.lastError || !resp || !resp.observation) {
                  fetch(`http://127.0.0.1:8000/observation_result`, {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({ 
                          task: taskText, 
                          observation: { url: tabs[0].url || "", title: tabs[0].title || "", page_text: "", buttons: [], inputs: [] }
                      })
                  });
                  return;
              }
              fetch(`http://127.0.0.1:8000/observation_result`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ task: taskText, observation: resp.observation })
              });
          });
        });
      }
      else if (data.type === 'execute_action') {
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
          if (!tabs || tabs.length === 0) {
              fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=false&error=No active tab`);
              return;
          }
          
          if (data.action.action_type === 'navigate') {
              try {
                  const targetHost = new URL(data.action.target).hostname.replace('www.', '');
                  const currentHost = new URL(tabs[0].url).hostname.replace('www.', '');
                  
                  // If we are already on the correct website, do NOT reload it! This preserves search results!
                  if (currentHost.includes(targetHost) || targetHost.includes(currentHost)) {
                      fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=true&error=`);
                      return;
                  }
              } catch (e) {} // Fallback to normal navigation if URL parsing fails

              chrome.tabs.update(tabs[0].id, { url: data.action.target }, (tab) => {
                  let resolved = false;
                  let listener = function(tabId, info) {
                      if (tabId === tab.id && info.status === 'complete') {
                          resolved = true;
                          chrome.tabs.onUpdated.removeListener(listener);
                          fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=true&error=`);
                      }
                  };
                  chrome.tabs.onUpdated.addListener(listener);
                  setTimeout(() => {
                      if (!resolved) {
                          chrome.tabs.onUpdated.removeListener(listener);
                          fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=true&error=`);
                      }
                  }, 8000);
              });
              return;
          }

          let attempts = 0;
          function attemptSend() {
              attempts++;
              chrome.tabs.sendMessage(tabs[0].id, { type: "EXECUTE_ACTION", action: data.action }, (resp) => {
                  if (chrome.runtime.lastError) {
                      if (attempts < 8) { // Retry for up to 8 seconds if page is reloading
                          setTimeout(attemptSend, 1000);
                          return;
                      }
                      fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=false&error=${encodeURIComponent("Cannot reach page. Page is still loading or disconnected.")}`);
                      return;
                  }
                  const success = resp && resp.success ? 'true' : 'false';
                  const err = resp && resp.error ? encodeURIComponent(resp.error) : '';
                  fetch(`http://127.0.0.1:8000/step_result?task=${encodeURIComponent(taskText)}&step_id=${data.step_id}&success=${success}&error=${err}`);
              });
          }
          attemptSend();
        });
      }
      else if (data.type === 'error') {
        updateStep('error', data.error, 'fail');
        stopBtn.style.display = 'none';
        eventSource.close();
      }
  }

  function handleSSEError(err) {
      console.error("SSE Error:", err);
      updateStep('error', 'Lost connection to backend.', 'fail');
      stopBtn.style.display = 'none';
      eventSource.close();
  }

  function startTask(taskText) {
    appendUserMessage(taskText);
    taskInput.value = '';
    stopBtn.style.display = 'block';
    confBar.style.display = 'none';
    waitingForUser = false;
    taskInput.placeholder = "Ask me anything...";
    activeTaskPrompt = taskText;

    createStepTracker();
    updateStep('planning', 'Generating task plan...', 'active');

    if (eventSource) eventSource.close();
    eventSource = new EventSource(`http://127.0.0.1:8000/stream_task?task=${encodeURIComponent(taskText)}`);
    eventSource.onmessage = handleSSEMessage;
    eventSource.onerror = handleSSEError;
  }

  function resumeTask(replyText) {
    appendUserMessage(replyText);
    taskInput.value = '';
    stopBtn.style.display = 'block';
    waitingForUser = false;
    taskInput.placeholder = "Ask me anything...";
    
    fetch('http://127.0.0.1:8000/resume_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ task: pendingTaskName, reply: replyText })
    }).then(res => res.json()).then(data => {
        if (data.status === 'resuming') {
            if (eventSource) eventSource.close();
            activeTaskPrompt = pendingTaskName + " (User replied: " + replyText + ")";
            eventSource = new EventSource(`http://127.0.0.1:8000/stream_task?task=${encodeURIComponent(activeTaskPrompt)}`);
            eventSource.onmessage = handleSSEMessage;
            eventSource.onerror = handleSSEError;
        } else {
            updateStep('error', 'Failed to resume task.', 'fail');
        }
    }).catch(err => {
        updateStep('error', 'Failed to reach backend.', 'fail');
    });
  }

  function handleSend() {
    const val = taskInput.value.trim();
    if (val) {
        if (waitingForUser) resumeTask(val);
        else startTask(val);
    }
  }

  sendBtn.addEventListener('click', handleSend);

  taskInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  stopBtn.addEventListener('click', () => {
    if (eventSource) {
      eventSource.close();
      updateStep('stopped', 'Agent stopped by user.', 'fail');
      stopBtn.style.display = 'none';
    }
  });
});
