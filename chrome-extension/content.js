/**
 * BPMN Process Recorder - Content Script
 * Captura todos os cliques possíveis em qualquer página da web e envia para o background.
 */

(function () {
  'use strict';

  if (window.__bpmnRecorderInitialized) return;
  window.__bpmnRecorderInitialized = true;

  let isRecording = false;

  // Sincroniza estado de gravação inicial
  chrome.storage.local.get(['isRecording'], (result) => {
    isRecording = !!result.isRecording;
  });

  // Atualiza estado reativamente
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === 'local' && changes.isRecording !== undefined) {
      isRecording = changes.isRecording.newValue;
    }
  });

  function extractElementText(target) {
    if (!target) return '';
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
      if (target.type === 'password') return '[SENHA]';
      if (target.value && target.value.trim()) {
        return target.value.trim().substring(0, 100);
      }
    }
    const label = target.getAttribute('aria-label') || target.getAttribute('title');
    if (label && label.trim()) return label.trim().substring(0, 100);

    let text = (target.innerText || target.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text && target.parentElement) {
      const p = target.closest('button, a, [role="button"]');
      if (p) text = (p.innerText || p.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    }
    return text.substring(0, 100);
  }

  function handleMouseDown(event) {
    if (!isRecording) return;
    const target = event.target;
    if (!target) return;

    // Metadados da interação
    const metadata = {
      timestamp: Date.now(),
      url: window.location.href,
      pageTitle: document.title || window.location.hostname,
      tagName: target.tagName ? target.tagName.toUpperCase() : 'ELEMENTO',
      elementText: extractElementText(target) || 'Clique na tela',
      elementId: target.id || '',
      coordinates: {
        clientX: event.clientX,
        clientY: event.clientY,
        pageX: event.pageX,
        pageY: event.pageY
      }
    };

    try {
      chrome.runtime.sendMessage({
        type: 'RECORD_CLICK',
        metadata: metadata
      });
    } catch (err) {
      // Ignora erro se canal fechar temporariamente
    }
  }

  // Escuta em fase de captura (true) para capturar em TODOS os elementos de qualquer site
  window.addEventListener('mousedown', handleMouseDown, true);
  window.addEventListener('pointerdown', handleMouseDown, true);

})();
