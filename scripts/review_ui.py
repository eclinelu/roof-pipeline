# Builds the interactive visual-review page: ONE self-contained HTML file,
# opened directly from disk. No server, no build step, no Python dependency
# beyond the standard library, and nothing running in the background while
# Emmett works.
#
# Images are referenced by RELATIVE PATH rather than embedded as data URIs.
# The close-ups are 2 to 5 MB each and 29 of them inlined would make a
# 100 MB page that no browser opens comfortably. Relative paths keep the page
# small and mean a re-render updates the pictures without regenerating the UI.
#
# The review DATA is inlined, because a page opened over file:// cannot fetch()
# a sibling JSON: the browser treats every local file as a separate origin and
# blocks it. Inlining is not a shortcut here, it is the only thing that works.
#
# DESIGN CONSTRAINTS, all from Emmett and all load-bearing:
#   - one facet per screen, close-up at full size, overview as a small inset,
#     so it is always obvious WHERE on the building the current facet is
#   - a key for every button; 29 facets x 4 fields is too much clicking
#   - autosave, so closing the tab does not lose the pass
#   - `unsure` styled EXACTLY like every other option. An interface that makes
#     the decisive answers look more attractive than the honest one is
#     collecting the reviewer's compliance, not their judgement
#   - pitch and area hidden by default, so the outline is judged against the
#     roof before a plausible number can talk him into accepting a boundary he
#     would otherwise have questioned. This is the same principle as
#     ground-truth-is-audit-only, applied to the reviewer instead of the code.
import json

IDENTITY = [("correct", "1"), ("merge", "2"), ("split", "3"),
            ("spurious", "4"), ("unsure", "5")]
BOUNDARY = [("tight", "q"), ("short", "w"), ("over", "e"), ("ragged", "r"),
            ("cut", "t"), ("unsure", "y")]
SEVERITY = [("minor", "a"), ("moderate", "s"), ("major", "d")]
LOCATION = [("N", "z"), ("NE", "x"), ("E", "c"), ("SE", "v"), ("S", "b"),
            ("SW", "n"), ("W", "m"), ("NW", ","), ("multiple", ".")]
LINE_VERDICT = [("correct", "1"), ("mistyped", "2"), ("misplaced", "3"),
                ("spurious", "4"), ("short", "5"), ("long", "6"),
                ("unsure", "7")]


def _js(obj):
    """Embed JSON in a <script> tag safely. A literal </script> inside a
    string would end the tag early and break the page."""
    return json.dumps(obj).replace("</", "<\\/")


def build_review_html(data, name, stamp):
    facets = data["facets"]
    lines = data["intersection_lines"]
    cfg = dict(identity=IDENTITY, boundary=BOUNDARY, severity=SEVERITY,
               location=LOCATION, lineVerdict=LINE_VERDICT)
    return _TEMPLATE.replace("__DATA__", _js(data)) \
                    .replace("__CFG__", _js(cfg)) \
                    .replace("__NAME__", name) \
                    .replace("__STAMP__", stamp) \
                    .replace("__NFACETS__", str(len(facets))) \
                    .replace("__NLINES__", str(len(lines)))


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__NAME__ visual review __STAMP__</title>
<style>
  :root{
    --bg:#14171c; --panel:#1c2027; --line:#2c323c; --ink:#e8ecf2;
    --dim:#98a2b3; --accent:#00e5ff; --on:#1d6fa5; --warn:#ff2d95;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:14px/1.45 ui-sans-serif,system-ui,"Segoe UI",Roboto,sans-serif}
  header{display:flex;align-items:center;gap:14px;padding:8px 14px;
         background:var(--panel);border-bottom:1px solid var(--line);
         position:sticky;top:0;z-index:30}
  header h1{font-size:15px;margin:0;font-weight:650}
  .grow{flex:1}
  .bar{height:5px;background:var(--line);border-radius:3px;width:220px;
       overflow:hidden}
  .bar > div{height:100%;background:var(--accent);width:0}
  main{display:grid;grid-template-columns:1fr 420px;gap:0;
       height:calc(100vh - 47px)}
  #stage{overflow:auto;background:#0c0e11;display:flex;align-items:flex-start;
         justify-content:center;padding:10px}
  #stage img.big{max-width:100%;height:auto;display:block}
  aside{overflow-y:auto;padding:14px 16px 60px;background:var(--panel);
        border-left:1px solid var(--line)}
  h2{font-size:16px;margin:0 0 2px}
  .sub{color:var(--dim);font-size:12px;margin-bottom:12px}
  fieldset{border:1px solid var(--line);border-radius:8px;margin:0 0 12px;
           padding:9px 11px 11px}
  legend{color:var(--dim);font-size:11px;letter-spacing:.09em;
         text-transform:uppercase;padding:0 5px}
  .opts{display:flex;flex-wrap:wrap;gap:6px}
  /* Every option, including `unsure`, uses this one rule. There is
     deliberately no variant that makes any answer look preferable. */
  button.opt{background:#232935;color:var(--ink);border:1px solid var(--line);
             border-radius:7px;padding:7px 10px;cursor:pointer;font-size:13px;
             font-family:inherit;display:flex;align-items:center;gap:6px}
  button.opt:hover{border-color:var(--accent)}
  button.opt.on{background:var(--on);border-color:var(--accent);font-weight:650}
  button.opt kbd{background:#0e1116;border:1px solid var(--line);
                 border-radius:4px;padding:0 5px;font-size:11px;color:var(--dim)}
  button.opt.on kbd{color:#dff3ff;border-color:#4aa8d8}
  textarea{width:100%;min-height:78px;background:#0e1116;color:var(--ink);
           border:1px solid var(--line);border-radius:7px;padding:8px;
           font:13px/1.4 inherit;resize:vertical}
  .inset{border:1px solid var(--line);border-radius:7px;overflow:hidden;
         margin-bottom:12px;cursor:zoom-in}
  .inset img{width:100%;display:block}
  .stats{font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;color:var(--dim);
         background:#0e1116;border:1px solid var(--line);border-radius:7px;
         padding:8px;margin-bottom:12px}
  .hidden{display:none}
  .ghost{background:transparent;color:var(--dim);border:1px solid var(--line);
         border-radius:7px;padding:6px 10px;cursor:pointer;font:inherit;
         font-size:12px}
  .ghost:hover{color:var(--ink);border-color:var(--accent)}
  .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  table{width:100%;border-collapse:collapse;font-size:13px}
  td,th{border-bottom:1px solid var(--line);padding:6px 5px;text-align:left;
        vertical-align:top}
  th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;
     letter-spacing:.07em}
  .pill{display:inline-block;border-radius:20px;padding:1px 9px;font-size:11px;
        border:1px solid var(--line);color:var(--dim)}
  .pill.done{background:#14402a;border-color:#2f7d52;color:#8fe0b0}
  .pill.todo{background:#3a2030;border-color:#7d3060;color:var(--warn)}
  #big{position:fixed;inset:0;background:#000d;z-index:60;display:none;
       align-items:center;justify-content:center;cursor:zoom-out;padding:20px}
  #big img{max-width:100%;max-height:100%}
  .keyhelp{font-size:11.5px;color:var(--dim);line-height:1.7}
  .keyhelp kbd{background:#0e1116;border:1px solid var(--line);border-radius:4px;
               padding:0 5px}
  a.dl{display:inline-block;background:var(--on);color:#fff;text-decoration:none;
       padding:10px 16px;border-radius:8px;font-weight:650;border:1px solid var(--accent)}
  .note{color:var(--dim);font-size:12px;margin:10px 0}
  .warnbox{border:1px solid #7d3060;background:#2a1320;border-radius:8px;
           padding:10px 12px;margin-bottom:12px;font-size:12.5px}
</style></head><body>

<header>
  <h1>__NAME__ &middot; visual review &middot; __STAMP__</h1>
  <span class="pill" id="where"></span>
  <div class="bar"><div id="prog"></div></div>
  <span class="grow"></span>
  <button class="ghost" id="tglStats">show pitch / area (#)</button>
  <button class="ghost" id="prev">&larr; prev</button>
  <button class="ghost" id="next">next &rarr;</button>
</header>

<main>
  <div id="stage"></div>
  <aside id="panel"></aside>
</main>
<div id="big"><img></div>

<script>
const DATA = __DATA__;
const CFG  = __CFG__;
const NF = __NFACETS__, NL = __NLINES__;
const KEY = "roofreview:" + DATA.dataset + ":" + DATA.date;

// screens: 0..NF-1 facets, NF missing, NF+1 lines, NF+2 export
const S_MISSING = NF, S_LINES = NF + 1, S_EXPORT = NF + 2;
let scr = 0, showStats = false;

const blank = () => ({identity:"",boundary:"",severity:"",location:"",note:""});
let state = {
  facets: DATA.facets.map(blank),
  lines:  DATA.intersection_lines.map(() => ({verdict:"",note:""})),
  missing: [],
  missingLines: [],
  observations: (DATA.top_level_observations||[]).map(o => ({...o})),
};

// ---- autosave -------------------------------------------------------------
// Local browser storage only. The page runs from disk in Emmett's own browser,
// so nothing leaves the machine.
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(state)); }catch(e){} }
function load(){
  try{
    const s = localStorage.getItem(KEY);
    if(!s) return;
    const p = JSON.parse(s);
    // Merge rather than replace, so a re-render that changes the facet count
    // does not silently drop answers already given.
    if(p.facets) p.facets.forEach((v,i)=>{ if(state.facets[i]) state.facets[i]=v; });
    if(p.lines)  p.lines.forEach((v,i)=>{ if(state.lines[i]) state.lines[i]=v; });
    state.missing = p.missing || [];
    state.missingLines = p.missingLines || [];
    if(p.observations && p.observations.length) state.observations = p.observations;
  }catch(e){}
}
load();

// ---- helpers --------------------------------------------------------------
// Built through <template>, NOT through a <div>. THIS WAS A REAL BUG and it
// cost a review pass: the HTML parser DISCARDS <tr>, <td> and <th> when they
// are assigned to a <div>, because a table row outside table context is not
// valid content. `el("<tr>...")` therefore returned null, appendChild(null)
// threw, and render() aborted halfway, so the "add a missing facet" and "add a
// missing line" buttons silently did nothing. <template> content parses any
// fragment, including table rows.
//
// It is exactly the failure the silent-failure standing rule describes: no
// message to the user, output that looked fine, and a list that stayed empty
// because nothing could be added to it rather than because there was nothing
// to add. The guard added below is the independent check that would have
// caught it.
const el = (h) => { const t=document.createElement("template");
                    t.innerHTML=h.trim();
                    const n=t.content.firstElementChild;
                    if(!n) throw new Error("el(): produced no element for: "
                                           + h.slice(0,60));
                    return n; };
const esc = (s) => String(s==null?"":s).replace(/[&<>"]/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));

function optRow(list, cur, onPick){
  const wrap = el(`<div class="opts"></div>`);
  list.forEach(([val,key])=>{
    const b = el(`<button class="opt${cur===val?" on":""}" data-v="${val}">
                    <span>${val}</span><kbd>${esc(key)}</kbd></button>`);
    b.onclick = ()=>onPick(cur===val?"":val);   // click again to clear
    wrap.appendChild(b);
  });
  return wrap;
}

function facetDone(i){
  const a = state.facets[i];
  return a.identity && a.boundary;              // severity/location optional
}
function progress(){
  const done = state.facets.filter((_,i)=>facetDone(i)).length;
  document.getElementById("prog").style.width = (100*done/NF) + "%";
  document.getElementById("where").textContent =
    scr < NF ? `facet ${scr} of ${NF-1}  (${done} done)`
    : scr===S_MISSING ? "missing facets"
    : scr===S_LINES ? "intersection lines"
    : "export";
}

// ---- screens --------------------------------------------------------------
function render(){
  const stage = document.getElementById("stage");
  const panel = document.getElementById("panel");
  stage.innerHTML = ""; panel.innerHTML = "";
  if(scr < NF) renderFacet(stage, panel);
  else if(scr === S_MISSING) renderMissing(stage, panel);
  else if(scr === S_LINES) renderLines(stage, panel);
  else renderExport(stage, panel);
  progress(); save();
}

function insetOverview(){
  const d = el(`<div class="inset"><img src="overview.png" alt="overview"></div>`);
  d.onclick = ()=>showBig("overview.png");
  return d;
}

function renderFacet(stage, panel){
  const f = DATA.facets[scr], a = state.facets[scr];
  stage.appendChild(el(`<img class="big" src="${f.render}" alt="facet ${f.facet}">`));
  panel.appendChild(el(`<h2>facet ${f.facet} <span class="pill ${facetDone(scr)?"done":"todo"}">${facetDone(scr)?"answered":"not answered"}</span></h2>`));
  panel.appendChild(el(`<div class="sub">${f.kind} &middot; ${f.n_points.toLocaleString()} points</div>`));
  panel.appendChild(insetOverview());

  // Pitch and area, default hidden. See the note at the top of review_ui.py.
  const st = el(`<div class="stats ${showStats?"":"hidden"}" id="stats">
      pitch    ${f.pitch_deg.toFixed(2)} deg
      <br>plan     ${f.plan_ft2} ft2 (PLAN, not slope)
      <br>quality  ${f.quality}</div>`);
  panel.appendChild(st);

  const mk = (label, list, field) => {
    const fs = el(`<fieldset><legend>${label}</legend></fieldset>`);
    fs.appendChild(optRow(list, a[field], v=>{ a[field]=v; render(); }));
    return fs;
  };
  panel.appendChild(mk("identity", CFG.identity, "identity"));
  panel.appendChild(mk("boundary", CFG.boundary, "boundary"));
  panel.appendChild(mk("severity (area impact)", CFG.severity, "severity"));
  panel.appendChild(mk("location of the affected edge", CFG.location, "location"));

  const nf = el(`<fieldset><legend>note</legend>
     <textarea id="note" placeholder="What you SAW. A physical description travels to the next site; a suggested threshold does not."></textarea></fieldset>`);
  panel.appendChild(nf);
  const ta = nf.querySelector("textarea");
  ta.value = a.note || "";
  ta.oninput = ()=>{ a.note = ta.value; save(); };

  panel.appendChild(el(`<div class="keyhelp">
    <b>keys</b> &nbsp;identity <kbd>1</kbd>&ndash;<kbd>5</kbd> &nbsp;
    boundary <kbd>q w e r t y</kbd> &nbsp; severity <kbd>a s d</kbd><br>
    location <kbd>z x c v b n m , .</kbd> (N NE E SE S SW W NW multiple)<br>
    note <kbd>/</kbd> &nbsp; blur <kbd>Esc</kbd> &nbsp;
    next <kbd>&rarr;</kbd> or <kbd>space</kbd> &nbsp; prev <kbd>&larr;</kbd> &nbsp;
    stats <kbd>#</kbd><br>
    Click a selected option again to clear it.
  </div>`));
}

function renderMissing(stage, panel){
  stage.appendChild(el(`<img class="big" src="overview.png" alt="overview">`));
  panel.appendChild(el(`<h2>missing facets</h2>`));
  panel.appendChild(el(`<div class="sub">Real roof sections with NO outline at all. Described by location, since there is no id to attach them to.</div>`));
  panel.appendChild(el(`<div class="warnbox">Pink on the render is testable roof no facet claims: <b>${DATA.unassigned_footprint.segmentation_gap.ft2} ft&sup2;</b>. Blue is untestable capture gap: <b>${DATA.unassigned_footprint.capture_gap.ft2} ft&sup2;</b>. A missing facet should sit under PINK.</div>`));
  const tbl = el(`<table><thead><tr><th>where</th><th>what</th><th>approx ft2</th><th></th></tr></thead><tbody></tbody></table>`);
  const tb = tbl.querySelector("tbody");
  state.missing.forEach((m,i)=>{
    const tr = el(`<tr>
      <td><input value="${esc(m.where)}" style="width:100%"></td>
      <td><input value="${esc(m.what)}" style="width:100%"></td>
      <td><input value="${esc(m.approx_ft2)}" style="width:70px"></td>
      <td><button class="ghost">del</button></td></tr>`);
    const [w,wt,ar] = tr.querySelectorAll("input");
    w.oninput=()=>{m.where=w.value;save()};
    wt.oninput=()=>{m.what=wt.value;save()};
    ar.oninput=()=>{m.approx_ft2=ar.value;save()};
    tr.querySelector("button").onclick=()=>{state.missing.splice(i,1);render()};
    tb.appendChild(tr);
  });
  panel.appendChild(tbl);
  const add = el(`<button class="ghost" style="margin-top:10px">+ add a missing facet</button>`);
  add.onclick = ()=>{
    const before = state.missing.length;
    state.missing.push({where:"",what:"",approx_ft2:""});
    render();
    // INDEPENDENT CHECK: the row count on screen must match the array. The
    // first version failed silently here; a mismatch now says so out loud.
    const shown = document.querySelectorAll("#panel tbody tr").length;
    if(shown !== before + 1)
      alert("BUG: " + (before+1) + " missing-facet rows in state but " + shown +
            " on screen. Your entry would not have been saved. Tell Claude.");
  };
  panel.appendChild(add);
  panel.appendChild(el(`<div class="note">Inputs autosave. Click the overview to enlarge it.</div>`));
  stage.firstChild.onclick = ()=>showBig("overview.png");
  stage.firstChild.style.cursor = "zoom-in";
}

function renderLines(stage, panel){
  stage.appendChild(el(`<img class="big" src="overview.png" alt="overview">`));
  stage.firstChild.onclick = ()=>showBig("overview.png");
  stage.firstChild.style.cursor = "zoom-in";
  panel.appendChild(el(`<h2>intersection lines</h2>`));
  panel.appendChild(el(`<div class="sub">${NL} lines, labelled <b>L0</b>&ndash;<b>L${NL-1}</b> on the overview. These are INFERRED geometry and have never been validated; they are part of what you are judging.</div>`));
  DATA.intersection_lines.forEach((ln,i)=>{
    const a = state.lines[i];
    const fs = el(`<fieldset><legend>L${ln.id} &middot; ${ln.kind} &middot; facets ${ln.between[0]}&ndash;${ln.between[1]} &middot; ${ln.length_ft} ft</legend></fieldset>`);
    fs.appendChild(optRow(CFG.lineVerdict, a.verdict, v=>{ a.verdict=v; render(); }));
    const ta = el(`<textarea placeholder="note (optional)" style="min-height:44px;margin-top:7px"></textarea>`);
    ta.value = a.note||""; ta.oninput=()=>{a.note=ta.value;save()};
    fs.appendChild(ta);
    panel.appendChild(fs);
  });
  panel.appendChild(el(`<h2 style="margin-top:16px">missing lines</h2>`));
  const tbl = el(`<table><thead><tr><th>where</th><th>type</th><th></th></tr></thead><tbody></tbody></table>`);
  const tb = tbl.querySelector("tbody");
  state.missingLines.forEach((m,i)=>{
    const tr = el(`<tr><td><input value="${esc(m.where)}" style="width:100%"></td>
      <td><input value="${esc(m.type)}" style="width:90px" placeholder="ridge/hip/valley"></td>
      <td><button class="ghost">del</button></td></tr>`);
    const [w,t] = tr.querySelectorAll("input");
    w.oninput=()=>{m.where=w.value;save()}; t.oninput=()=>{m.type=t.value;save()};
    tr.querySelector("button").onclick=()=>{state.missingLines.splice(i,1);render()};
    tb.appendChild(tr);
  });
  panel.appendChild(tbl);
  const add = el(`<button class="ghost" style="margin-top:10px">+ add a missing line</button>`);
  add.onclick = ()=>{
    const before = state.missingLines.length;
    state.missingLines.push({where:"",type:""});
    render();
    const shown = document.querySelectorAll("#panel tbody tr").length;
    if(shown !== before + 1)
      alert("BUG: " + (before+1) + " missing-line rows in state but " + shown +
            " on screen. Your entry would not have been saved. Tell Claude.");
  };
  panel.appendChild(add);
}

function buildOutput(){
  const out = JSON.parse(JSON.stringify(DATA));
  out.completed_utc = new Date().toISOString();
  out.facets = DATA.facets.map((f,i)=>({...f, ...state.facets[i]}));
  out.intersection_lines = DATA.intersection_lines.map((l,i)=>({...l, ...state.lines[i]}));
  out.missing_facets = state.missing.filter(m=>m.where||m.what);
  out.missing_lines = state.missingLines.filter(m=>m.where||m.type);
  out.top_level_observations = state.observations.filter(o=>o.observation);
  const unanswered = out.facets.filter(f=>!f.identity||!f.boundary)
                               .map(f=>f.facet);
  // Recorded rather than hidden: a partial pass is still evidence, but a
  // reader has to be able to tell a blank from a considered answer.
  out.completeness = {
    facets_total: NF,
    facets_answered: NF - unanswered.length,
    facets_unanswered: unanswered,
    lines_total: NL,
    lines_answered: out.intersection_lines.filter(l=>l.verdict).length,
  };
  return out;
}

function renderExport(stage, panel){
  const out = buildOutput();
  stage.appendChild(el(`<pre style="color:#9fb3c8;font:12px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;max-width:900px;padding:14px">${esc(JSON.stringify(out,null,2))}</pre>`));
  panel.appendChild(el(`<h2>export</h2>`));
  panel.appendChild(el(`<div class="sub">Save this into <code>reviews/__NAME__/review-__STAMP__.json</code> and commit it.</div>`));
  const c = out.completeness;
  panel.appendChild(el(`<div class="stats">facets answered  ${c.facets_answered} / ${c.facets_total}
<br>lines answered   ${c.lines_answered} / ${c.lines_total}
<br>missing facets   ${out.missing_facets.length}
<br>missing lines    ${out.missing_lines.length}${c.facets_unanswered.length?`
<br><br>unanswered: ${c.facets_unanswered.join(", ")}`:""}</div>`));

  panel.appendChild(el(`<h2 style="font-size:14px;margin-top:6px">top-level observations</h2>`));
  state.observations.forEach((o,i)=>{
    const fs = el(`<fieldset><legend>observation ${i+1}</legend></fieldset>`);
    const ta = el(`<textarea style="min-height:60px"></textarea>`);
    ta.value = o.observation||""; ta.oninput=()=>{o.observation=ta.value;save()};
    fs.appendChild(ta);
    const del = el(`<button class="ghost" style="margin-top:6px">del</button>`);
    del.onclick=()=>{state.observations.splice(i,1);render()};
    fs.appendChild(del);
    panel.appendChild(fs);
  });
  const addo = el(`<button class="ghost">+ add observation</button>`);
  addo.onclick=()=>{state.observations.push({observation:"",by:"Emmett"});render()};
  panel.appendChild(addo);

  const dl = el(`<div style="margin-top:16px"><a class="dl" id="dl">download review JSON</a></div>`);
  panel.appendChild(dl);
  const a = dl.querySelector("a");
  const blob = new Blob([JSON.stringify(out,null,2)], {type:"application/json"});
  a.href = URL.createObjectURL(blob);
  a.download = "review-" + DATA.date + ".json";

  const clr = el(`<div style="margin-top:22px"><button class="ghost">clear saved progress</button></div>`);
  clr.querySelector("button").onclick = ()=>{
    if(confirm("Erase this browser's saved progress for this review?")){
      localStorage.removeItem(KEY);
      state.facets = DATA.facets.map(blank);
      state.lines = DATA.intersection_lines.map(()=>({verdict:"",note:""}));
      state.missing = []; state.missingLines = [];
      render();
    }};
  panel.appendChild(clr);
}

// ---- navigation and keys --------------------------------------------------
function go(n){ scr = Math.max(0, Math.min(S_EXPORT, n)); window.scrollTo(0,0);
                document.getElementById("stage").scrollTop = 0; render(); }
document.getElementById("next").onclick = ()=>go(scr+1);
document.getElementById("prev").onclick = ()=>go(scr-1);
document.getElementById("tglStats").onclick = ()=>{
  showStats = !showStats;
  document.getElementById("tglStats").textContent =
    (showStats?"hide":"show") + " pitch / area (#)";
  render();
};
function showBig(src){
  const b = document.getElementById("big");
  b.querySelector("img").src = src; b.style.display="flex";
}
document.getElementById("big").onclick = (e)=>{ e.currentTarget.style.display="none"; };

document.addEventListener("keydown", (e)=>{
  const t = e.target.tagName;
  if(t==="TEXTAREA" || t==="INPUT"){
    if(e.key==="Escape") e.target.blur();
    return;                                  // never steal keys while typing
  }
  if(e.key==="ArrowRight" || e.key===" "){ e.preventDefault(); go(scr+1); return; }
  if(e.key==="ArrowLeft"){ e.preventDefault(); go(scr-1); return; }
  if(e.key==="#"){ document.getElementById("tglStats").click(); return; }
  if(e.key==="/"){ e.preventDefault();
    const n=document.getElementById("note"); if(n){n.focus();} return; }
  if(scr < NF){
    const a = state.facets[scr];
    for(const [field,list] of [["identity",CFG.identity],["boundary",CFG.boundary],
                               ["severity",CFG.severity],["location",CFG.location]]){
      const hit = list.find(([v,k])=>k===e.key);
      if(hit){ a[field] = (a[field]===hit[0] ? "" : hit[0]); render(); return; }
    }
  }
});

render();
</script></body></html>
"""
