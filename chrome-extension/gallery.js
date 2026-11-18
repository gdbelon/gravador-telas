/**
 * BPMN Recorder - Galeria Direta de Fotos
 */

document.addEventListener('DOMContentLoaded', async () => {
  const cardsList = document.getElementById('cardsList');
  const emptyState = document.getElementById('emptyState');
  const badgeTotal = document.getElementById('badgeTotal');
  const btnClear = document.getElementById('btnClear');
  const zoomModal = document.getElementById('zoomModal');
  const zoomImg = document.getElementById('zoomImg');
  const zoomTitle = document.getElementById('zoomTitle');

  const data = await chrome.storage.local.get(['savedGallerySteps']);
  const steps = data.savedGallerySteps || [];

  renderSteps(steps);

  btnClear.addEventListener('click', async () => {
    if (confirm('Deseja realmente limpar as fotos gravadas?')) {
      await chrome.storage.local.set({ savedGallerySteps: [], stepCount: 0 });
      renderSteps([]);
    }
  });

  function renderSteps(items) {
    cardsList.innerHTML = '';

    if (!items || items.length === 0) {
      emptyState.classList.remove('hidden');
      badgeTotal.textContent = '0 fotos';
      return;
    }

    emptyState.classList.add('hidden');
    badgeTotal.textContent = `${items.length * 2} fotos (${items.length} cliques)`;

    items.forEach((item, index) => {
      const stepNum = item.step_number || (index + 1);
      const meta = item.metadata || {};
      const card = document.createElement('div');
      card.className = 'bg-slate-900 border border-slate-800 rounded-3xl p-5 md:p-6 shadow-xl';

      card.innerHTML = `
        <div class="flex flex-wrap items-center justify-between border-b border-slate-800 pb-3 mb-4 gap-2">
          <div class="flex items-center gap-3">
            <span class="w-8 h-8 rounded-xl bg-blue-600 text-white font-black text-sm flex items-center justify-center shadow">
              #${stepNum}
            </span>
            <div>
              <h3 class="text-sm font-bold text-white">${meta.pageTitle || meta.elementText || 'Clique na tela'}</h3>
              <p class="text-[11px] text-slate-400 truncate max-w-md">URL: ${meta.url || 'Página web'}</p>
            </div>
          </div>
          <span class="text-xs bg-slate-800 text-blue-400 font-semibold px-3 py-1 rounded-full border border-slate-700">
            2 Fotos Capturadas
          </span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          
          <!-- Foto 1: 1s antes -->
          <div class="flex flex-col items-center">
            <div class="w-full flex items-center justify-between mb-1.5 px-1">
              <span class="text-xs font-bold text-slate-300">Foto 1: ~1s Antes do Clique</span>
              <span class="text-[10px] text-slate-500">Contexto inicial</span>
            </div>
            <div class="w-full rounded-2xl overflow-hidden border border-slate-800 bg-black aspect-video relative group cursor-pointer shadow"
                 data-img="${item.image_before}" data-title="Clique #${stepNum} - 1s Antes">
              <img src="${item.image_before}" class="w-full h-full object-contain transition-transform group-hover:scale-105" />
              <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span class="bg-white/90 text-slate-900 text-xs font-bold px-3 py-1.5 rounded-full shadow">
                  🔍 Ampliar Foto
                </span>
              </div>
            </div>
          </div>

          <!-- Foto 2: No momento do clique -->
          <div class="flex flex-col items-center">
            <div class="w-full flex items-center justify-between mb-1.5 px-1">
              <span class="text-xs font-bold text-blue-400">Foto 2: No Momento do Clique</span>
              <span class="text-[10px] text-blue-400 font-semibold">Instante da ação</span>
            </div>
            <div class="w-full rounded-2xl overflow-hidden border border-slate-700 bg-black aspect-video relative group cursor-pointer shadow"
                 data-img="${item.image_during}" data-title="Clique #${stepNum} - Momento do Clique">
              <img src="${item.image_during}" class="w-full h-full object-contain transition-transform group-hover:scale-105" />
              <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span class="bg-white/90 text-slate-900 text-xs font-bold px-3 py-1.5 rounded-full shadow">
                  🔍 Ampliar Foto
                </span>
              </div>
            </div>
          </div>

        </div>
      `;

      cardsList.appendChild(card);
    });

    // Eventos de clique nas imagens para zoom
    document.querySelectorAll('[data-img]').forEach(el => {
      el.addEventListener('click', () => {
        zoomImg.src = el.getAttribute('data-img');
        zoomTitle.textContent = el.getAttribute('data-title');
        zoomModal.classList.remove('hidden');
      });
    });
  }

  window.closeModal = function() {
    zoomModal.classList.add('hidden');
  };

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
});
