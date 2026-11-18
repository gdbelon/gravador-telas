/**
 * BPMN Process Recorder - Background Service Worker
 * Captura fotos limpas (1s antes e no momento do clique) em TODAS as páginas.
 */

const BUFFER_INTERVAL_MS = 550;
const MAX_BUFFER_FRAMES = 3;

let isRecording = false;
let frameBuffer = [];
let recordedSteps = [];
let bufferTimer = null;

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    isRecording: false,
    stepCount: 0
  });
});

async function captureActiveTab() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) return null;

    const activeTab = tabs[0];
    if (!activeTab.url || activeTab.url.startsWith('chrome://') || activeTab.url.startsWith('chrome-extension://')) {
      return null;
    }

    const dataUrl = await chrome.tabs.captureVisibleTab(null, {
      format: 'jpeg',
      quality: 65
    });

    return dataUrl;
  } catch (err) {
    return null;
  }
}

function startBufferPolling() {
  if (bufferTimer) clearInterval(bufferTimer);

  bufferTimer = setInterval(async () => {
    if (!isRecording) {
      clearInterval(bufferTimer);
      bufferTimer = null;
      return;
    }

    const dataUrl = await captureActiveTab();
    if (dataUrl) {
      frameBuffer.push({
        timestamp: Date.now(),
        dataUrl: dataUrl
      });

      if (frameBuffer.length > MAX_BUFFER_FRAMES) {
        frameBuffer.shift();
      }
    }
  }, BUFFER_INTERVAL_MS);
}

function stopBufferPolling() {
  if (bufferTimer) {
    clearInterval(bufferTimer);
    bufferTimer = null;
  }
  frameBuffer = [];
}

async function handleClickCaptured(metadata) {
  if (!isRecording) return;

  // Foto 1: 1 segundo antes (frame mais antigo do buffer)
  let imageBefore = null;
  if (frameBuffer.length > 0) {
    imageBefore = frameBuffer[0].dataUrl;
  }

  // Foto 2: No momento do clique (captura limpa da tela atual)
  const imageDuring = await captureActiveTab();

  if (!imageBefore) {
    imageBefore = imageDuring;
  }

  const stepNumber = recordedSteps.length + 1;
  const newStep = {
    step_number: stepNumber,
    metadata: metadata,
    image_before: imageBefore,
    image_during: imageDuring
  };

  recordedSteps.push(newStep);

  await chrome.storage.local.set({ stepCount: recordedSteps.length });

  chrome.runtime.sendMessage({
    type: 'STEP_COUNT_UPDATED',
    stepCount: recordedSteps.length
  }).catch(() => {});
}

async function startRecording() {
  isRecording = true;
  recordedSteps = [];
  frameBuffer = [];

  await chrome.storage.local.set({
    isRecording: true,
    stepCount: 0
  });

  const firstFrame = await captureActiveTab();
  if (firstFrame) {
    frameBuffer.push({ timestamp: Date.now(), dataUrl: firstFrame });
  }

  startBufferPolling();
}

async function stopRecordingAndOpenGallery() {
  isRecording = false;
  stopBufferPolling();

  await chrome.storage.local.set({ isRecording: false });

  if (recordedSteps.length === 0) {
    throw new Error('Nenhum clique foi capturado. Navegue e clique em qualquer página antes de finalizar.');
  }

  // Salva no storage local da extensão para visualização direta sem precisar de IA ou servidor
  await chrome.storage.local.set({
    savedGallerySteps: recordedSteps
  });

  // Abre a galeria de fotos diretamente na extensão (instantâneo e 100% confiável)
  const galleryUrl = chrome.runtime.getURL('gallery.html');
  await chrome.tabs.create({ url: galleryUrl });

  // Tenta em segundo plano enviar para o backend (se estiver ligado) sem bloquear o usuário
  try {
    const storage = await chrome.storage.local.get(['apiUrl']);
    const apiUrl = storage.apiUrl || 'http://localhost:8000/api/processar-fluxo';
    fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ steps: recordedSteps })
    }).catch(() => {});
  } catch (e) {}

  return { success: true, count: recordedSteps.length, galleryUrl: galleryUrl };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'START_RECORDING') {
    startRecording()
      .then(() => sendResponse({ success: true }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'STOP_RECORDING') {
    stopRecordingAndOpenGallery()
      .then((data) => sendResponse({ success: true, data: data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'RECORD_CLICK') {
    handleClickCaptured(message.metadata)
      .then(() => sendResponse({ success: true }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'GET_STATUS') {
    sendResponse({
      isRecording: isRecording,
      stepCount: recordedSteps.length
    });
    return false;
  }
});
