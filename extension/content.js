// content.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getPageContext') {
    const context = {
      title: document.title,
      url: window.location.href,
      visibleText: document.body.innerText.slice(0, 8000), // limit size
      // Add more later: forms, buttons, inputs
      inputs: Array.from(document.querySelectorAll('input, textarea')).map(el => ({
        placeholder: el.placeholder,
        name: el.name,
        type: el.type,
        value: el.value
      })),
      buttons: Array.from(document.querySelectorAll('button, [role="button"]')).map(el => el.innerText.trim())
    };

    sendResponse({ context: JSON.stringify(context, null, 2) });
    return true;
  }

  if (message.action === 'executeAction') {
    const parts = message.command.split('|');
    const command = parts[0];
    let result = 'Executed';

    try {
      if (command === 'TYPE') {
  const text = parts[1];
  let selector = parts[2];
  let el = document.querySelector(selector);

  // Fallback: find best input if selector fails
  if (!el) {
    el = [...document.querySelectorAll('input[type="text"], input[type="search"], textarea')].find(e =>
      (e.placeholder || '').toLowerCase().includes('search') ||
      (e.name || '').toLowerCase().includes('q') ||
      (e.id || '').toLowerCase().includes('search')
    );
  }

  if (el) {
    el.value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
} else if (command === 'CLICK') {
  const selector = parts[1];
  let el = document.querySelector(selector);

  // Fallback: text-based search for button
  if (!el) {
    el = [...document.querySelectorAll('button, [role="button"], input[type="submit"]')].find(e =>
      (e.innerText || e.value || '').toLowerCase().includes('search') ||
      (e.innerText || e.value || '').toLowerCase().includes('find') ||
      (e.innerText || e.value || '').toLowerCase().includes('go')
    );
  }

  if (el) el.click();
}
      // Add NAVIGATE, SCROLL later
    } catch (e) {
      result = `Error: ${e.message}`;
    }

    sendResponse({ result });
    return true;
  }
});