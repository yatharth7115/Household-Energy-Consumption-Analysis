const data = window.energyData;
const fmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const monthFmt = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const compactMonthFmt = new Intl.DateTimeFormat('en-US', { month: 'short', timeZone: 'UTC' });
const dateOf = (row) => new Date(`${row.month.slice(0, 10)}T00:00:00Z`);
const svgNS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}) => { const el = document.createElementNS(svgNS, tag); for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value); return el; };

function renderTimeline(year = 'all') {
  const rows = year === 'all' ? data.monthly : data.monthly.filter(row => row.month.startsWith(year));
  const chart = document.querySelector('#timeline-svg');
  chart.replaceChildren();
  chart.setAttribute('viewBox', '0 0 1040 340');
  const left = 48, right = 1026, top = 18, bottom = 293;
  const max = Math.ceil(Math.max(...rows.map(row => row.Total_kWh)) / 300) * 300;
  const x = index => left + index * (right - left) / Math.max(1, rows.length - 1);
  const y = value => bottom - value / max * (bottom - top);
  for (let tick = 0; tick <= max; tick += 300) {
    const yy = y(tick);
    chart.append(svg('line', { x1: left, x2: right, y1: yy, y2: yy, class: 'chart-grid' }));
    const label = svg('text', { x: 0, y: yy + 4, class: 'chart-y' }); label.textContent = fmt.format(tick); chart.append(label);
  }
  const points = rows.map((row, index) => [x(index), y(row.Total_kWh)]);
  const path = points.map(([xx, yy], index) => `${index ? 'L' : 'M'}${xx.toFixed(1)} ${yy.toFixed(1)}`).join(' ');
  chart.append(svg('path', { d: `${path} L${x(rows.length - 1)} ${bottom} L${x(0)} ${bottom} Z`, class: 'chart-area' }));
  chart.append(svg('path', { d: path, class: 'chart-line' }));
  const labelIndices = year === 'all' ? [0, 6, 12, 18, 24, 30, 36, 42, rows.length - 1] : [0, 2, 4, 6, 8, 10, rows.length - 1];
  [...new Set(labelIndices)].filter(index => index < rows.length).forEach(index => {
    const label = svg('text', { x: x(index), y: 327, 'text-anchor': index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle', class: 'chart-x' });
    label.textContent = year === 'all' ? `${compactMonthFmt.format(dateOf(rows[index]))} '${String(dateOf(rows[index]).getUTCFullYear()).slice(2)}` : compactMonthFmt.format(dateOf(rows[index]));
    chart.append(label);
  });
  rows.forEach((row, index) => {
    const dot = svg('circle', { cx: x(index), cy: y(row.Total_kWh), r: year === 'all' ? 10 : 12, class: 'chart-point', tabindex: '0', role: 'button', 'aria-label': `${monthFmt.format(dateOf(row))}: ${fmt.format(row.Total_kWh)} kilowatt-hours, ${Math.round(row.coverage * 100)} percent coverage` });
    const show = () => { document.querySelector('#chart-readout').textContent = `${monthFmt.format(dateOf(row))} · ${fmt.format(row.Total_kWh)} kWh observed · ${(row.coverage * 100).toFixed(1)}% coverage`; };
    dot.addEventListener('pointerenter', show); dot.addEventListener('focus', show); dot.addEventListener('click', show);
    chart.append(dot);
  });
  const bars = document.querySelector('#coverage-bars'); bars.replaceChildren();
  rows.forEach(row => { const bar = document.createElement('span'); bar.style.height = `${Math.max(5, row.coverage * 100)}%`; if (row.coverage < .9) bar.classList.add('low'); bar.title = `${monthFmt.format(dateOf(row))}: ${(row.coverage * 100).toFixed(1)}% complete`; bars.append(bar); });
  const total = rows.reduce((sum, row) => sum + row.Total_kWh, 0);
  document.querySelector('#chart-total').textContent = fmt.format(total);
  document.querySelector('.panel-top p span').textContent = year === 'all' ? 'kWh across the dataset' : `kWh observed in ${year}`;
  document.querySelector('#chart-readout').textContent = year === 'all' ? 'Select a point to inspect a month.' : `${year}: ${fmt.format(total)} kWh observed across ${rows.length} months.`;
}
document.querySelectorAll('.year-tabs button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.year-tabs button').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', active); });
  renderTimeline(button.dataset.year);
}));
renderTimeline();

const colors = ['#d4ec67', '#f39c6b', '#b78cdb', '#72c7aa', '#eddfae'];
function renderScatter(model = 'K-Means') {
  const canvas = document.querySelector('#scatter-canvas');
  const box = canvas.parentElement.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(box.width * dpr); canvas.height = Math.round(box.height * dpr);
  const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
  const width = box.width, height = box.height;
  const pad = { left: 32, right: 20, top: 17, bottom: 32 };
  const xs = data.points.map(p => p[0]), ys = data.points.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const sx = value => pad.left + (value - minX) / (maxX - minX) * (width - pad.left - pad.right);
  const sy = value => height - pad.bottom - (value - minY) / (maxY - minY) * (height - pad.top - pad.bottom);
  ctx.strokeStyle = '#394339'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) { const xx = pad.left + i * (width - pad.left - pad.right) / 4; const yy = pad.top + i * (height - pad.top - pad.bottom) / 4; ctx.beginPath(); ctx.moveTo(xx, pad.top); ctx.lineTo(xx, height - pad.bottom); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke(); }
  const column = { 'K-Means': 2, Hierarchical: 3, DBSCAN: 4 }[model];
  const radius = width < 500 ? 2 : 2.5;
  data.points.forEach(point => { const cluster = point[column]; ctx.fillStyle = cluster < 0 ? '#858a80aa' : `${colors[cluster % colors.length]}b0`; ctx.beginPath(); ctx.arc(sx(point[0]), sy(point[1]), radius, 0, Math.PI * 2); ctx.fill(); });
  ctx.fillStyle = '#a8b2a4'; ctx.font = '11px system-ui'; ctx.fillText('PC 1', width - 49, height - 10); ctx.fillText('PC 2', 8, 16);
  document.querySelector('#scatter-title').textContent = model;
  document.querySelectorAll('.score-row').forEach(row => row.classList.toggle('active', row.dataset.model === model));
}
let activeModel = 'K-Means';
document.querySelectorAll('.model-tabs button').forEach(button => button.addEventListener('click', () => {
  activeModel = button.dataset.model;
  document.querySelectorAll('.model-tabs button').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', active); });
  renderScatter(activeModel);
}));
const scoreList = document.querySelector('#score-list');
data.scores.forEach(row => { const item = document.createElement('div'); item.className = 'score-row'; item.dataset.model = row.model; item.innerHTML = `<strong>${row.model}</strong><span>${row.silhouette.toFixed(3)}</span><span>${row.davies_bouldin.toFixed(3)}</span>`; scoreList.append(item); });
new ResizeObserver(() => renderScatter(activeModel)).observe(document.querySelector('.canvas-shell'));

const clusterCopy = [
  { name: 'Moderate, reactive load', detail: 'Moderate active power and the highest average reactive power of the five groups. A common middle-intensity pattern rather than a single appliance signature.', note: 'Reactive power · 0.262 kW' },
  { name: 'High load, channel 1', detail: 'One of the two smallest groups, with high active power and a pronounced reading on the first sub-metering channel.', note: 'Sub-metering 1 · 37.68 Wh/min' },
  { name: 'High load, channel 2', detail: 'Another infrequent high-power pattern, distinguished mainly by the second sub-metering channel.', note: 'Sub-metering 2 · 37.60 Wh/min' },
  { name: 'Channel 3 elevated', detail: 'Nearly a third of sampled minutes. This group has a higher average reading on the third sub-metering channel.', note: 'Sub-metering 3 · 18.01 Wh/min' },
  { name: 'Low-load baseline', detail: 'The largest group has low active power and low readings across all three sub-metering channels.', note: '44.6% of sampled minutes' }
];
const clusterList = document.querySelector('#cluster-list');
data.profiles.forEach(profile => { const index = profile.cluster; const button = document.createElement('button'); button.type = 'button'; button.innerHTML = `<span class="cluster-index">0${index + 1}</span><span>${clusterCopy[index].name}</span><span class="cluster-share">${(profile.sample_fraction * 100).toFixed(1)}%</span>`; button.addEventListener('click', () => renderCluster(index)); clusterList.append(button); });
function renderCluster(index) {
  const profile = data.profiles.find(row => row.cluster === index);
  [...clusterList.children].forEach((button, i) => { button.classList.toggle('active', i === index); button.setAttribute('aria-pressed', i === index); });
  document.querySelector('#cluster-detail').innerHTML = `<small>CLUSTER 0${index + 1} / ${fmt.format(profile.sample_minutes)} SAMPLED MINUTES</small><h4>${clusterCopy[index].name}</h4><p>${clusterCopy[index].detail}</p><div class="detail-bottom"><div><span>Mean active power</span><strong>${profile.Global_active_power.toFixed(2)} kW</strong></div><div><span>Distinctive signal</span><strong style="font-size:18px;line-height:1.3;margin-top:8px">${clusterCopy[index].note}</strong></div></div>`;
}
renderCluster(4);
