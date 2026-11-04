"use strict";
// Reference-only archive: no operational hive writes, model calls or inferred alerts.
let researchData = null;
let researchLoading = false;
let researchHiveId = null;
const studyCountry = code => ({ PT: "Portugal", DK: "Denmark" }[code] || code);
const studyTime = date => Date.parse(`${date}T12:00:00Z`);

function fieldChart(rows, allDates, label, scatter = false) {
  if (!rows.length) return '<p class="muted">No observations for this hive.</p>';
  const W = 820, H = 230, left = 52, right = 18, top = 20, bottom = scatter ? 63 : 35;
  const times = allDates.map(studyTime);
  const first = Math.min(...times), last = Math.max(...times);
  const values = rows.filter(r => r.value != null && Number.isFinite(r.value)).map(r => r.value);
  const min = scatter ? 0 : Math.floor(Math.min(...values) / 10) * 10;
  const max = Math.max(min + 1, scatter ? Math.ceil(Math.max(0, ...values) * 1.15) : Math.ceil(Math.max(...values) / 10) * 10);
  const x = d => left + (studyTime(d) - first) / Math.max(86400000, last - first) * (W - left - right);
  const y = v => H - bottom - (v - min) / (max - min) * (H - bottom - top);
  let contents = '';
  for (let i = 0; i < 4; i++) {
    const value = min + (max - min) * i / 3, pos = y(value);
    contents += `<line class="gridline" x1="${left}" x2="${W-right}" y1="${pos}" y2="${pos}"/><text x="${left-10}" y="${pos+4}" text-anchor="end">${num(value, 1)}</text>`;
  }
  if (scatter) {
    const lodY = H - bottom + 22;
    contents += `<text x="${left-10}" y="${lodY+4}" text-anchor="end">&lt;LOD</text>`;
    contents += rows.map(r => `<circle class="${r.value == null ? 'lod-dot' : 'sample-dot'}" cx="${x(r.date)}" cy="${r.value == null ? lodY : y(r.value)}" r="4.5"><title>${esc(r.date)} · ${r.value == null ? 'Below detection limit; not zero' : num(r.value, 3) + ' mites / 100 bees'} · ${esc(r.source_id)}</title></circle>`).join('');
  } else {
    // Break lines across missing days. No interpolated observations.
    let previous = null;
    const d = rows.map(r => {
      const command = previous && studyTime(r.date) - studyTime(previous.date) <= 86400000 ? 'L' : 'M';
      previous = r;
      return `${command}${x(r.date).toFixed(2)},${y(r.value).toFixed(2)}`;
    }).join(' ');
    contents += `<path class="series" d="${d}"/>`;
    contents += rows.map(r => `<circle class="sample-dot" cx="${x(r.date)}" cy="${y(r.value)}" r="1.4"><title>${esc(r.date)} · ${num(r.value,3)} kg · ${r.n} readings</title></circle>`).join('');
  }
  for (let i = 0; i < 5; i++) {
    const t = first + (last-first)*i/4, pos = left+(W-left-right)*i/4;
    const text = new Date(t).toLocaleDateString('en-GB', {month:'short', year:'numeric',timeZone:'UTC'});
    contents += `<text x="${pos}" y="${H-5}" text-anchor="${i===0?'start':i===4?'end':'middle'}">${text}</text>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${contents}</svg>`;
}

function renderStudyHive() {
  const hive = researchData.hives.find(h => h.id === researchHiveId) || researchData.hives[0];
  researchHiveId = hive.id;
  $('research-hive-detail').innerHTML = studyHiveMarkup(hive);
}

function studyHiveMarkup(hive) {
  const dates = [...hive.weight, ...hive.varroa].map(r => r.date).sort();
  return `
    <h2>${esc(hive.site)} <span class="muted">/ ${esc(hive.id)}</span></h2>
    <p class="muted">${esc(studyCountry(hive.country))} · Original study hive ${esc(hive.hive_no)} · ${dateLabel(dates[0])} – ${dateLabel(dates.at(-1))}</p>
    <div class="research-chart"><h3>Colony weight <span class="muted">· kg</span></h3><p class="hint">Daily mean of scale readings. Whole-colony weight, not honey yield. Gaps remain gaps.</p>${fieldChart(hive.weight, dates, 'Daily mean colony weight in kilograms over the original sampling dates')}</div>
    <div class="research-chart"><h3>Varroa samples <span class="muted">· mites per 100 adult bees</span></h3><p class="hint">Soapy water method. Each dot is one sample. Open dots below the axis mean below detection limit, not zero.</p>${fieldChart(hive.varroa, dates, 'Varroa wash observations in mites per 100 adult bees', true)}</div>
    <div class="research-table-wrap"><table><caption class="sr-only">Original Varroa observations for ${esc(hive.id)}</caption><thead><tr><th>Sampling date</th><th>Mites / 100 bees</th><th>Result</th><th>Source record</th></tr></thead><tbody>${hive.varroa.map(r => `<tr><td>${dateLabel(r.date)}</td><td>${r.value == null ? '&lt;LOD' : num(r.value,3)}</td><td>${r.value == null ? 'Below detection limit' : 'Numeric observation'}</td><td><code>${esc(r.source_id)}</code></td></tr>`).join('') || '<tr><td colspan="4">No wash observations linked to this hive.</td></tr>'}</tbody></table></div>
    <p class="hint">The source does not provide a numeric detection limit for these &lt;LOD rows. No infestation status is inferred.</p>`;
}

function downloadStudyHive() {
  const hive = researchData.hives.find(h => h.id === researchHiveId);
  const result = { source: researchData.source_url, paper: researchData.paper_url, license: researchData.license,
    attribution: researchData.attribution, transformations: researchData.transformations, hive };
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = `MUST-B_${hive.id}.json`;
  a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function renderResearch() {
  if (researchData || researchLoading) return;
  researchLoading = true;
  try {
    researchData = await api('/api/research/mustb');
    const d = researchData;
    const countries = [...new Set(d.hives.map(h => h.country))].sort();
    $('research-content').innerHTML = `
      <div class="research-summary"><div><strong>${d.summary.hives}</strong><span>study hives</span></div><div><strong>2019–2020</strong><span>original observation dates</span></div><div><strong>${num(d.summary.daily_weights,0)}</strong><span>daily weight observations</span></div><div><strong>${d.summary.varroa_samples}</strong><span>Varroa wash samples</span></div></div>
      <div class="panel"><div class="research-toolbar"><label>Choose a study hive<span class="research-select"><select id="research-hive">${countries.map(country => `<optgroup label="${esc(studyCountry(country))}">${d.hives.filter(h => h.country===country).map(h => `<option value="${esc(h.id)}" ${h.id===d.hives[0].id?'selected':''}>${esc(h.site)} · ${esc(h.id)} · ${h.varroa.length} wash samples</option>`).join('')}</optgroup>`).join('')}</select><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m7 10 5 5 5-5"/></svg></span></label><button class="btn" type="button" id="research-download">Download hive data</button></div><div class="research-body" id="research-hive-detail"></div></div>
      <details class="research-details"><summary>Sources, transformations and exclusions</summary><p>${esc(d.attribution)} <a href="${esc(d.license_url)}" target="_blank" rel="noopener">${esc(d.license)}</a>.</p><ul>${d.transformations.map(t=>`<li>${esc(t)}</li>`).join('')}<li>The study describes six experimental apiaries. The archive has seven site IDs because Flakkebjerg has an additional 2020 ID; these are not seven separate farms.</li><li>Excluded: ${d.omitted_varroa['Mite down-fall in 24h']} mite-fall samples with conflicting units, ${d.unmatched_weight_rows} weight rows without a matching master hive, and ${d.excluded_dates.length} rows dated outside the campaign.</li></ul><p><a href="${esc(apiUrl('/api/research/mustb'))}" target="_blank" rel="noopener">Complete normalized archive and source checksums ↗</a></p></details>`;
    researchHiveId = d.hives[0].id;
    $('research-hive').addEventListener('change', event => { researchHiveId = event.target.value; renderStudyHive(); });
    $('research-download').addEventListener('click', downloadStudyHive);
    renderStudyHive();
  } catch (error) {
    researchData = null;
    $('research-content').innerHTML = `<p class="alert">Could not load the archive: ${esc(error.message)}</p><button class="btn" type="button" id="research-retry">Try again</button>`;
    $('research-retry').addEventListener('click', renderResearch);
  } finally { researchLoading = false; }
}
if (view === 'research') renderResearch();

function fieldSourceMarkup(source) {
  return `<div class="reference-context"><strong>Published field study · ${esc(source.site || 'EFSA MUST-B')}</strong><p>Original observations from the 2019–2020 EFSA MUST-B study. Imported from the published dataset; these are historical measurements, not current hive status or a HiveLens field deployment.</p><div class="reference-links"><a href="${esc(source.source_url)}" target="_blank" rel="noopener">Dataset ↗</a><a href="${esc(source.paper_url)}" target="_blank" rel="noopener">Scientific report ↗</a><a href="${esc(source.license_url)}" target="_blank" rel="noopener">${esc(source.license)}</a></div></div>`;
}

function renderImportedApiaries(all, farm) {
  const holder = $('imported-apiaries');
  const imported = all.filter(h => h.field_archive);
  holder.hidden = !imported.length;
  const archivedOnly = all.length > 0 && all.every(h => h.field_archive && !h.inspection_count);
  $('overview-stats').classList.toggle('research-kpis', archivedOnly);
  $('hives-panel').hidden = archivedOnly;
  if (!imported.length) { holder.innerHTML = ''; return; }
  const archiveFarms = farms().filter(f => f.field_archive && imported.some(h => h.farm_id === f.id));
  holder.innerHTML = archiveFarms.map(f => {
    const source = f.field_archive;
    const members = imported.filter(h => h.farm_id === f.id).sort(byHiveName);
    return `<section class="panel imported-apiary"><header class="panel-head"><div class="panel-title-group"><h2>${esc(f.name)}</h2><span class="sub-text">${esc(f.location)} · ${members.length} study hives · ${dateLabel(source.date_range[0])} – ${dateLabel(source.date_range[1])}</span></div><span class="tag">Research archive</span></header><div class="research-body">${fieldSourceMarkup(source)}<div class="research-table-wrap"><table><caption class="sr-only">Imported historical hives from ${esc(f.name)}</caption><thead><tr><th>Study hive</th><th>Recorded dates</th><th>Weight observations</th><th>Latest weight</th><th>Varroa wash samples</th><th><span class="sr-only">Open history</span></th></tr></thead><tbody>${members.map(h => {
      const a = h.field_archive;
      return `<tr><td><strong>${esc(a.study_hive_id)}</strong></td><td>${dateLabel(a.date_range[0])}<br><span class="muted">to ${dateLabel(a.date_range[1])}</span></td><td>${num(a.daily_weights,0)} days</td><td>${a.latest_weight ? `${num(a.latest_weight.value,2)} kg<br><span class="hint">${dateLabel(a.latest_weight.date)}</span>` : '—'}</td><td>${a.varroa_samples} samples</td><td><button class="btn sm" type="button" data-hive="${esc(h.id)}" data-destination="history">View history</button></td></tr>`;
    }).join('')}</tbody></table></div><p class="hint">Weight means the whole colony on its scale, not honey yield. Varroa wash results are mites per 100 adult bees. Open a hive for dated observations, methods and source record IDs.</p></div></section>`;
  }).join('');
  if (archivedOnly) {
    const dates = imported.flatMap(h => h.field_archive.date_range).sort();
    $('overview-sub').textContent = `${farm ? farm.location : archiveFarms.map(f=>f.location).join(' · ')}. Published field observations with original hive IDs and dates.`;
    $('overview-stats').innerHTML = kpi('Study hives', imported.length, 'Original research identifiers') +
      kpi('Daily weights', num(imported.reduce((n,h)=>n+h.field_archive.daily_weights,0),0), 'Colony scale · kg') +
      kpi('Varroa samples', imported.reduce((n,h)=>n+h.field_archive.varroa_samples,0), 'Soapy water method') +
      kpi('Observation years', `${dates[0].slice(0,4)}–${dates.at(-1).slice(0,4)}`, 'Historical field campaign');
  }
}

function renderImportedHistory(archive) {
  const holder = $('history-field-archive');
  holder.hidden = !archive;
  holder.innerHTML = archive ? `<section class="panel imported-apiary"><div class="research-body">${fieldSourceMarkup({...archive,site:archive.hive.site})}${studyHiveMarkup(archive.hive)}<details class="research-details"><summary>Data provenance and transformations</summary><p>${esc(archive.attribution)}</p><ul>${archive.transformations.map(t=>`<li>${esc(t)}</li>`).join('')}</ul><p>Export ZIP includes the original imported observation series in field_history.json, with attribution and source checksums.</p></details></div></section>` : '';
}
