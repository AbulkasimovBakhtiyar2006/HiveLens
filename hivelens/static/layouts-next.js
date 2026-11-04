/* Second set of layout studies. Derived views use the existing filtered hive rows.
   No extra requests, fake records or parallel application state. */
(() => {
  const key = document.documentElement.dataset.layout;
  if (!['board', 'atlas', 'chronicle', 'workbench', 'folio', 'dispatch'].includes(key)) return;
  const byId = id => document.getElementById(id);
  const overview = byId('view-overview');
  const stats = byId('overview-stats');
  const attention = byId('attention');
  const hives = byId('hives-panel');
  const maps = byId('farm-maps');
  const weather = byId('farm-conditions');
  const rows = byId('hive-grid');
  const area = document.createElement('div');
  area.className = 'next-main';
  overview.append(area);
  const fold = (title, nodes) => {
    const details = document.createElement('details');
    details.className = 'layout-environment';
    const summary = document.createElement('summary');
    summary.textContent = title;
    details.append(summary, ...nodes);
    if (nodes.length === 1 && nodes[0] === attention) {
      const sync = () => { details.hidden = attention.hidden; };
      sync();
      new MutationObserver(sync).observe(attention, {attributes:true, attributeFilter:['hidden']});
    }
    return details;
  };
  const element = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  };
  const copy = (row, index) => {
    const box = element('div', 'next-cell');
    for (const child of row.children[index].childNodes) box.append(child.cloneNode(true));
    return box;
  };
  const hiveId = row => row.querySelector('[data-hive]').dataset.hive;
  const status = row => ['act', 'watch', 'good'].find(s => row.querySelector('.badge')?.classList.contains(s)) || 'unknown';
  const metrics = row => {
    const grid = element('dl', 'next-metrics');
    for (const [index, label] of [[4,'Mites / day'],[6,'Honey'],[7,'Brood'],[8,'Stores']]) {
      const item = element('div');
      item.append(element('dt', '', label), element('dd', '', row.children[index].textContent.trim()));
      grid.append(item);
    }
    return grid;
  };
  const card = row => {
    const article = element('article', 'next-hive');
    article.dataset.status = status(row);
    const head = element('div', 'next-hive-head');
    head.append(copy(row, 2), copy(row, 3));
    const name = element('h3');
    name.append(row.children[0].firstElementChild.cloneNode(true));
    article.append(head, name, element('p', 'next-location', row.children[1].textContent), metrics(row));
    const footer = element('div', 'next-hive-foot');
    footer.append(element('span', '', row.children[9].textContent), row.children[10].firstElementChild.cloneNode(true));
    article.append(footer);
    return article;
  };
  const observe = fn => { fn(); new MutationObserver(fn).observe(rows, {childList:true}); };
  const canvas = element('div', 'next-canvas');
  canvas.id = 'layout-derived-hives';
  const derived = ['board', 'chronicle', 'workbench', 'dispatch'].includes(key);
  if (derived) {
    hives.classList.add('has-derived-view');
    hives.insertBefore(canvas, byId('hive-empty'));
  }
  const environment = fold('Yard maps & local weather', [maps, weather]);

  if (key === 'board') {
    area.append(hives);
    overview.append(fold('Review inspection alerts', [attention]), environment);
    hives.querySelector('h2').textContent = 'Hive status board';
    const note = element('p', 'next-view-note', 'Grouped by the latest inspection. Status changes when new measurements are recorded.');
    hives.querySelector('.hive-list-title').after(note);
    observe(() => {
      canvas.replaceChildren();
      const current = [...rows.children];
      canvas.hidden = current.length === 0;
      for (const [state, title] of [['act','Critical'],['watch','Watch'],['good','Normal'],['unknown','No data']]) {
        const group = element('section', 'board-lane');
        group.dataset.status = state;
        const matches = current.filter(row => status(row) === state);
        const heading = element('h3', 'board-lane-title');
        heading.append(element('span','',title),element('span','board-count',String(matches.length)));
        group.append(heading);
        for (const row of matches) group.append(card(row));
        if (!matches.length) group.append(element('p','lane-empty','No matching hives'));
        canvas.append(group);
      }
    });
  } else if (key === 'atlas') {
    const summary = element('div','atlas-summary');
    const demoNote = byId('atlas-demo-note');
    demoNote.before(summary);
    summary.append(demoNote,stats);
    area.append(maps, hives);
    const review = fold('Inspection review', [attention]);
    review.classList.add('atlas-review');
    const reviewSummary = review.querySelector('summary');
    const syncReview = () => {
      const entries = [...attention.querySelectorAll('.attention-row')];
      const demo = entries.filter(row => row.querySelector('.tag.demo')).length;
      const measured = entries.length - demo;
      reviewSummary.replaceChildren(element('strong','','Inspection review'),element('span','',`${measured} measured ${measured === 1 ? 'hive' : 'hives'} to review · ${demo} demo ${demo === 1 ? 'example' : 'examples'}`));
    };
    syncReview();
    new MutationObserver(syncReview).observe(attention,{childList:true});
    area.before(review);
    overview.append(fold('Local weather', [weather]));
    const farms = document.querySelector('.farm-nav');
    farms.classList.add('atlas-farms');
    const comparison = document.querySelector('.design-bar');
    if (comparison) comparison.after(farms);
    else document.querySelector('.workspace').prepend(farms);
    document.querySelectorAll('.side-nav a').forEach(link => {
      link.setAttribute('title',link.textContent.trim());
      link.setAttribute('aria-label',link.textContent.trim());
    });
    // A compact map-side index; the complete measurements remain in the record.
    const labelCells = () => [...rows.children].forEach(row => {
      [...row.children].forEach((cell,i) => cell.dataset.label = ['Hive','Farm','Source','Status','Mites / day','Change','Honey','Brood','Stores','Last inspection',''][i]);
    });
    observe(labelCells);
    const simplify = () => maps.querySelectorAll('.farm-map:not([data-atlas-ready])').forEach(map => {
      map.dataset.atlasReady = 'true';
      const guide = fold('Map legend & drift details', []);
      for (const selector of ['.map-explain','.map-legend','.drift-sidebar']) {
        const node = map.querySelector(selector);
        if (node) guide.append(node);
      }
      guide.open = Boolean(map.querySelector('.map-node.selected'));
      map.append(guide);
    });
    simplify();
    new MutationObserver(simplify).observe(maps, {childList:true});
  } else if (key === 'chronicle') {
    area.append(hives, stats);
    overview.append(fold('Review inspection alerts', [attention]),environment);
    hives.querySelector('h2').textContent = 'Latest inspections';
    hives.querySelector('.hive-list-title').after(element('p','next-view-note','The latest inspection of each hive, grouped by date. Open a record for its complete history.'));
    observe(() => {
      canvas.replaceChildren();
      const groups = new Map();
      [...rows.children].forEach(row => {
        const label = row.children[9].textContent.replace(/\s*\(\d+\)\s*$/, '').trim();
        if (!groups.has(label)) groups.set(label,[]);
        groups.get(label).push(row);
      });
      canvas.hidden = !groups.size;
      const timestamp = value => value === 'None' ? -Infinity : Date.parse(value);
      [...groups].sort(([a],[b]) => timestamp(b)-timestamp(a)).forEach(([date, members]) => {
        const section = element('section','chronicle-day');
        const heading = element('h3','chronicle-date', date === 'None' ? 'Not inspected' : date);
        const entries = element('div','chronicle-entries');
        members.forEach(row => {
          const entry = element('article','chronicle-entry');
          const title = element('h4'); title.append(row.children[0].firstElementChild.cloneNode(true));
          const tags = element('div','chronicle-tags'); tags.append(copy(row,2),copy(row,3));
          entry.append(title,element('p','next-location',row.children[1].textContent),tags,metrics(row),row.children[10].firstElementChild.cloneNode(true));
          entries.append(entry);
        });
        section.append(heading,entries); canvas.append(section);
      });
    });
  } else if (key === 'workbench') {
    area.append(hives);
    overview.append(fold('Apiary summary & inspection alerts', [stats,attention]),environment);
    hives.querySelector('h2').textContent = 'Record browser';
    const list = element('div','workbench-list');
    list.setAttribute('role','group'); list.setAttribute('aria-label','Select a hive to preview');
    const detail = element('section','workbench-detail'); detail.setAttribute('aria-label','Selected hive measurements');
    canvas.append(list,detail);
    let selected = null;
    const choose = (row, focus = false) => {
      selected = hiveId(row);
      list.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.reviewHive === selected)));
      detail.replaceChildren();
      const eyebrow = element('p','workbench-eyebrow','Latest inspection · '+row.children[9].textContent);
      const title = element('h2','',row.children[0].textContent);
      const tags = element('div','workbench-tags'); tags.append(copy(row,2),copy(row,3));
      const open = row.children[10].firstElementChild.cloneNode(true); open.textContent='Open full hive record →';open.className='btn primary';
      detail.append(eyebrow,title,element('p','next-location',row.children[1].textContent),tags,metrics(row),element('p','next-view-note','Open the hive record to review photos, evidence and recommendations.'),open);
      if (focus) detail.scrollIntoView({block:'nearest',behavior:'instant'});
    };
    observe(() => {
      const current = [...rows.children]; list.replaceChildren(); detail.replaceChildren(); canvas.hidden = !current.length;
      current.forEach(row => {
        const button = element('button','workbench-item'); button.type='button';button.dataset.reviewHive=hiveId(row);
        button.append(element('strong','',row.children[0].textContent),element('span','',row.children[1].textContent));
        const tags=element('span','workbench-item-tags'); tags.append(copy(row,2),element('span','badge '+status(row),row.querySelector('.badge').textContent));button.append(tags);
        button.addEventListener('click',()=>choose(row,true));list.append(button);
      });
      if(current.length) choose(current.find(row=>hiveId(row)===selected)||current[0]);
    });
  } else if (key === 'folio') {
    hives.dataset.columns = 'key';
    const columns = element('button', 'btn sm layout-columns', 'All measurements');
    columns.type = 'button'; columns.setAttribute('aria-pressed','false'); columns.setAttribute('aria-controls','hive-table-wrap');
    columns.addEventListener('click',()=>{const expanded=columns.getAttribute('aria-pressed')!=='true';columns.setAttribute('aria-pressed',String(expanded));columns.textContent=expanded?'Key measurements':'All measurements';hives.dataset.columns=expanded?'all':'key';});
    hives.querySelector('.hive-list-title').append(columns);
    const tabs = element('div','folio-tabs'); tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Apiary views');
    const panels = [['hives','Hives',[hives]],['health','Health summary',[stats,attention]],['yard','Yard & weather',[maps,weather]]].map(([id,label,nodes],i)=>{
      const panel=element('section','folio-panel');panel.id='folio-'+id;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','folio-tab-'+id);panel.tabIndex=0;panel.hidden=i!==0;panel.append(...nodes);
      const button=element('button','',label);button.type='button';button.id='folio-tab-'+id;button.setAttribute('role','tab');button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-selected',String(i===0));button.tabIndex=i===0?0:-1;
      button.addEventListener('click',()=>{tabs.querySelectorAll('button').forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1;});area.querySelectorAll('.folio-panel').forEach(p=>p.hidden=p!==panel);});
      tabs.append(button);return panel;
    });
    tabs.addEventListener('keydown',event=>{
      const buttons=[...tabs.querySelectorAll('button')];const i=buttons.indexOf(document.activeElement);if(i<0)return;
      const next=event.key==='ArrowRight'?(i+1)%buttons.length:event.key==='ArrowLeft'?(i+buttons.length-1)%buttons.length:event.key==='Home'?0:event.key==='End'?buttons.length-1:null;
      if(next!==null){event.preventDefault();buttons[next].click();buttons[next].focus();}
    });
    area.append(tabs,...panels);
  } else if (key === 'dispatch') {
    area.append(hives);
    overview.append(attention,environment);
    hives.querySelector('h2').textContent='Hives by farm';
    observe(()=>{
      canvas.replaceChildren();const groups=new Map();
      [...rows.children].forEach(row=>{const farm=row.children[1].textContent;if(!groups.has(farm))groups.set(farm,[]);groups.get(farm).push(row);});
      canvas.hidden=!groups.size;
      for(const [farm,members] of groups){
        const section=element('details','dispatch-farm');section.open=true;
        const summary=element('summary');summary.append(element('strong','',farm),element('span','',members.length+' '+(members.length===1?'hive':'hives')));section.append(summary);
        for(const row of members){const line=element('article','dispatch-row');line.append(copy(row,0),copy(row,2),copy(row,3),metrics(row),row.children[10].firstElementChild.cloneNode(true));section.append(line);}
        canvas.append(section);
      }
    });
  }
})();
