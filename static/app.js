const input = document.querySelector('#image-input');
const dropZone = document.querySelector('#drop-zone');
const previewWrap = document.querySelector('#preview-wrap');
const preview = document.querySelector('#preview');
const analyze = document.querySelector('#analyze-button');
const form = document.querySelector('#upload-form');
const resultCard = document.querySelector('#result-card');

function showFile(file) {
  if (!file || !file.type.startsWith('image/')) return;
  const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
  preview.src = URL.createObjectURL(file); dropZone.classList.add('hidden'); previewWrap.classList.remove('hidden'); analyze.disabled = false;
}
document.querySelector('#browse-button').onclick = () => input.click();
dropZone.onclick = () => input.click();
input.onchange = () => showFile(input.files[0]);
dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragging'); };
dropZone.ondragleave = () => dropZone.classList.remove('dragging');
dropZone.ondrop = (e) => { e.preventDefault(); dropZone.classList.remove('dragging'); showFile(e.dataTransfer.files[0]); };
document.querySelector('#remove-button').onclick = () => { input.value = ''; previewWrap.classList.add('hidden'); dropZone.classList.remove('hidden'); analyze.disabled = true; };

form.onsubmit = async (event) => {
  event.preventDefault(); analyze.disabled = true; analyze.innerHTML = 'Analyzing image <span>…</span>';
  resultCard.innerHTML = '<div class="result-empty"><div class="sparkle">✦</div><h2>Looking closely…</h2><p>Our AI is identifying the item and its best next destination.</p></div>';
  try {
    const response = await fetch('/api/classify', { method:'POST', body:new FormData(form) });
    const data = await response.json(); if (!response.ok) throw new Error(data.error);
    const details = data.category_details, percent = Math.round(data.confidence * 100), demo = data.demo ? '<p class="demo-note">Demo mode: add GEMINI_API_KEY for live image identification.</p>' : '';
    resultCard.innerHTML = `<div class="result"><span class="result-label">We spotted</span><h2>${escapeHtml(data.item || 'Unknown item')}</h2><span class="pill ${details.color}">${details.label}</span><p>${escapeHtml(data.reason || details.description)}</p><div class="confidence"><i style="width:${percent}%"></i></div><span class="confidence-text">${percent ? `${percent}% confidence` : 'Awaiting AI configuration'}</span><p class="tip"><strong>Next step:</strong> ${escapeHtml(data.preparation || details.tip)}</p>${demo}</div>`;
  } catch (error) { resultCard.innerHTML = `<div class="result-empty"><div class="sparkle">!</div><h2>Something went wrong</h2><p>${escapeHtml(error.message)}</p></div>`; }
  analyze.disabled = false; analyze.innerHTML = 'Analyze my waste <span>→</span>';
};
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = value; return div.innerHTML; }
