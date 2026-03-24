// Helper to find element by selector or text content
function findElementByText(target) {
  if (!target) return null;
  try {
    const el = document.querySelector(target);
    if (el) return el;
  } catch (e) {} // Not a valid selector, fallback below
  
  let cleanTarget = String(target).toLowerCase();
  const hrefMatch = cleanTarget.match(/href=["']?([^"']+)["']?/);
  if (hrefMatch) cleanTarget = hrefMatch[1];
  cleanTarget = cleanTarget.replace(/^#|^\./, '');

  const elements = document.querySelectorAll('button, a, input, select, textarea, [role="button"]');
  for (let el of elements) {
    if (el.textContent && el.textContent.toLowerCase().includes(cleanTarget)) return el;
    if (el.placeholder && el.placeholder.toLowerCase().includes(cleanTarget)) return el;
    if (el.name && el.name.toLowerCase() === cleanTarget) return el;
    if (el.id && el.id.toLowerCase() === cleanTarget) return el;
    if (el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes(cleanTarget)) return el;
    if (el.href && el.href.toLowerCase().includes(cleanTarget)) return el;
  }
  return null;
}

// Build a snapshot of the current page state
function getObservation() {
  const getSelector = (el) => {
    // Generate a unique hash guaranteeing the LLM can precisely select this exact DOM element
    if (!el.hasAttribute('data-navis-id')) {
        el.setAttribute('data-navis-id', `el-${Math.random().toString(36).substr(2, 9)}`);
    }
    return `[data-navis-id="${el.getAttribute('data-navis-id')}"]`;
  };

  const inputEls = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, select')).slice(0, 15);
  const inputs = inputEls.map(el => {
    return {
      type: el.tagName.toLowerCase() === 'textarea' ? 'textarea' : (el.tagName.toLowerCase() === 'select' ? 'select' : el.type),
      placeholder: el.placeholder || undefined,
      aria_label: el.getAttribute('aria-label') || undefined,
      name: el.name || undefined,
      selector: getSelector(el)
    };
  });

  const buttonEls = Array.from(document.querySelectorAll('button, a, [role="button"]'));
  const buttons = buttonEls.map(el => {
    const text = el.textContent.trim().substring(0, 40);
    if (!text && !el.title && !el.getAttribute('aria-label')) return null;
    return {
      text: text || el.title || el.getAttribute('aria-label') || "",
      selector: getSelector(el)
    };
  }).filter(Boolean).slice(0, 50);

  return {
    url: window.location.href,
    title: document.title,
    page_text: document.body.innerText.substring(0, 1500),
    buttons: buttons,
    inputs: inputs
  };
}

// Must return true from the listener to keep the channel open for sendResponse
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "GET_OBSERVATION") {
    sendResponse({ observation: getObservation() });
    return true;
  }

  if (msg.type === "EXECUTE_ACTION") {
    (async () => {
      const { action_type, target, value } = msg.action;
      let success = true;
      let error = null;

      try {
        if (action_type === "click") {
          const el = findElementByText(target);
          if (el) el.click();
          else { success = false; error = "element not found: " + target; }

        } else if (action_type === "submit") {
          let el = findElementByText(target);
          if (el && el.tagName.toLowerCase() !== 'form') el = el.closest('form');
          if (el) el.submit();
          else { success = false; error = "form not found: " + target; }

        } else if (action_type === "scroll") {
          const el = findElementByText(target);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          else if (target === "down" || value === "down") window.scrollBy(0, window.innerHeight);
          else if (target === "up" || value === "up") window.scrollBy(0, -window.innerHeight);
          else { success = false; error = "element to scroll not found: " + target; }

        } else if (action_type === "wait") {
          const ms = parseInt(value) || parseInt(target) || 2000;
          await new Promise(r => setTimeout(r, ms));

        } else if (action_type === "select_option") {
          let el = findElementByText(target);
          if (el && el.tagName.toLowerCase() !== 'select') el = el.closest('select');
          if (el) {
            const valStr = String(value).toLowerCase();
            const optionToSelect = Array.from(el.options).find(o => o.text.toLowerCase().includes(valStr) || o.value.toLowerCase().includes(valStr));
            if (optionToSelect) {
              el.value = optionToSelect.value;
              el.dispatchEvent(new Event("change", { bubbles: true }));
            } else { success = false; error = "option not found: " + value; }
          } else { success = false; error = "select not found: " + target; }

        } else if (action_type === "press_key") {
          const key = value || target || 'Enter';
          const keyCodeMap = { 'Enter': 13, 'Escape': 27, 'Tab': 9, 'ArrowDown': 40, 'ArrowUp': 38 };
          const code = keyCodeMap[key] || 13;
          const activeEl = document.activeElement || document.body;
          activeEl.dispatchEvent(new KeyboardEvent('keydown', {key: key, code: key, keyCode: code, which: code, bubbles: true}));
          activeEl.dispatchEvent(new KeyboardEvent('keyup', {key: key, code: key, keyCode: code, which: code, bubbles: true}));

        } else if (action_type === "type") {
          let el = findElementByText(target);
          if (!el) {
            // Desperate fallback for completely blind types
            el = document.querySelector('input[type="search"], textarea') || document.querySelector('input[type="text"]');
          }

          if (el) {
            el.focus();
            el.value = value || "";
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            // Press Enter automatically to submit search if it's an input/textarea
            if (el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea') {
                el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
            }
          } else {
            success = false; error = "input not found: " + target;
          }

        } else if (action_type === "navigate") {
          window.location.href = target;

        } else if (action_type === "done") {
          // success is still true
        } else {
          success = false; error = "unknown action_type: " + action_type;
        }
      } catch (e) {
        success = false;
        error = "error: " + e.message;
      }

      sendResponse({ success: success, error: error });
    })();
    return true;
  }
});