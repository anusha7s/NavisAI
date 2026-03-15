// Helper to find element by text content
function findElementByText(text) {
  const elements = document.querySelectorAll('button, a, input, [role="button"]');
  for (let el of elements) {
    if (el.textContent.toLowerCase().includes(text.toLowerCase())) return el;
  }
  return null;
}

// Build a snapshot of the current page state
function getObservation() {
  return {
    url: window.location.href,
    title: document.title,
    page_text: document.body.innerText.substring(0, 1500),
    visible_buttons: Array.from(document.querySelectorAll('button, a'))
      .map(b => b.textContent.trim())
      .filter(Boolean)
      .slice(0, 30),
    forms: []
  };
}

// Must return true from the listener to keep the channel open for sendResponse
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "GET_OBSERVATION") {
    sendResponse({ observation: getObservation() });
    return true;
  }

  if (msg.type === "EXECUTE_ACTION") {
    const { action_type, target, value } = msg.action;
    let result = "success";

    try {
      if (action_type === "click") {
        const el = findElementByText(target);
        if (el) el.click();
        else result = "element not found: " + target;

      } else if (action_type === "type") {
        // Try multiple selectors to find the input field
        const el =
          document.querySelector(`input[name="${target}"]`) ||
          document.querySelector(`input[placeholder*="${target}" i]`) ||
          document.querySelector('input[type="search"]') ||
          document.querySelector('input[type="text"]') ||
          findElementByText(target);

        if (el) {
          el.focus();
          el.value = value || "";
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
          result = "input not found: " + target;
        }

      } else if (action_type === "navigate") {
        window.location.href = target;

      } else if (action_type === "done") {
        result = "done";
      }
    } catch (e) {
      result = "error: " + e.message;
    }

    sendResponse({ status: result, observation: getObservation() });
    return true;
  }
});