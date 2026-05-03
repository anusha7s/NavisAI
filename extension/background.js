// Set side panel behavior to open on action click
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error(error));

// The rest of the background script will act as a bridge for taking screenshots 
// or calling chrome.debugger when the backend requests it via SSE or content script.

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "CAPTURE_SCREENSHOT") {
    chrome.tabs.captureVisibleTab(null, {format: 'png'}, (dataUrl) => {
      sendResponse({ dataUrl: dataUrl });
    });
    return true; // Keep channel open for async response
  }
});