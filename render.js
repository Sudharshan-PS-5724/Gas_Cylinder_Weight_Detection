const startButton = document.getElementById('start-button');
const stopButton = document.getElementById('stop-button');
const captureButton = document.getElementById('capture-button');
const analyzeButton = document.getElementById('analyze-button');
const waitButton = document.getElementById('wait-button');
const numInput = document.getElementById('num_wait');
const enterButton = document.getElementById('enter');
const prediction = document.getElementById('hehe');
const canvas = document.getElementById('captured-image');
const ctx = canvas.getContext('2d');
const video = document.getElementById('webcam');
let stream

stopButton.addEventListener('click', () => {
  window.electron.stopCapture();
});

analyzeButton.addEventListener('click', () => {
  window.electron.downloadExcel();
});

waitButton.addEventListener('click', () => {
  numInput.style.visibility = 'visible';
  enterButton.style.visibility = 'visible';
});

enterButton.addEventListener('click', () => {
  const input = numInput.value;
  window.electron.waitInput(input);
});

startButton.addEventListener('click', async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    prediction.innerText = '';
  } catch (error) {
    console.error('Error accessing webcam:', error);
    prediction.innerText = 'Error accessing webcam.';
  }
});

captureButton.addEventListener('click', () => {
  if (video.srcObject) {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL('image/jpeg');
    prediction.innerText = 'Processing...';
    sendImageToModel(imageData);
  }
});

// Feedback after the Download button writes the results sheet.
window.addEventListener('excel-downloaded', (event) => {
  const data = event.detail || {};
  if (data.error) {
    prediction.innerText = `Download: ${data.error}`;
  } else {
    prediction.innerText = `Saved ${data.count} reading(s) to ${data.path}`;
  }
});

async function sendImageToModel(imageData) {
  try {
    const { prediction: predictionText, error } = await window.electron.sendImage(imageData);
    if (error) {
      console.error('Error received from main process:', error);
      prediction.innerText = `Error: ${error}`;
    } else {
      console.log('Prediction received:', predictionText);
      prediction.innerText = `Prediction: ${predictionText}`;
    }
  } catch (error) {
    console.error('Error sending image to model:', error);
    prediction.innerText = 'Error sending image to model.';
  }
}