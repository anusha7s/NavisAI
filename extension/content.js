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

  // 1. Prioritize native interactive elements
  const interactiveElements = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [tabindex]');
  for (let el of interactiveElements) {
    if (el.textContent && el.textContent.toLowerCase().includes(cleanTarget)) return el;
    if (el.placeholder && el.placeholder.toLowerCase().includes(cleanTarget)) return el;
    if (el.name && el.name.toLowerCase() === cleanTarget) return el;
    if (el.id && el.id.toLowerCase() === cleanTarget) return el;
    if (el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes(cleanTarget)) return el;
    if (el.href && el.href.toLowerCase().includes(cleanTarget)) return el;
  }

  // 2. Fallback to generic text containers (span, div, label, p, li)
  const genericElements = document.querySelectorAll('label, span, div, p, li, h1, h2, h3, h4');
  for (let el of genericElements) {
    // Only match if the text is relatively short to avoid matching the entire body
    if (el.textContent && el.textContent.length < 100 && el.textContent.toLowerCase().includes(cleanTarget)) {
        return el;
    }
  }

  return null;
}

// Universal product & price extractor — works on Amazon, Flipkart, and most shopping sites
function extractProducts() {
  const products = [];
  const seen = new Set();

  // Strategy 1: Amazon — each result card is a [data-component-type="s-search-result"]
  document.querySelectorAll('[data-component-type="s-search-result"]').forEach(card => {
    const nameEl = card.querySelector('h2 a span, h2 span');
    const priceWhole = card.querySelector('.a-price .a-offscreen');
    const name = nameEl ? nameEl.textContent.trim().substring(0, 80) : '';
    const price = priceWhole ? priceWhole.textContent.trim() : '';
    if (name && price && !seen.has(name)) {
      seen.add(name);
      products.push({ name, price });
    }
  });

  // Strategy 2: Flipkart — product cards usually have an anchor with a title + price nearby
  if (products.length === 0) {
    document.querySelectorAll('a[href*="/p/"], div[data-id]').forEach(card => {
      // Walk up to get the full product card container
      let container = card.closest('[data-id]') || card.parentElement?.parentElement || card;
      const text = container.innerText || '';
      // Look for ₹ price pattern in the card text
      const priceMatch = text.match(/₹[\s]?[\d,]+/);
      // Get product name from the link title or first significant text
      const titleEl = container.querySelector('a[title], a div, div[class*="title"], div[class*="name"]');
      const name = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()).substring(0, 80) : '';
      const price = priceMatch ? priceMatch[0] : '';
      if (name && price && name.length > 5 && !seen.has(name)) {
        seen.add(name);
        products.push({ name, price });
      }
    });
  }

  // Strategy 3: Universal fallback — scan ALL elements for currency patterns
  if (products.length === 0) {
    const allEls = document.querySelectorAll('*');
    for (let el of allEls) {
      if (el.children.length > 5) continue; // Skip containers
      const text = el.textContent.trim();
      if (text.length > 200 || text.length < 3) continue;
      const priceMatch = text.match(/[₹$€£]\s?[\d,]+(\.\d{2})?/);
      if (priceMatch && !seen.has(text.substring(0, 40))) {
        seen.add(text.substring(0, 40));
        // Try to get a product name from a nearby heading or parent
        let parent = el.closest('article, li, [class*="product"], [class*="item"], [class*="card"]') || el.parentElement;
        let nameEl = parent ? parent.querySelector('h2, h3, h4, a[title], [class*="title"], [class*="name"]') : null;
        let name = nameEl ? nameEl.textContent.trim().substring(0, 80) : text.substring(0, 60);
        products.push({ name, price: priceMatch[0] });
      }
      if (products.length >= 10) break;
    }
  }

  return products.slice(0, 10);
}

// Build a snapshot of the current page state
function getObservation() {
  const getSelector = (el) => {
    if (!el.hasAttribute('data-navis-id')) {
        el.setAttribute('data-navis-id', `el-${Math.random().toString(36).substr(2, 9)}`);
    }
    return `[data-navis-id="${el.getAttribute('data-navis-id')}"]`;
  };

  const inputEls = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, select')).slice(0, 20);
  const inputs = inputEls.map(el => {
    return {
      type: el.tagName.toLowerCase() === 'textarea' ? 'textarea' : (el.tagName.toLowerCase() === 'select' ? 'select' : el.type),
      placeholder: el.placeholder || undefined,
      aria_label: el.getAttribute('aria-label') || undefined,
      name: el.name || undefined,
      selector: getSelector(el)
    };
  });

  let mainArea = document.querySelector('main, [role="main"], #main, #content, #search');
  let buttonContext = mainArea ? mainArea : document;
  
  const buttonEls = Array.from(buttonContext.querySelectorAll('button, a, [role="button"]'));
  const buttons = buttonEls.map(el => {
    const text = el.textContent.trim().substring(0, 40);
    if (!text && !el.title && !el.getAttribute('aria-label')) return null;
    return {
      text: text || el.title || el.getAttribute('aria-label') || "",
      selector: getSelector(el)
    };
  }).filter(Boolean).slice(0, 100);

  // Extract products with prices
  const products = extractProducts();
  
  // Build a clean page text that leads with product/price data
  let productSection = "";
  if (products.length > 0) {
    productSection = "=== PRODUCTS WITH PRICES FOUND ON THIS PAGE ===\n";
    products.forEach((p, i) => {
      productSection += `${i+1}. ${p.name} — ${p.price}\n`;
    });
    productSection += "=== END PRODUCTS ===\n\n";
  }

  let textNode = mainArea ? mainArea : document.body;
  let rawText = textNode.innerText || "";
  let cleanText = rawText.replace(/\n{3,}/g, '\n\n').substring(0, 4000);

  return {
    url: window.location.href,
    title: document.title,
    page_text: productSection + cleanText,
    buttons: buttons,
    inputs: inputs
  };
}

function highlightElement(el) {
  if (!el) return;
  const originalOutline = el.style.outline;
  const originalTransition = el.style.transition;
  
  el.style.transition = 'outline 0.1s ease-in-out';
  el.style.outline = '4px solid rgba(99, 102, 241, 0.8)';
  el.style.outlineOffset = '2px';
  
  setTimeout(() => {
    el.style.outline = originalOutline;
    el.style.transition = originalTransition;
  }, 1000);
}

function findInputByText(target) {
  if (!target) return null;
  
  // 1. Try exact selector first (e.g. data-navis-id)
  try {
    const el = document.querySelector(target);
    if (el && (el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea' || el.tagName.toLowerCase() === 'select')) return el;
  } catch (e) {}

  let cleanTarget = String(target).toLowerCase();
  const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea');
  
  for (let el of inputs) {
      if (el.placeholder && el.placeholder.toLowerCase().includes(cleanTarget)) return el;
      if (el.name && el.name.toLowerCase() === cleanTarget) return el;
      if (el.id && el.id.toLowerCase() === cleanTarget) return el;
      if (el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes(cleanTarget)) return el;
      if (el.title && el.title.toLowerCase().includes(cleanTarget)) return el;
  }

  if (cleanTarget.includes('search')) {
      for (let el of inputs) {
          if (el.placeholder && el.placeholder.toLowerCase().includes('search')) return el;
          if (el.getAttribute('aria-label') && el.getAttribute('aria-label').toLowerCase().includes('search')) return el;
          if (el.id && el.id.toLowerCase().includes('search')) return el;
          if (el.className && typeof el.className === 'string' && el.className.toLowerCase().includes('search')) return el;
      }
  }

  const labels = document.querySelectorAll('label');
  for (let label of labels) {
      if (label.textContent && label.textContent.toLowerCase().includes(cleanTarget)) {
          if (label.htmlFor) return document.getElementById(label.htmlFor);
          const childInput = label.querySelector('input, textarea');
          if (childInput) return childInput;
      }
  }
  return null;
}

function setNativeValue(element, value) {
  const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
  const prototype = Object.getPrototypeOf(element);
  const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
  
  if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
    prototypeValueSetter.call(element, value);
  } else if (valueSetter) {
    valueSetter.call(element, value);
  } else {
    element.value = value;
  }
}

async function pollForElement(target, isInput = false, maxRetries = 10, interval = 500) {
  for (let i = 0; i < maxRetries; i++) {
      let el = isInput ? findInputByText(target) : findElementByText(target);
      
      if (!el && isInput) {
          el = document.querySelector('input[type="search"]') || 
               document.querySelector('input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"])') || 
               document.querySelector('textarea');
      }
      
      if (el) return el;
      await new Promise(r => setTimeout(r, interval));
  }
  return null;
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
          const el = await pollForElement(target, false);
          if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              highlightElement(el);
              await new Promise(r => setTimeout(r, 1000));
              el.click();
          }
          else { success = false; error = "element not found: " + target; }

        } else if (action_type === "submit") {
          let el = await pollForElement(target, false);
          if (el && el.tagName.toLowerCase() !== 'form') el = el.closest('form');
          if (el) {
              highlightElement(el);
              await new Promise(r => setTimeout(r, 1000));
              el.submit();
          }
          else { success = false; error = "form not found: " + target; }

        } else if (action_type === "scroll") {
          const el = await pollForElement(target, false);
          if (el) {
              highlightElement(el);
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
          else if (target === "down" || value === "down") window.scrollBy(0, window.innerHeight);
          else if (target === "up" || value === "up") window.scrollBy(0, -window.innerHeight);
          else { success = false; error = "element to scroll not found: " + target; }

        } else if (action_type === "wait") {
          const ms = parseInt(value) || parseInt(target) || 2000;
          await new Promise(r => setTimeout(r, ms));

        } else if (action_type === "select_option") {
          let el = await pollForElement(target, false);
          if (el && el.tagName.toLowerCase() !== 'select') el = el.closest('select');
          if (el) {
            const valStr = String(value).toLowerCase();
            const optionToSelect = Array.from(el.options).find(o => o.text.toLowerCase().includes(valStr) || o.value.toLowerCase().includes(valStr));
            if (optionToSelect) {
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              highlightElement(el);
              await new Promise(r => setTimeout(r, 1000));
              el.value = optionToSelect.value;
              el.dispatchEvent(new Event("change", { bubbles: true }));
            } else { success = false; error = "option not found: " + value; }
          } else { success = false; error = "select not found: " + target; }

        } else if (action_type === "press_key") {
          const key = value || target || 'Enter';
          const keyCodeMap = { 'Enter': 13, 'Escape': 27, 'Tab': 9, 'ArrowDown': 40, 'ArrowUp': 38 };
          const code = keyCodeMap[key] || 13;
          const activeEl = document.activeElement || document.body;
          highlightElement(activeEl);
          activeEl.dispatchEvent(new KeyboardEvent('keydown', {key: key, code: key, keyCode: code, which: code, bubbles: true}));
          activeEl.dispatchEvent(new KeyboardEvent('keyup', {key: key, code: key, keyCode: code, which: code, bubbles: true}));

        } else if (action_type === "type") {
          let el = await pollForElement(target, true);
          
          if (!el) {
             // Smart Fallback: It might be a fake search bar (div/button) that opens a modal!
             const fakeBar = await pollForElement(target, false, 3, 500);
             if (fakeBar && fakeBar.tagName.toLowerCase() !== 'input' && fakeBar.tagName.toLowerCase() !== 'textarea') {
                 fakeBar.scrollIntoView({ behavior: 'smooth', block: 'center' });
                 highlightElement(fakeBar);
                 fakeBar.click();
                 await new Promise(r => setTimeout(r, 1000)); // Wait for modal to open
                 el = await pollForElement(target, true, 4, 500); // Try finding the real input again
             }
          }

          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            highlightElement(el);
            await new Promise(r => setTimeout(r, 1000));
            el.focus();
            setNativeValue(el, value || "");
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            if (el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea') {
                el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                el.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                el.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                
                // Aggressive fallback for Amazon and similar sites that intercept standard key events
                const form = el.closest('form');
                if (form) {
                    const submitBtn = form.querySelector('input[type="submit"], button[type="submit"]');
                    if (submitBtn) submitBtn.click();
                    else form.submit();
                }
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