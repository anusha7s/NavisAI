// background.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'startAgent') {
    handleAgentStart(message.task, sendResponse);
    return true; // Keep channel open for async response
  }
});

async function handleAgentStart(task, sendResponse) {
  let currentStatus = 'Starting...';
  let iteration = 0;
  const maxIterations = 10;

  sendResponse({ status: currentStatus });

  while (iteration < maxIterations) {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const contextRes = await new Promise(r => chrome.tabs.sendMessage(tab.id, { action: 'getPageContext' }, r));
      const context = contextRes?.context || 'No context';

      const res = await fetch('http://127.0.0.1:8000/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task,
          page_context: context,
          mode: 'general',
          previous_outcome: ''  // Later: pass last action result
        })
      });

      if (!res.ok) throw new Error('Backend failed');

      const plan = await res.json();

      // Update popup log (send message to popup)
      chrome.runtime.sendMessage({
        action: 'updateLog',
        log: `Iteration ${iteration+1}:\n${plan.reasoning}\nAction: ${plan.next_action}\nConfidence: ${plan.confidence}%`
      });

      if (plan.is_task_complete) {
        chrome.runtime.sendMessage({ action: 'updateLog', log: 'TASK COMPLETE!' });
        break;
      }

      if (!plan.is_safe) {
        chrome.runtime.sendMessage({ action: 'updateLog', log: 'Action blocked for safety.' });
        break;
      }

      // Execute
      const execRes = await new Promise(r => chrome.tabs.sendMessage(tab.id, {
        action: 'executeAction',
        command: plan.next_action
      }, r));

      // Wait a bit for page to react (dynamic sites)
      await new Promise(r => setTimeout(r, 2000));

      iteration++;
    } catch (err) {
      chrome.runtime.sendMessage({ action: 'updateLog', log: 'Error: ' + err.message });
      break;
    }
  }
}

//     // Call backend
//     const res = await fetch('http://127.0.0.1:8000/plan', {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         task: task,
//         page_context: context,
//         mode: 'general' // can be dynamic later
//       })
//     });

//     if (!res.ok) throw new Error(`Backend error ${res.status}`);

//     const plan = await res.json();

//     // Send plan back to popup
//     sendResponse({ status: 'Plan received', plan });

//     // Later: execute the action here or send to content script
//     if (plan.is_safe && plan.next_action !== 'TASK_COMPLETE') {
//       chrome.tabs.sendMessage(tab.id, {
//         action: 'executeAction',
//         command: plan.next_action
//       });
//     }

//   } catch (err) {
//     sendResponse({ status: 'Error: ' + err.message });
//   }
// }