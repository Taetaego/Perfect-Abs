const GOAL = { kcal: 2350, carb: 270, protein: 170, fat: 65 };
const KEY = 'perfect-abs-log';
const $ = id => document.getElementById(id);
let repo = {}, data = {};
try { data = JSON.parse(localStorage.getItem(KEY)) || {}; } catch {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(data)); } catch {} };
const iso = d => { const z = new Date(d.getTime() - d.getTimezoneOffset() * 6e4); return z.toISOString().slice(0, 10); };
const sum = (items, k) => items.reduce((a, i) => a + (+i[k] || 0), 0);

$('date').value = iso(new Date());
$('date').onchange = render;

$('form').onsubmit = e => {
  e.preventDefault();
  const d = $('date').value;
  (data[d] ||= []).push({
    meal: $('meal').value, food: $('food').value, kcal: +$('kcal').value,
    carb: +$('carb').value || 0, protein: +$('protein').value || 0, fat: +$('fat').value || 0
  });
  save(); e.target.reset(); render();
};

function render() {
  const d = $('date').value, base = repo[d] || [], local = data[d] || [], items = [...base, ...local];
  const tb = document.querySelector('#log tbody');
  tb.replaceChildren();
  items.forEach((it, i) => {
    const tr = tb.insertRow();
    [it.meal, it.food, it.kcal, it.carb, it.protein, it.fat].forEach(v => tr.insertCell().textContent = v);
    const b = document.createElement('button');
    b.textContent = '✕'; b.setAttribute('aria-label', '삭제');
    b.onclick = () => { local.splice(i - base.length, 1); save(); render(); };
    if (i >= base.length) tr.insertCell().append(b); else tr.insertCell().textContent = '📌';
  });
  const t = { kcal: sum(items, 'kcal'), carb: sum(items, 'carb'), protein: sum(items, 'protein'), fat: sum(items, 'fat') };
  $('kcalBar').style.width = Math.min(100, t.kcal / GOAL.kcal * 100) + '%';
  $('kcalBar').classList.toggle('over', t.kcal > GOAL.kcal);
  const left = GOAL.kcal - t.kcal;
  $('kcalText').textContent = `${t.kcal.toLocaleString()} / ${GOAL.kcal.toLocaleString()} kcal · ` +
    (left >= 0 ? `${left.toLocaleString()} 남음` : `${(-left).toLocaleString()} 초과`);
  $('macros').replaceChildren(...[['carb', '탄수화물'], ['protein', '단백질'], ['fat', '지방']].map(([k, n]) => {
    const el = document.createElement('div');
    el.textContent = `${n} ${t[k]} / ${GOAL[k]}g (남은 ${Math.max(0, GOAL[k] - t[k])}g)`;
    return el;
  }));
  chart(d);
}

function chart(end) {
  const svg = $('chart'), NS = 'http://www.w3.org/2000/svg';
  svg.replaceChildren();
  const add = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text) e.textContent = text; svg.append(e); };
  const base = new Date(end + 'T00:00');
  const max = Math.max(GOAL.kcal * 1.2, ...Object.values(repo).map(v => sum(v, 'kcal')));
  const y = v => 130 - v / max * 120;
  for (let i = 0; i < 7; i++) {
    const dt = new Date(base); dt.setDate(base.getDate() - 6 + i);
    const k = iso(dt), v = sum([...(repo[k] || []), ...(data[k] || [])], 'kcal'), x = 15 + i * 47;
    add('rect', { x, y: y(v), width: 32, height: 130 - y(v), rx: 3, fill: v > GOAL.kcal ? '#dc2626' : '#2563eb' });
    add('text', { x: x + 16, y: 145, 'text-anchor': 'middle' }, k.slice(5));
    if (v) add('text', { x: x + 16, y: y(v) - 3, 'text-anchor': 'middle' }, v);
  }
  add('line', { x1: 0, x2: 350, y1: y(GOAL.kcal), y2: y(GOAL.kcal), stroke: '#16a34a', 'stroke-dasharray': '4' });
}
fetch('data/log.json', { cache: 'no-cache' }).then(r => r.json()).then(j => { repo = j; }).catch(() => {}).finally(render);
