const axios = require('axios');
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const FormData = require('form-data');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  });

  mainWindow.loadFile('main.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('send-image', async (event, imageData) => {
  try {
    console.log('Sending image to model...');

    // Convert base64 image to binary and send to the Flask server
    const base64Data = imageData.split(',')[1];
    const imageBuffer = Buffer.from(base64Data, 'base64');
    
    const formData = new FormData();
    formData.append('image', imageBuffer, { filename: 'temp_image.jpg' });

    // Send the image to the Flask server
    const response = await axios.post('http://127.0.0.1:5000/predict', formData, {
      headers: formData.getHeaders()
    });

    const prediction = response.data.prediction;
    console.log('Prediction received:', prediction);

    return { prediction };
  } catch (error) {
    console.error('Error in main process:', error);
    return { error: error.message };
  }
});