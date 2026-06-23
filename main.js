const axios = require('axios');
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const FormData = require('form-data');
const ExcelJS = require('exceljs');

let mainWindow;

// Accumulated successful readings for this session: { no, time, weight }.
// Each successful prediction is added here; the Download button writes them out.
const results = [];
let cylinderCount = 0;

// Where the inference backend lives. Defaults to the Release Share link for the
// laptop container, so on the Pi you can just run `npm start`.
// Override per-run with GCWD_SERVER when needed, e.g. for an all-local setup:
//   GCWD_SERVER=http://127.0.0.1:5000 npm start
const DEFAULT_SERVER = 'https://meet-marten-55.rshare.io';
const SERVER_URL = (process.env.GCWD_SERVER || DEFAULT_SERVER).replace(/\/+$/, '');

// Full-screen kiosk (no window chrome) when GCWD_KIOSK=1 — the Pi launcher sets
// this. Left unset everywhere else, so `npm start` stays windowed for dev.
const KIOSK = process.env.GCWD_KIOSK === '1';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 700,
    kiosk: KIOSK,
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
    const response = await axios.post(`${SERVER_URL}/predict`, formData, {
      headers: formData.getHeaders()
    });

    const prediction = response.data.prediction;
    const error = response.data.error;
    console.log('Prediction received:', prediction ?? error);

    // A successful reading is a real weight (not an error / not unreadable).
    if (!error && prediction && prediction !== "Couldn't be read") {
      cylinderCount += 1;
      results.push({
        no: cylinderCount,
        time: new Date().toLocaleString(),
        weight: prediction,
      });
      console.log(`Saved reading #${cylinderCount}: ${prediction}`);
    }

    return { prediction, error };
  } catch (error) {
    console.error('Error in main process:', error);
    return { error: error.message };
  }
});

// Download button: write the accumulated readings to an .xlsx the user picks.
ipcMain.on('download-excel', async () => {
  try {
    if (results.length === 0) {
      mainWindow.webContents.send('excel-downloaded', { error: 'No readings yet.' });
      return;
    }

    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Readings');
    sheet.columns = [
      { header: 'Cylinder No.', key: 'no', width: 14 },
      { header: 'Time', key: 'time', width: 26 },
      { header: 'Weight', key: 'weight', width: 12 },
    ];
    results.forEach((row) => sheet.addRow(row));

    const { canceled, filePath } = await dialog.showSaveDialog(mainWindow, {
      title: 'Save readings',
      defaultPath: path.join(app.getPath('downloads'), 'gas_cylinder_results.xlsx'),
      filters: [{ name: 'Excel Workbook', extensions: ['xlsx'] }],
    });
    if (canceled || !filePath) return;

    await workbook.xlsx.writeFile(filePath);
    mainWindow.webContents.send('excel-downloaded', {
      path: filePath,
      count: results.length,
    });
  } catch (err) {
    console.error('Error writing results:', err);
    mainWindow.webContents.send('excel-downloaded', { error: err.message });
  }
});