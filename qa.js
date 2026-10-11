/* Static questions and full law articles remain readable without JavaScript. */
(() => {
  'use strict';
  const form = document.getElementById('qaSearchForm');
  if (!form) return;
  const input = document.getElementById('qaSearch');
  const clear = document.getElementById('qaClearSearch');
  const resultCount = document.getElementById('qaResultCount');
  const empty = document.getElementById('qaEmpty');
  const expand = document.getElementById('qaExpandAll');
  const collapse = document.getElementById('qaCollapseAll');
  const items = Array.from(document.querySelectorAll('.qa-item'));
  const groups = Array.from(document.querySelectorAll('.qa-group'));
  const categories = Array.from(document.querySelectorAll('[data-category-filter]'));
  const normalize = text => text.normalize('NFKC').toLowerCase().replace(/\s+/g, '');
  const searchText = new Map(items.map(item => [item, normalize(item.textContent + ' ' + item.dataset.keywords)]));
  let currentCategory = 'all';
  const categoryTitle = () => categories.find(button => button.dataset.categoryFilter === currentCategory).querySelector('span').textContent;
  const visibleItems = () => items.filter(item => !item.hidden);

  function update() {
    const query = input.value.trim();
    const tokens = query.split(/\s+/).filter(Boolean).map(normalize);
    const questionMatch = query.normalize('NFKC').match(/^q\s*(\d+)$/i);
    for (const item of items) {
      const matches = questionMatch ? item.id === 'q' + Number(questionMatch[1]) : tokens.every(token => searchText.get(item).includes(token));
      item.hidden = (currentCategory !== 'all' && item.dataset.category !== currentCategory) || !matches;
    }
    for (const group of groups) {
      const count = Array.from(group.querySelectorAll('.qa-item')).filter(item => !item.hidden).length;
      group.hidden = count === 0;
      group.querySelector('.qa-group-count').textContent = count + ' 題';
    }
    const count = visibleItems().length;
    resultCount.textContent = categoryTitle() + (query ? '，搜尋「' + query + '」' : '') + '，共 ' + count + ' 題';
    empty.hidden = count !== 0;
    clear.hidden = !query;
    expand.disabled = count === 0;
    collapse.disabled = count === 0;
    categories.forEach(button => {
      const selected = button.dataset.categoryFilter === currentCategory;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }

  function reset() { input.value = ''; currentCategory = 'all'; update(); }
  form.addEventListener('submit', event => { event.preventDefault(); update(); });
  input.addEventListener('input', update);
  clear.addEventListener('click', () => { input.value = ''; update(); input.focus(); });
  categories.forEach(button => button.addEventListener('click', () => {
    currentCategory = button.dataset.categoryFilter;
    update();
    const results = document.getElementById('qaResults');
    if (results.getBoundingClientRect().top < 0) results.scrollIntoView({block:'start', behavior:'auto'});
  }));
  expand.addEventListener('click', () => visibleItems().forEach(item => { item.open = true; }));
  collapse.addEventListener('click', () => visibleItems().forEach(item => { item.open = false; }));
  document.getElementById('qaResetFilters').addEventListener('click', () => { reset(); input.focus(); });
  document.querySelectorAll('[data-close-question]').forEach(button => button.addEventListener('click', () => {
    const item = document.getElementById(button.dataset.closeQuestion);
    item.open = false;
    item.querySelector('summary').focus();
    item.scrollIntoView({ block:'start', behavior:'auto' });
  }));
  function openLinkedQuestion() {
    const item = items.find(entry => '#' + entry.id === location.hash);
    if (!item) return;
    reset(); item.open = true;
    item.scrollIntoView({ block:'start', behavior:'auto' });
  }
  window.addEventListener('hashchange', openLinkedQuestion);

  document.querySelectorAll('.qa-figure-details').forEach(details => {
    details.addEventListener('toggle', () => {
      details.querySelector('summary span').textContent = details.open ? '點圖可放大' : '展開圖片';
    });
  });

  const viewer = document.getElementById('qaImageViewer');
  if (viewer) {
    const picture = document.getElementById('qaImageContent');
    const viewport = viewer.querySelector('.qa-image-viewer__viewport');
    const fit = document.getElementById('qaImageFit');
    const natural = document.getElementById('qaImageNatural');
    const error = document.getElementById('qaImageError');
    let pictureTrigger = null;
    function setPictureSize(originalSize) {
      viewport.classList.toggle('is-original-size', originalSize);
      fit.setAttribute('aria-pressed', String(!originalSize));
      natural.setAttribute('aria-pressed', String(originalSize));
      viewport.scrollTop = 0;
      viewport.scrollLeft = 0;
    }
    document.querySelectorAll('[data-qa-image]').forEach(link => {
      link.addEventListener('click', event => {
        if (typeof viewer.showModal !== 'function') return;
        event.preventDefault();
        pictureTrigger = link;
        document.getElementById('qaImageTitle').textContent = link.dataset.title;
        document.getElementById('qaImageOriginal').href = link.href;
        error.hidden = true;
        picture.hidden = false;
        picture.alt = link.querySelector('img').alt;
        picture.src = link.href;
        setPictureSize(false);
        viewer.showModal();
      });
    });
    picture.addEventListener('error', () => { error.hidden = false; picture.hidden = true; });
    fit.addEventListener('click', () => setPictureSize(false));
    natural.addEventListener('click', () => setPictureSize(true));
    document.getElementById('qaImageClose').addEventListener('click', () => viewer.close());
    viewer.addEventListener('close', () => {
      if (pictureTrigger?.isConnected) pictureTrigger.focus();
    });
  }
  update(); openLinkedQuestion();
})();
