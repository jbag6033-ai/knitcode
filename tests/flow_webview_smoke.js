/* A small DOM harness for behavior checks; it does not validate browser layout. */
class MockElement {
  constructor(tag) { this.tag=tag; this.children=[]; this.events={}; this.attrs={}; this.dataset={}; this.value=''; this.textContent=''; }
  append(node) { this.children.push(node); }
  replaceChildren(...nodes) { this.children=nodes; this.textContent=''; }
  addEventListener(type, callback) { this.events[type]=callback; }
  setAttribute(key,value) { this.attrs[key]=value; }
}
const elements=new Map(), listeners={}, messages=[];
const document={
  getElementById(id) { if(!elements.has(id)) elements.set(id,new MockElement('div')); return elements.get(id); },
  createElement(tag) { return new MockElement(tag); },
  querySelector() { return null; }
};
const window={addEventListener(type,callback){listeners[type]=callback;}};
function requestAnimationFrame() {} // Layout is verified separately in a real browser.
function acquireVsCodeApi() { return {postMessage(message){messages.push(message);}}; }
function assert(value,message) { if(!value)throw new Error(message); }
function text(node) { return node.textContent+' '+node.children.map(text).join(' '); }
function find(node,predicate) { if(predicate(node))return node; for(const child of node.children){const match=find(child,predicate);if(match)return match;} }
load('vscode-flow-extension/media/map.js');
const payload=JSON.parse(readFile(arguments[0]));
const target=payload.nodes.find(n=>n.name==='calculate_price');
const peer=payload.nodes.find(n=>n.type==='file'&&n.file!==target.file);
payload.history.available=true;
payload.history.commits=[{sha:'a'.repeat(40),subject:'coupled update',date:'2026-10-15',files:[target.file,peer.file]}];
payload.edges.push({source:'file:'+target.file,target:peer.id,type:'cochange',count:2,commits:['a'.repeat(40)]});
listeners.message({data:{type:'data',data:payload,initialFile:target.file}});
assert(text(elements.get('focus')).includes('calculate_price'),'active editor file determines initial focus');
assert(text(elements.get('flow')).includes('OrderService'),'caller lane shows class context');
assert(text(elements.get('flow')).includes('코드 ↗'),'source actions rendered');
assert(!text(elements.get('flow')).includes('coupled update'),'Git commits remain outside call flow');
const one=layers(target.id,true,1);
assert(one[0].some(id=>id.includes('create_order')),'first incoming step contains caller');
elements.get('more').events.click();
assert(text(elements.get('depth')).includes('2단계'),'expansion updates depth');
assert(text(elements.get('flow')).includes('main'),'second incoming step reaches main');
const evidenceLink=find(elements.get('evidence'),n=>n.tag==='button'&&n.textContent.includes('service.py:'));
assert(evidenceLink,'callsite evidence exists');evidenceLink.events.click();
assert(messages.at(-1).type==='open'&&messages.at(-1).line===7,'evidence opens actual call line');
const commitButton=find(elements.get('history'),n=>n.tag==='button'&&n.textContent.includes('coupled update'));
assert(commitButton,'cochange evidence rendered');commitButton.events.click();
assert(messages.at(-1).type==='commit','commit opens through extension host');
choose(peer.id);
assert(text(elements.get('flow')).includes('이 파일의 함수'),'file selection shows members');
elements.get('back').events.click();
assert(text(elements.get('focus')).includes('calculate_price'),'back restores prior function');
const recursive={source:target.id,target:target.id,type:'calls',lineno:1};
calls.push(recursive);
assert(!layers(target.id,true,3).flat().includes(target.id),'recursive traversal terminates');
listeners.message({data:{type:'data',data:{...payload,nodes:[],edges:[]}}});
assert(text(elements.get('flow')).includes('분석할 Python 코드가 없습니다'),'empty analysis clears prior view');
print('Flow webview: selection, directed expansion, callsite, cochange, back, recursion, empty state OK');
