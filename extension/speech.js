// Speech Recognition wrapper
class SpeechHandler {
  constructor(inputElement, micButton) {
    this.inputElement = inputElement;
    this.micButton = micButton;
    this.isRecording = false;
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.setupListeners();
    } else {
      console.warn("Speech Recognition API not supported in this browser.");
      this.micButton.style.display = 'none';
    }
  }

  setupListeners() {
    this.micButton.addEventListener('click', () => {
      if (this.isRecording) {
        this.stop();
      } else {
        this.start();
      }
    });

    this.recognition.onstart = () => {
      this.isRecording = true;
      this.micButton.classList.add('recording');
      this.inputElement.placeholder = "Listening...";
      this.inputElement.value = "";
    };

    this.recognition.onresult = (event) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      this.inputElement.value = transcript;
    };

    this.recognition.onerror = (event) => {
      console.error("Speech error", event.error);
      this.stop();
    };

    this.recognition.onend = () => {
      this.stop();
    };
  }

  start() {
    try {
      this.recognition.start();
    } catch(e) {}
  }

  stop() {
    this.isRecording = false;
    this.micButton.classList.remove('recording');
    this.inputElement.placeholder = "Ask me anything...";
    try {
      this.recognition.stop();
    } catch(e) {}
  }
}

window.SpeechHandler = SpeechHandler;
