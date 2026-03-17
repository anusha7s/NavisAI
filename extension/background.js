let isRunning = false;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "START_AGENT") {
    isRunning = true;
    runAgentLoop(msg.task, msg.initialPlan);
  }
  if (msg.type === "STOP_AGENT") isRunning = false;
});

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  return tab;
}

async function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    let timer;
    let listener = (updatedTabId, info, updatedTab) => {
      if (updatedTabId === tabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        resolve(updatedTab);
      }
    };
    
    timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      chrome.tabs.get(tabId, tab => resolve(tab));
    }, 10000); // 10s fallback

    chrome.tabs.get(tabId, (tab) => {
      if (!tab) {
        clearTimeout(timer);
        resolve(null);
      } else if (tab.status === 'complete') {
        clearTimeout(timer);
        resolve(tab);
      } else {
        chrome.tabs.onUpdated.addListener(listener);
      }
    });
  });
}

async function runAgentLoop(task, currentPlan) {
  let step = 0;
  let nextAction = currentPlan; // Start with the plan we got from the popup
  
  while (isRunning) {
    try {
        // Some AI APIs wrap the response in .plan or flat, safely extract the actual action
        let actionToExecute = nextAction;
        if (actionToExecute && actionToExecute.plan) {
            actionToExecute = actionToExecute.plan;
        }
        
        console.log("RAW nextAction:", nextAction);
        console.log("EXTRACTED actionToExecute:", actionToExecute);

        if (!actionToExecute || !actionToExecute.action_type) {
          chrome.runtime.sendMessage({type: "AGENT_DONE", text: `[Error] Received empty or invalid plan from AI.`});
          break; 
        }

        if (actionToExecute.action_type === "done") {
          chrome.runtime.sendMessage({type: "AGENT_DONE", text: `Task completed! Confidence: ${actionToExecute.confidence || 1.0}`});
          break;
        }

        // 1. Execute the action we currently hold (initial plan or previous next_step)
        const tabs = await chrome.tabs.query({active: true, currentWindow: true});
        if (!tabs || tabs.length === 0) throw new Error("No active tab found. Was the window minimized?");
        const tab = tabs[0];

        let result = { status: 'failed_to_connect' };
        try {
            if (actionToExecute.action_type === "navigate") {
                await chrome.tabs.update(tab.id, { url: actionToExecute.target });
                result = { status: 'navigated' };
                console.log("Navigated directly via background script to", actionToExecute.target);
            } else {
                result = await chrome.tabs.sendMessage(tab.id, {
                  type: "EXECUTE_ACTION",
                  action: actionToExecute
                });
            }
        } catch(e) {
            console.error("Content script not reachable. Did you hard refresh?", e);
            chrome.runtime.sendMessage({type: "AGENT_DONE", text: `[Error] Cannot reach webpage. Press Ctrl+F5 on the page first!`});
            break;
        }

        // 2. Log result to popup
        chrome.runtime.sendMessage({type: "AGENT_STEP", text: `[Step ${++step}] Executed: ${actionToExecute.action_type} → ${result?.status || 'unknown'}`});
        
        // Wait for the page to physically react (e.g. load new HTML, open menus, finish typing)
        await new Promise(r => setTimeout(r, 2000)); 

        if (!isRunning) break;

        // 3. Wait if we just navigated, then get fresh observation of the new page state
        let freshTab = await getActiveTab();
        if (!freshTab) throw new Error("Lost active tab during observation");
        
        // If we just clicked a link or navigated, wait for the page to finish loading before observing
        if (actionToExecute.action_type === "navigate" || actionToExecute.action_type === "click") {
            console.log("Waiting for new page to settle...");
            // Reduced to 2000ms delay since waitForTabLoad is reliable now
            await new Promise(r => setTimeout(r, 2000)); 
            freshTab = await waitForTabLoad(freshTab.id);
            if (!freshTab) throw new Error("Tab closed or lost before it could finish loading.");
        }

        let obsResponse = {};
        for (let attempts = 0; attempts < 3; attempts++) {
            try {
                obsResponse = await chrome.tabs.sendMessage(freshTab.id, {type: "GET_OBSERVATION"});
                if (obsResponse && obsResponse.observation) break; // Success!
            } catch(e) {
                console.error(`Observation failed attempt ${attempts+1}`, e);
                if (attempts === 2) {
                    throw new Error(`Lost connection to page. Did it load?`);
                }
                await new Promise(r => setTimeout(r, 2000));
            }
        }
        
        if (!isRunning) break;
        if (!obsResponse || !obsResponse.observation) throw new Error("Could not retrieve observation from page");
        
        // 4. Ask Backend (Groq) what to do next based on new state
        try {
            const payload = obsResponse.observation;
            payload.task = task;
            const resp = await fetch('http://127.0.0.1:8000/next_step', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify(payload)
            });
            
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            nextAction = await resp.json(); // loop around and execute this!
        } catch (e) {
            chrome.runtime.sendMessage({type: "AGENT_DONE", text: `Backend Error getting next step: ${e.message}`});
            break;
        }
    } catch (globalErr) {
        console.error("Agent Loop Error:", globalErr);
        chrome.runtime.sendMessage({type: "AGENT_DONE", text: `[Error] ${globalErr.message}`});
        isRunning = false;
        break;
    }
  }
}