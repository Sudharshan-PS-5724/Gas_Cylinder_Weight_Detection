const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  sendImage: (imageData) => ipcRenderer.invoke('send-image', imageData),
  stopCapture: () => ipcRenderer.send('stop-capture'),
  downloadExcel: () => ipcRenderer.send('download-excel'),
  waitInput: (input) => ipcRenderer.send('wait-input', input)
});

ipcRenderer.on('input-stored', (event, data) => {
  window.dispatchEvent(new CustomEvent('input-stored', { detail: data }));
});

ipcRenderer.on('excel-downloaded', (event, data) => {
  window.dispatchEvent(new CustomEvent('excel-downloaded', { detail: data }));
});
