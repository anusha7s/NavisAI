let isRunning = false;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "START_AGENT") {
    isRunning = true;
    runAgentLoop(msg.task, msg.initialPlan);
  }
  if (msg.type === "STOP_AGENT") isRunning = false;
});

async function runAgentLoop(task, currentPlan) {
  let step = 0;
  while (isRunning) {
    // Get current observation from active tab
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const obsResponse = await chrome.tabs.sendMessage(tab.id, {type: "GET_OBSERVATION"});
    
    // Send to backend for next action
    const resp = await fetch('http://127.0.0.1:8000/next_step', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(obsResponse.observation || {})
    });
    const actionPlan = await resp.json();

    if (actionPlan.action_type === "done") {
      chrome.runtime.sendMessage({type: "LOG", text: `Task completed! Confidence: ${actionPlan.confidence}`});
      break;
    }

    // Execute action via content script
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: "EXECUTE_ACTION",
      action: actionPlan
    });

    chrome.runtime.sendMessage({type: "LOG", text: `Step ${++step}: ${actionPlan.action_type} → ${result.status}`});
    
    await new Promise(r => setTimeout(r, 1500)); // safety delay
  }
}