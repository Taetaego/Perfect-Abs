const GOAL = { kcal: 2350, carb: 270, protein: 170, fat: 65 };
const $ = id => document.getElementById(id);
const iso = d => { const z = new Date(d.getTime() - d.getTimezoneOffset() * 6e4); return z.toISOString().slice(0, 10); };
const sum = (items, k) => items.reduce((a, i) => a + (+i[k] || 0), 0);
const REPO = 'taetaego/perfect-abs', PATH = 'data/log.json';
const cfg = { get token() { try { return localStorage.getItem('pa-token') || ''; } catch { return ''; } },
              get branch() { try { return localStorage.getItem('pa-branch') || 'ccr-c0a6bca3-fu3lns'; } catch { return 'ccr-c0a6bca3-fu3lns'; } } };
let data = {}, sha = null;
const status = m => { $('status').textContent = m; };
const api = (method, body) => fetch(`https://api.github.com/repos/${REPO}/contents/${PATH}?ref=${encodeURIComponent(cfg.branch)}`, {
  method, cache: 'no-store',
  headers: { Authorization: `Bearer ${cfg.token}`, Accept: 'application/vnd.github+json' },
  body: body && JSON.stringify({ ...body, branch: cfg.branch })
});
const dec = b64 => JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64.replace(/\n/g, '')), c => c.charCodeAt(0))));
const enc = obj => { const bytes = new TextEncoder().encode(JSON.stringify(obj, null, 2) + '\n'); let s = ''; bytes.forEach(b => s += String.fromCharCode(b)); return btoa(s); };

async function load() {
  try {
    if (cfg.token) {
      const r = await api('GET');
      if (!r.ok) throw new Error('GitHub ' + r.status);
      const j = await r.json(); sha = j.sha; data = dec(j.content);
    } else {
      data = await (await fetch(PATH, { cache: 'no-cache' })).json();
      status('읽기 전용: 저장하려면 ⚙ 에서 GitHub 토큰을 설정하세요.');
    }
  } catch (e) { status('불러오기 실패: ' + e.message); }
  render();
}

// 항상 최신 파일을 받아 변경을 적용한 뒤 커밋 (충돌 방지)
async function commit(mutate, message) {
  if (!cfg.token) { status('⚙ 에서 GitHub 토큰을 먼저 설정하세요.'); return false; }
  try {
    status('GitHub에 저장 중…');
    const g = await api('GET');
    if (!g.ok) throw new Error('GitHub ' + g.status);
    const cur = await g.json(), next = dec(cur.content);
    mutate(next);
    const p = await api('PUT', { message, content: enc(next), sha: cur.sha });
    if (!p.ok) throw new Error('GitHub ' + p.status);
    sha = (await p.json()).content.sha; data = next;
    status('저장됨 ✓ (' + new Date().toLocaleTimeString() + ')');
    return true;
  } catch (e) { status('저장 실패: ' + e.message); return false; }
}

$('date').value = iso(new Date());
$('date').onchange = render;

$('form').onsubmit = async e => {
  e.preventDefault();
  const d = $('date').value, entry = {
    meal: $('meal').value, food: $('food').value, kcal: +$('kcal').value,
    carb: +$('carb').value || 0, protein: +$('protein').value || 0, fat: +$('fat').value || 0
  };
  if (await commit(n => (n[d] ||= []).push(entry), `식단 추가: ${d} ${entry.food}`)) { e.target.reset(); render(); }
};

$('settings').onclick = () => {
  const t = prompt('GitHub 토큰 (이 저장소 Contents 쓰기 권한만 있는 fine-grained 토큰). 비우면 삭제', cfg.token);
  if (t === null) return;
  const b = prompt('저장할 브랜치', cfg.branch);
  try { localStorage.setItem('pa-token', t.trim()); if (b) localStorage.setItem('pa-branch', b.trim()); } catch {}
  load();
};

function render() {
  const d = $('date').value, items = data[d] || [];
  const tb = document.querySelector('#log tbody');
  tb.replaceChildren();
  items.forEach((it, i) => {
    const tr = tb.insertRow();
    [it.meal, it.food, it.kcal, it.carb, it.protein, it.fat].forEach(v => tr.insertCell().textContent = v);
    const b = document.createElement('button');
    b.textContent = '✕'; b.setAttribute('aria-label', '삭제');
    b.onclick = async () => { if (await commit(n => n[d]?.splice(i, 1), `식단 삭제: ${d} ${it.food}`)) render(); };
    tr.insertCell().append(b);
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
  const max = Math.max(GOAL.kcal * 1.2, ...Object.values(data).map(v => sum(v, 'kcal')));
  const y = v => 130 - v / max * 120;
  for (let i = 0; i < 7; i++) {
    const dt = new Date(base); dt.setDate(base.getDate() - 6 + i);
    const k = iso(dt), v = sum(data[k] || [], 'kcal'), x = 15 + i * 47;
    add('rect', { x, y: y(v), width: 32, height: 130 - y(v), rx: 3, fill: v > GOAL.kcal ? '#dc2626' : '#2563eb' });
    add('text', { x: x + 16, y: 145, 'text-anchor': 'middle' }, k.slice(5));
    if (v) add('text', { x: x + 16, y: y(v) - 3, 'text-anchor': 'middle' }, v);
  }
  add('line', { x1: 0, x2: 350, y1: y(GOAL.kcal), y2: y(GOAL.kcal), stroke: '#16a34a', 'stroke-dasharray': '4' });
}
load();
