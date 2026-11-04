/* Twelve comparison layouts over the same application, routes and records. */
(() => {
  const key = document.documentElement.dataset.layout;
  const designs = {
    focus: ['01', 'Focus', 'Linear'],
    registry: ['02', 'Registry', 'Shopify Admin'],
    panorama: ['03', 'Panorama', 'Stripe Dashboard'],
    notebook: ['04', 'Notebook', 'GitHub Primer'],
    triage: ['05', 'Triage', 'Sentry'],
    fieldbook: ['06', 'Fieldbook', 'Mailchimp'],
    board: ['07', 'Board', 'Trello'],
    atlas: ['08', 'Atlas', 'ArcGIS'],
    chronicle: ['09', 'Chronicle', 'Basecamp'],
    workbench: ['10', 'Workbench', 'Airtable'],
    folio: ['11', 'Folio', 'Notion'],
    dispatch: ['12', 'Dispatch', 'Asana'],
  };
  if (!designs[key]) return;
  const [number, name, reference] = designs[key];
  const bar = document.createElement('nav');
  bar.className = 'design-bar';
  bar.setAttribute('aria-label', 'Interface comparison');
  bar.innerHTML = `<a href="/designs">← All 12 designs</a><span><b>${number} / ${name}</b><span class="design-reference"> · ${reference}</span></span><a href="/?palette=honey#welcome">Current version ↗</a>`;
  if (document.documentElement.dataset.layoutPreview === 'true') document.querySelector('.workspace').prepend(bar);
  if (['board','atlas','chronicle','workbench','folio','dispatch'].includes(key)) return;

  const overview = document.getElementById('view-overview');
  const stats = document.getElementById('overview-stats');
  const attention = document.getElementById('attention');
  const hives = document.getElementById('hives-panel');
  const maps = document.getElementById('farm-maps');
  const conditions = document.getElementById('farm-conditions');
  const area = document.createElement('div');
  area.className = 'layout-workspace';
  overview.append(area);

  const environment = document.createElement('details');
  environment.className = 'layout-environment';
  environment.innerHTML = '<summary>Yard maps & weather <span>Locations, drift exposure and local conditions</span></summary>';
  environment.append(maps, conditions);
  if (key === 'focus') {
    area.append(hives, attention);
  } else if (key === 'registry') {
    area.append(hives);
    const review = document.createElement('details');
    review.className = 'layout-review';
    review.innerHTML = '<summary>Inspection follow-up <span>Review the latest hive alerts</span></summary>';
    review.append(attention);
    area.before(review);
    const updateReview = () => {
      review.hidden = attention.hidden;
      const count = attention.querySelectorAll('.attention-row').length;
      review.querySelector('summary').firstChild.textContent = `Inspection follow-up · ${count} ${count === 1 ? 'hive' : 'hives'} `;
    };
    updateReview();
    new MutationObserver(updateReview).observe(attention, {childList: true, attributes: true, attributeFilter: ['hidden']});
  } else if (key === 'panorama') {
    area.append(maps, attention);
    overview.append(hives);
    environment.querySelector('summary').innerHTML = 'Local weather <span>Conditions at your farms</span>';
  } else if (key === 'triage') {
    const queue = document.createElement('div');
    queue.className = 'layout-queue';
    queue.append(attention, hives);
    area.append(stats, queue);
  } else if (key === 'fieldbook') {
    area.append(hives);
    overview.append(attention);
    // Keep the real table and all cells; label them when shown as hive cards.
    const labels = ['Hive', 'Farm', 'Source', 'Status', 'Mites per day', 'Change', 'Honey', 'Brood', 'Stores', 'Last inspection', ''];
    const labelCells = () => document.querySelectorAll('#hive-grid tr').forEach(row => {
      [...row.children].forEach((cell, i) => cell.dataset.label = labels[i]);
    });
    labelCells();
    new MutationObserver(labelCells).observe(document.getElementById('hive-grid'), {childList: true});
  } else {
    area.append(hives);
    overview.append(attention);
  }
  overview.append(environment);
  if (key !== 'fieldbook') {
    const columns = document.createElement('button');
    columns.type = 'button';
    columns.className = 'btn sm layout-columns';
    columns.textContent = 'All measurements';
    columns.setAttribute('aria-pressed', 'false');
    columns.setAttribute('aria-controls', 'hive-table-wrap');
    columns.addEventListener('click', () => {
      const expanded = columns.getAttribute('aria-pressed') !== 'true';
      columns.setAttribute('aria-pressed', String(expanded));
      columns.textContent = expanded ? 'Key measurements' : 'All measurements';
      hives.dataset.columns = expanded ? 'all' : 'key';
    });
    hives.dataset.columns = 'key';
    hives.querySelector('.hive-list-title').append(columns);
  }
  if (key === 'panorama') {
    const simplifyMaps = () => maps.querySelectorAll('.farm-map:not([data-layout-ready])').forEach(map => {
      map.dataset.layoutReady = 'true';
      const guide = document.createElement('details');
      guide.className = 'layout-map-guide';
      guide.innerHTML = '<summary>How to read this map</summary>';
      const explanation = map.querySelector('.map-explain');
      const legend = map.querySelector('.map-legend');
      if (explanation) guide.append(explanation);
      if (legend) guide.append(legend);
      map.append(guide);
    });
    simplifyMaps();
    new MutationObserver(simplifyMaps).observe(maps, {childList: true});
  }
})();
