const state={rows:[],knobs:{},currentRun:null,lastRun:null,lastSolution:null};
const byId=(id)=>document.getElementById(id);
const fmt=(n)=>Number(n||0).toFixed(3);

function initClock(){setInterval(()=>byId('clock').textContent=new Date().toLocaleString(),1000)}
async function pingHealth(){try{const r=await fetch('/api/health');const j=await r.json();byId('serverHealth').textContent=`health: ${j.status} runs:${j.run_count}`}catch{}}

function drawLineChart(svgId,positions,current,pred,tol){
  const svg=byId(svgId);svg.innerHTML='';
  const W=svg.clientWidth||600,H=svg.clientHeight||180,pad=24;
  const vals=[...current,...(pred||[])]; if(!vals.length)return;
  const min=Math.min(...vals)-tol,max=Math.max(...vals)+tol;
  const x=(i)=>pad+(i/(positions.length-1||1))*(W-2*pad);
  const y=(v)=>H-pad-((v-min)/(max-min||1))*(H-2*pad);
  const band=document.createElementNS('http://www.w3.org/2000/svg','rect');
  band.setAttribute('x',pad);band.setAttribute('y',y(Math.max(...current)+tol));band.setAttribute('width',W-2*pad);band.setAttribute('height',Math.abs(y(Math.max(...current)+tol)-y(Math.min(...current)-tol)));band.setAttribute('fill','#28445f66');svg.appendChild(band);
  const mk=(arr,color)=>{const p=document.createElementNS('http://www.w3.org/2000/svg','path');let d='';arr.forEach((v,i)=>d+=(i?'L':'M')+x(i)+','+y(v));p.setAttribute('d',d);p.setAttribute('stroke',color);p.setAttribute('fill','none');p.setAttribute('stroke-width','2');svg.appendChild(p)};
  mk(current,'#4ea1ff'); if(pred) mk(pred,'#3ec46d');
}

async function loadDataset(){
  const path=byId('datasetPath').value.trim();
  const r=await fetch('/api/dataset/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
  const j=await r.json(); if(!r.ok){alert(j.error);return;}
  const s=j.summary;byId('datasetStatus').textContent=`dataset loaded: ${s.rows} rows`;byId('datasetSummary').textContent=`dates ${s.date_min}..${s.date_max} | devices ${s.devices.join(', ')} | segments ${s.segment_count}`;

  state.rows=[];
  const ctx=await fetch('/api/context'); const c=await ctx.json(); state.rows=c.rows||[];
  populateFromSummary(s);
  await loadTargets();
  await loadKnobs();
}

function populateFromSummary(s){
  const fill=(id,arr)=>{byId(id).innerHTML='';[''].concat(arr||[]).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v||'(any)';byId(id).appendChild(o);});};
  fill('day',s.dates||[]);
  const products=[...new Set(state.rows.map(r=>r.product_name||r.product).filter(Boolean))];
  fill('product',products);
  const plates=[...new Set(state.rows.map(r=>r.plate_id).filter(Boolean))];
  fill('plate',plates);
}

async function loadTargets(){const r=await fetch('/api/optimizer/targets');const j=await r.json();byId('target').innerHTML='';(j.targets||[]).forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;byId('target').appendChild(o);});}

async function loadKnobs(){
  const q=new URLSearchParams({product_name:byId('product').value,day:byId('day').value,plate:byId('plate').value});
  const r=await fetch('/api/optimizer/knobs?'+q.toString());
  const j=await r.json(); if(j.error){return;}
  state.knobs={};
  const box=byId('knobGroups'); box.innerHTML='';
  Object.entries(j.compartments||{}).forEach(([comp,groups])=>{
    const block=document.createElement('div'); block.innerHTML=`<h4>${comp}</h4>`;
    ['power','main_gases','segment_gases'].forEach(g=>{
      (groups[g]||[]).forEach(k=>{
        const item=document.createElement('div'); item.className='knob-item';
        item.innerHTML=`<label><input type='checkbox' data-k='${k}' checked /> enable</label><span>${k}</span><span>${j.current_values[k]??''}</span>`;
        block.appendChild(item); state.knobs[k]=true;
      });
    });
    box.appendChild(block);
  });
}

function selectedKnobs(){return [...document.querySelectorAll('#knobGroups input[type=checkbox]')].filter(x=>x.checked).map(x=>x.dataset.k)}

async function runOptimizer(){
  const payload={
    product_name:byId('product').value||null,
    day:byId('day').value||null,
    plate:byId('plate').value||null,
    target:byId('target').value,
    tolerance:Number(byId('tolerance').value),
    mode:byId('mode').value,
    train_new_model:byId('modelMode').value==='train',
    use_existing_model:byId('modelMode').value==='existing',
    allowed_knobs:selectedKnobs(),
    price_kwh:Number(byId('priceKwh').value),
    price_gas:Number(byId('priceGas').value)
  };
  const r=await fetch('/api/optimizer/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const j=await r.json(); if(!r.ok){alert(j.error);return;}
  state.lastRun=j; renderRun(j);
}

function renderRun(data){
  drawLineChart('chartCurrent',data.positions,data.current_profile,null,data.tolerance);
  drawLineChart('chartOptimized',data.positions,data.current_profile,data.optimized_profile,data.tolerance);

  const tbody=byId('changesTable').querySelector('tbody'); tbody.innerHTML='';
  const primary=data.top_solutions[0]; state.lastSolution=primary;
  primary.knob_changes.forEach(c=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${c.compartment}</td><td>${c.knob}</td><td>${fmt(c.current)}</td><td>${fmt(c.proposed)}</td><td>${fmt(c.delta)}</td><td>${fmt(c.pct_change)}</td>`;tbody.appendChild(tr);});

  byId('costCards').innerHTML=`<div class='card'>Plate: ${fmt(data.cost_summary.per_plate)}</div><div class='card'>Day: ${fmt(data.cost_summary.per_day)}</div><div class='card'>Month: ${fmt(data.cost_summary.per_month)}</div><div class='card'>ΔCost: ${fmt(data.cost_summary.delta_cost)}</div>`;

  const sol=byId('solutions'); sol.innerHTML='';
  data.top_solutions.forEach(s=>{const d=document.createElement('div');d.className='solution';d.innerHTML=`<b>#${s.rank}</b> target=${fmt(s.predicted_target_value)} | stability=${fmt(s.stability_score)} | cost=${fmt(s.cost_impact.per_plate)}<br>${s.summary}<br><button data-r='${s.rank}'>APPLY</button>`;d.querySelector('button').onclick=()=>{state.lastSolution=s;byId('verifyPlate').value=byId('plate').value||''};sol.appendChild(d);});
}

async function verifyRun(){
  if(!state.lastSolution){alert('Run optimizer first');return;}
  const payload={plate_id:byId('verifyPlate').value,target:byId('target').value,predicted_profile:state.lastSolution.predicted_profile};
  const r=await fetch('/api/optimizer/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const j=await r.json(); if(!r.ok){alert(j.error);return;}
  drawLineChart('chartVerify',j.positions,j.actual_profile,j.predicted_profile,0);
  byId('verifyMetrics').textContent=`MAE ${fmt(j.metrics.mae)} | RMSE ${fmt(j.metrics.rmse)} | MaxErr ${fmt(j.metrics.max_abs_error)} | ${j.explanation}`;
}

function bind(){
  byId('btnLoad').onclick=loadDataset;
  byId('btnRun').onclick=runOptimizer;
  byId('btnVerify').onclick=verifyRun;
  ['product','day','plate'].forEach(id=>byId(id).addEventListener('change',loadKnobs));
  byId('knobSearch').addEventListener('input',()=>{const q=byId('knobSearch').value.toLowerCase();document.querySelectorAll('#knobGroups .knob-item').forEach(x=>x.style.display=x.textContent.toLowerCase().includes(q)?'grid':'none');});
}

bind(); initClock(); pingHealth(); setInterval(pingHealth,5000);
