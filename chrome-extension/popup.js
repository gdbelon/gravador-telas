/**
 * BPMN Recorder - Popup Script
 */

document.addEventListener('DOMContentLoaded', async () => {
  const btnStart = document.getElementById('btnStart');
  const btnStop = document.getElementById('btnStop');
  const btnOpenGallery = document.getElementById('btnOpenGallery');
  const stepCounter = document.getElementById('stepCounter');
  const photoCounter = document.getElementById('photoCounter');
  const statusBadge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  const errorBox = document.getElementById('errorBox');

  const storage = await chrome.storage.local.get(['isRecording', 'stepCount']);
  const isRecording = !!storage.isRecording;
  const stepCount = storage.stepCount || 0;

  updateUI(isRecording, stepCount);

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === 'local') {
      if (changes.isRecording !== undefined) {
        chrome.storage.local.get(['stepCount'], (res) => {
          updateUI(changes.isRecording.newValue, res.stepCount || 0);
        });
      }
      if (changes.stepCount !== undefined) {
        const val = changes.stepCount.newValue || 0;
        stepCounter.textContent = val;
        photoCounter.textContent = `${val * 2} fotos`;
      }
    }
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'STEP_COUNT_UPDATED') {
      stepCounter.textContent = message.stepCount;
      photoCounter.textContent = `${message.stepCount * 2} fotos`;
    }
  });

  btnStart.addEventListener('click', () => {
    hideError();
    chrome.runtime.sendMessage({ type: 'START_RECORDING' }, (res) => {
      if (res && res.success) {
        updateUI(true, 0);
      } else {
        showError('Erro ao iniciar: ' + (res?.error || 'Desconhecido'));
      }
    });
  });

  btnStop.addEventListener('click', () => {
    hideError();
    chrome.runtime.sendMessage({ type: 'STOP_RECORDING' }, (res) => {
      if (res && res.success) {
        updateUI(false, 0);
        window.close(); // Fecha popup pois a aba da galeria já abre
      } else {
        showError(res?.error || 'Erro ao finalizar gravação.');
      }
    });
  });

  btnOpenGallery.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('gallery.html') });
  });

  function updateUI(recording, count) {
    stepCounter.textContent = count;
    photoCounter.textContent = `${count * 2} fotos`;

    if (recording) {
      statusBadge.className = 'badge-status recording';
      statusText.textContent = 'Gravando';
      btnStart.style.display = 'none';
      btnStop.style.display = 'flex';
    } else {
      statusBadge.className = 'badge-status';
      statusText.textContent = 'Pronto';
      btnStart.style.display = 'flex';
      btnStop.style.display = 'none';
    }
  }

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.style.display = 'block';
  }

  function hideError() {
    errorBox.style.display = 'none';
    errorBox.textContent = '';
  }
});
