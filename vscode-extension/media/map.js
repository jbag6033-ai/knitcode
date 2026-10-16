/* All project strings are rendered as text, never as markup. */
const api = acquireVsCodeApi();
const $ = id => document.getElementById(id);
let data, selected, visible = new Set();
const ns = 'http://www.w3.org/2000/svg';
function element(tag, text, parent, action) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
  if (parent) parent.append(el); if (action) el.addEventListener('click', action); return el;
}
function svg(tag, attrs, parent) {
  const el = document.createElementNS(ns, tag);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,v);
  parent.append(el); return el;
}
function select(id) { selected = id; visible = new Set([id]); expand(); }
function expand() {
  if (!data || !selected) return;
  const previous = new Set(visible);
  for (const edge of data.edges) {
    if (previous.has(edge.source)) visible.add(edge.target);
    if (previous.has(edge.target)) visible.add(edge.source);
  }
  draw(); detail();
}
function tree() {
  $('tree').replaceChildren();
  const query = $('search').value.toLowerCase();
  for (const file of data.nodes.filter(n => n.type === 'file')) {
    const children = data.nodes.filter(n => n.file === file.file && n.type !== 'file');
    const match = n => `${n.name} ${n.file}`.toLowerCase().includes(query);
    if (!match(file) && !children.some(match)) continue;
    const group = element('details', undefined, $('tree')); group.open = !!query;
    element('summary', file.file, group);
    element('button', '파일 관계 보기', group, () => select(file.id)).className = 'symbol';
    for (const node of children.filter(match)) element('button', node.name, group, () => select(node.id)).className = 'symbol';
  }
}
function draw() {
  const graph = $('graph'); graph.replaceChildren();
  const nodes = data.nodes.filter(n => visible.has(n.id));
  // Bound rendering, while keeping the selected node visible and disclosing the limit.
  nodes.sort((a,b) => Number(b.id === selected) - Number(a.id === selected));
  const shown = nodes.slice(0,60), positions = new Map();
  shown.forEach((n,i) => {
    const angle = (i-1) * Math.PI * 2 / Math.max(1,shown.length-1);
    positions.set(n.id, i === 0 ? [450,325] : [450+330*Math.cos(angle),325+260*Math.sin(angle)]);
  });
  const defs = svg('defs',{},graph), marker = svg('marker',{id:'arrow',viewBox:'0 0 10 10',refX:10,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'},defs);
  svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#6899ba'},marker);
  const edges = data.edges.filter(e => positions.has(e.source) && positions.has(e.target));
  for (const edge of edges) {
    const [x1,y1] = positions.get(edge.source), [x2,y2] = positions.get(edge.target);
    const dx=x2-x1, dy=y2-y1, length=Math.hypot(dx,dy)||1;
    const line = svg('line',{x1,y1,x2:x2-dx/length*65,y2:y2-dy/length*25,class:edge.type},graph);
    if (['calls','instantiates'].includes(edge.type)) line.setAttribute('marker-end','url(#arrow)');
  }
  for (const node of shown) {
    const [x,y]=positions.get(node.id);
    const group = svg('g',{class:`node ${node.type} ${node.id===selected?'current':''}`,tabindex:0,role:'button','aria-label':node.name},graph);
    svg('rect',{x:x-76,y:y-22,width:152,height:44,rx:9},group);
    const label=svg('text',{x,y:y+4,'text-anchor':'middle'},group); label.textContent=node.name.length>21?node.name.slice(0,20)+'…':node.name;
    svg('title',{},group).textContent=`${node.file} · ${node.name}`;
    const pick=()=>{selected=node.id;detail();draw();};
    group.addEventListener('click',pick); group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});
  }
  $('relations').replaceChildren();
  element('small',`${shown.length}/${nodes.length} 노드 표시 (최대 60). 연결을 선택하면 근거를 확인합니다.`,$('relations'));
  for (const edge of edges.filter(e => e.source===selected || e.target===selected)) {
    const source=data.nodes.find(n=>n.id===edge.source), target=data.nodes.find(n=>n.id===edge.target);
    element('button',`${source.name} → ${target.name} · ${edge.type}${edge.lineno?` · ${source.file}:${edge.lineno}`:''}${edge.count?` · ${edge.count} 커밋`:''}`,$('relations'),()=>{
      if(edge.type==='cochange') showCommits(edge.commits);
      else if(edge.type==='contains') select(edge.target);
      else api.postMessage({type:'open',id:edge.source,line:edge.lineno});
    });
  }
}
function showCommits(hashes) {
  const box=$('detail'); element('h3','공동 변경 근거',box);
  for(const hash of hashes){const c=data.history.commits.find(c=>c.sha===hash);if(c)element('button',`${hash.slice(0,8)} · ${c.subject}`,box,()=>api.postMessage({type:'commit',sha:hash}));}
}
function detail() {
  const node=data.nodes.find(n=>n.id===selected); if(!node)return;
  const box=$('detail');box.replaceChildren();
  element('small',node.type.toUpperCase(),box);element('h2',node.name,box);
  element('p',`${node.file}:${node.lineno||1}`,box);
  element('button','코드 열기',box,()=>api.postMessage({type:'open',id:node.id}));
  if(node.type!=='file')element('button','소속 파일 관계',box,()=>select('file:'+node.file));
  element('p',node.type==='file'?'구조적 중요도: 함수 노드를 선택하세요.':`구조적 중요도: ${node.callers>=5?'높음':node.callers>=2?'보통':'낮음'} · 서로 다른 호출자 ${node.callers}개`,box);
  element('small','호출자 수 기준: 0–1 낮음 / 2–4 보통 / 5 이상 높음. 정적 분석 후보입니다.',box);
  element('p',data.history.available?`파일 변경 빈도: ${node.changes>=10?'높음':node.changes>=3?'보통':'낮음'} · ${node.changes} 커밋`:'Git 이력 없음',box);
  element('small',`최근 ${data.history.days}일, 최대 ${data.history.limit}개 비병합 커밋. 0–2 낮음 / 3–9 보통 / 10 이상 높음. 공동 변경은 2회 이상, 50파일 초과 커밋 제외 (${data.history.skipped_large_commits}개).`,box);
  if(data.history.available){element('h3','파일 변경 이력',box);for(const c of data.history.commits.filter(c=>c.files.includes(node.file)))element('button',`${c.sha.slice(0,8)} · ${c.subject}`,box,()=>api.postMessage({type:'commit',sha:c.sha}));}
}
$('search').addEventListener('input',()=>{if(data)tree();});
$('expand').addEventListener('click',expand);
$('reset').addEventListener('click',()=>{if(selected)select(selected);});
$('refresh').addEventListener('click',()=>api.postMessage({type:'refresh'}));
window.addEventListener('message',({data:message})=>{
  if(message.type==='status')$('status').textContent=message.text;
  if(message.type==='data'){
    data=message.data;const s=data.summary;
    $('status').textContent=`${s.files} Python 파일 · 해석된 호출 후보 ${s.resolved} · 미해석 ${s.unresolved} · 저장된 소스 기준${data.warnings.length?` · 파싱 제외 ${data.warnings.length}: ${data.warnings.join('; ')}`:''}${data.history.error?' · Git: '+data.history.error:''}${data.flow.converged?'':' · 값 흐름 반복 한도 도달'}`;
    tree(); if(data.nodes.length)select(data.nodes.find(n=>n.id===selected)?.id||data.nodes[0].id);
    else{$('graph').replaceChildren();$('relations').replaceChildren();$('detail').textContent='분석할 Python 파일이 없습니다.';}
  }
});
api.postMessage({type:'ready'});
