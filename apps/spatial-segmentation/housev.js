/* House V camera views and scene HUD. The Luxonis iframe supplies H.264 decoding. */
const $ = id => document.getElementById(id);
const view = $('view');
const spatialCanvas = $('spatial-map');
const spatialHeading = document.querySelector('.map-heading');
const intelPanel = document.querySelector('.intel-panel');
const keys = ['confidence', 'iou'];
const host = location.hostname;
const trainingMode = location.pathname === '/training';
document.querySelectorAll('.lab-nav a').forEach(link => {
  if ((link.getAttribute('href') === '/training') === trainingMode)
    link.setAttribute('aria-current','page');
});
if (trainingMode) {
  document.title='House V / Training Lab';
  document.querySelector('.brand small').textContent='TRAINING LAB // OAK 4 D PRO';
  $('lab-state').textContent='LIVE / NOT RECORDING';
}
const viewerUrl = new URL(`${location.protocol}//${host}:8082/viewer/`);
viewerUrl.searchParams.set('ws_url', `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${host}:8765`);

let mode = null;
let showLocks = true;
let viewerFrame = null;
let cameraStage = null;
let pipMain = 'video';
let latestScene = null;
let latestIdentities = null;
let indexMode = 'nearest';
const smoothedTracks = new Map();
let latestLidar = null;
let lastLidarStamp = null;
const lidarHistory = [];
const LIDAR_PERSIST_MS = 250;
let showLidar = true;
let zoomAvailable = false;
let monoGeneration = 0;

function setConnection(label, live) {
  $('connection-status').textContent = label;
  document.querySelector('.status-dot').classList.toggle('offline', !live);
}
function syncModel(state) {
  for (const key of keys) {
    $(key).value = state[key];
    $(`${key}-value`).value = Number(state[key]).toFixed(2);
  }
}
async function sendJson(path, data) {
  const response = await fetch(path, {
    method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
for (const key of keys) {
  $(key).addEventListener('input', () => {
    $(`${key}-value`).value = Number($(key).value).toFixed(2);
  });
  $(key).addEventListener('change', async () => {
    try { syncModel(await sendJson('/api/model', {[key]: Number($(key).value)})); }
    catch (error) { setConnection(`MODEL ERROR`, false); console.warn(error); }
  });
}
fetch('/api/model').then(r => r.json()).then(syncModel).catch(() => {});

function syncInference(state) {
  $('inference-fps').value = state.fps;
  $('inference-value').value = String(state.fps);
}
$('inference-fps').addEventListener('input', () => {
  $('inference-value').value = $('inference-fps').value;
});
$('inference-fps').addEventListener('change', async () => {
  try { syncInference(await sendJson('/api/inference',
                                     {fps:Number($('inference-fps').value)})); }
  catch(error) { setConnection('NN RATE ERROR',false);console.warn(error); }
});
fetch('/api/inference').then(r=>r.json()).then(syncInference).catch(()=>{});

function smoothScene(scene) {
  if(!scene?.objects || scene.device_timestamp_ns == null)return scene;
  const timestamp=scene.device_timestamp_ns/1e9,now=Date.now();
  const objects=scene.objects.map(obj=>{
    const observed=obj.track_state==='tracked';
    let state=smoothedTracks.get(obj.track_id);
    if(!state || timestamp<state.timestamp || now-state.seenMs>1500) {
      state={bbox:[...obj.bbox_xyxy_norm],xyz:obj.xyz_mm?.slice()||null,
             range:obj.range_m,timestamp,frame:scene.frame_id,seenMs:now};
      smoothedTracks.set(obj.track_id,state);
    } else if(observed && state.frame!==scene.frame_id) {
      const dt=Math.max(0,Math.min(.5,timestamp-state.timestamp));
      const alpha=Math.max(.08,Math.min(.85,1-Math.exp(-dt/.16)));
      state.bbox=state.bbox.map((value,i)=>
        value+alpha*(obj.bbox_xyxy_norm[i]-value));
      if(obj.range_m!=null)
        state.range=state.range==null?obj.range_m:
          state.range+alpha*(obj.range_m-state.range);
      if(obj.xyz_mm)
        state.xyz=state.xyz?state.xyz.map((value,i)=>
          value+alpha*(obj.xyz_mm[i]-value)):obj.xyz_mm.slice();
      state.timestamp=timestamp;state.frame=scene.frame_id;state.seenMs=now;
    }
    return {...obj,bbox_xyxy_norm:state.bbox,
            range_m:obj.range_m==null?null:state.range,
            xyz_mm:obj.xyz_mm==null?null:state.xyz};
  });
  for(const [id,state] of smoothedTracks)
    if(now-state.seenMs>1500)smoothedTracks.delete(id);
  return {...scene,objects};
}

function syncIR(state) {
  $('ir-toggle').setAttribute('aria-pressed', String(state.enabled));
  $('ir-toggle').textContent = state.enabled ? 'IR ON' : 'IR OFF';
  $('ir-intensity').value = state.intensity;
  $('ir-value').value = Number(state.intensity).toFixed(2);
}
$('ir-toggle').addEventListener('click', async () => {
  try { syncIR(await sendJson('/api/ir', {
    enabled: $('ir-toggle').getAttribute('aria-pressed') !== 'true'
  })); }
  catch (error) { setConnection('IR ERROR', false); console.warn(error); }
});
$('ir-intensity').addEventListener('input', () => {
  $('ir-value').value = Number($('ir-intensity').value).toFixed(2);
});
$('ir-intensity').addEventListener('change', async () => {
  try { syncIR(await sendJson('/api/ir', {intensity: Number($('ir-intensity').value)})); }
  catch (error) { setConnection('IR ERROR', false); console.warn(error); }
});
fetch('/api/ir').then(r => r.json()).then(syncIR).catch(() => {});

function syncZoom(state) {
  $('zoom-x').value = state.center_x;
  $('zoom-y').value = state.center_y;
}
async function updateZoom(data) {
  if (!zoomAvailable) return;
  try { syncZoom(await sendJson('/api/zoom', data)); }
  catch (error) { setConnection('ZOOM ERROR', false); console.warn(error); }
}
for (const [id, key] of [['zoom-x', 'center_x'], ['zoom-y', 'center_y']]) {
  $(id).addEventListener('change', event => updateZoom({[key]: Number(event.target.value)}));
}
fetch('/api/zoom').then(response => {
  if (!response.ok) throw new Error('No zoom pipeline');
  return response.json();
}).then(state => {
  zoomAvailable = true;
  syncZoom(state);
  $('zoom-controls').hidden = false;
}).catch(() => {});

function cleanupViewer() {
  viewerFrame?._houseObserver?.disconnect();
  viewerFrame = null;
}
function installViewerHud(frame) {
  try {
    const doc = frame.contentDocument;
    if (!doc?.body) return;
    const apply = () => {
      const source = doc.querySelector('canvas:not(.housev-overlay)');
      if (!source) return;
      const wrapper = source.parentElement;
      const section = wrapper.parentElement;
      const originalLogo = doc.querySelector('img[alt="Luxonis"]');
      const vendorHeader = originalLogo?.parentElement;
      if (vendorHeader) vendorHeader.style.display = 'none';
      if (section?.firstElementChild && section.firstElementChild !== wrapper)
        section.firstElementChild.style.display = 'none';
      if (section) { section.style.border = '0'; section.style.borderRadius = '0'; }
      doc.body.style.background = '#060b15';
      doc.querySelectorAll('canvas.pointer-events-none').forEach(canvas => {
        canvas.style.visibility = 'hidden'; // Replace the stock annotation layer.
      });
      let overlay = wrapper.querySelector('canvas.housev-overlay');
      if (!overlay) {
        overlay = doc.createElement('canvas');
        overlay.className = 'housev-overlay';
        overlay.width = 1920; overlay.height = 1056;
        overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:30;';
        wrapper.append(overlay);
      }
      frame._hudCanvas = overlay;
      renderActive();
    };
    apply();
    frame._houseObserver = new MutationObserver(apply);
    frame._houseObserver.observe(doc.body, {childList: true, subtree: true});
  } catch (error) { console.warn('Viewer HUD unavailable', error); }
}

function refreshButtons() {
  document.querySelectorAll('.modebar button[data-mode]').forEach(button =>
    button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
  $('overlay-toggle').disabled = mode === 'detections';
  const on = mode === 'detections' || showLocks;
  $('overlay-toggle').setAttribute('aria-pressed', String(on));
  $('overlay-toggle').textContent = on ? 'LOCKS ON' : 'LOCKS OFF';
  $('pip-toggle').disabled = mode === 'detections';
  $('pip-toggle').setAttribute('aria-pressed', String(pipMain === 'spatial'));
  $('pip-toggle').textContent = pipMain === 'video' ? 'SPATIAL MAIN' :
    mode === 'color' ? 'VIDEO MAIN' : 'MONO MAIN';
}
function swapPip() {
  if(mode === 'detections' || !cameraStage)return;
  pipMain = pipMain === 'video' ? 'spatial' : 'video';
  cameraStage.dataset.main = pipMain;
  refreshButtons();
  renderActive();
}
function setMode(next) {
  if (mode === next) return;
  if (spatialCanvas.parentElement !== intelPanel) spatialHeading.after(spatialCanvas);
  intelPanel.classList.remove('color-mode');
  cleanupViewer();
  monoGeneration++;
  mode = next;
  view.replaceChildren(); // Removing the iframe closes its H.264 WebSocket.
  refreshButtons();
  if (next === 'color') {
    $('mode-note').textContent = 'CAM A + L2 SPATIAL / SWITCHABLE PIP';
    const stage = document.createElement('div'); stage.className = 'color-stage';
    stage.dataset.main = pipMain;
    const videoPane = document.createElement('div'); videoPane.className = 'video-pane';
    const frame = document.createElement('iframe');
    frame.title = 'Color camera stream'; frame.allow = 'fullscreen';
    frame.onload = () => installViewerHud(frame);
    frame.src = viewerUrl.href;
    videoPane.append(frame);
    const spatialPane = document.createElement('div'); spatialPane.className = 'spatial-pane';
    spatialPane.append(spatialCanvas);
    const caption = document.createElement('span');caption.className = 'spatial-caption';
    caption.textContent = 'L2 FIELD // UNCALIBRATED';
    spatialPane.append(caption);
    stage.append(videoPane,spatialPane);view.append(stage);
    intelPanel.classList.add('color-mode');
    cameraStage = stage;viewerFrame = frame;
  } else if (next === 'left' || next === 'right') {
    $('mode-note').textContent = `CAM ${next === 'left' ? 'B' : 'C'} / MONO + L2 SPATIAL PIP`;
    const stage = document.createElement('div'); stage.className = 'color-stage';
    stage.dataset.main = pipMain;
    const monoPane = document.createElement('div'); monoPane.className = 'mono-pane';
    monoPane.dataset.label = `${next.toUpperCase()} MONO / PIP`;
    const image = document.createElement('img'); image.alt = `${next} monochrome camera`;
    const overlay = document.createElement('canvas');
    overlay.width = 640; overlay.height = 400;
    monoPane.append(image, overlay);
    const spatialPane = document.createElement('div'); spatialPane.className = 'spatial-pane';
    spatialPane.append(spatialCanvas);
    const caption = document.createElement('span');caption.className = 'spatial-caption';
    caption.textContent = 'L2 FIELD // UNCALIBRATED';spatialPane.append(caption);
    stage.append(monoPane,spatialPane);view.append(stage);
    intelPanel.classList.add('color-mode');cameraStage=stage;
    loadMono(next, image, monoGeneration);
  } else {
    cameraStage = null;
    $('mode-note').textContent = 'RGB FIELD / METADATA ONLY · VIDEO CLIENT DISCONNECTED';
    const stage = document.createElement('div'); stage.className = 'detections-stage';
    const canvas = document.createElement('canvas');
    canvas.width = 1920; canvas.height = 1056;
    canvas.setAttribute('aria-label', 'Detection-only target view');
    canvas.addEventListener('click', event => {
      if (!zoomAvailable) return;
      const rect = canvas.getBoundingClientRect();
      updateZoom({center_x: (event.clientX - rect.left) / rect.width,
                  center_y: (event.clientY - rect.top) / rect.height});
    });
    stage.append(canvas); view.append(stage);
  }
  renderActive();
}
document.querySelectorAll('.modebar button[data-mode]').forEach(button =>
  button.addEventListener('click', () => setMode(button.dataset.mode)));
$('pip-toggle').addEventListener('click',swapPip);
$('overlay-toggle').addEventListener('click', () => {
  if (mode === 'detections') return;
  showLocks = !showLocks;
  refreshButtons();
  renderActive();
});
$('lidar-toggle').addEventListener('click', () => {
  showLidar = !showLidar;
  if(!showLidar)lidarHistory.length=0;
  $('lidar-toggle').setAttribute('aria-pressed', String(showLidar));
  $('lidar-toggle').textContent = showLidar ? 'L2 POINTS ON' : 'L2 POINTS OFF';
  renderActive();
});

// Initial display only: assume L2 +X forward, +Y left, +Z up, and an
// approximately 90-degree camera horizontal FOV. No mount calibration yet.
function drawLidar(canvas) {
  if (!showLidar || !canvas) return;
  const ctx=canvas.getContext('2d'),W=canvas.width,H=canvas.height;
  const focal=W/2;
  const now=Date.now();
  for (const scan of visibleLidarScans(now)) {
    const alpha=.16+.55*(1-(now-scan.at)/LIDAR_PERSIST_MS);
    ctx.fillStyle=`rgba(71,232,243,${alpha.toFixed(3)})`;
    for (const [forward,left,up] of scan.points) {
      if(forward<.35 || forward>20)continue;
      const x=W/2-left/forward*focal,y=H/2-up/forward*focal;
      if(x<2||x>W-2||y<2||y>H-2)continue;
      ctx.fillRect(x-1.5,y-1.5,3,3);
    }
  }
}

function verticalFacePoints(points) {
  // A floor or ceiling contributes one thin height band in a ground-plane
  // cell. Keep cells with returns at three or more distinct heights.
  const columns=new Map();
  for(const point of points) {
    const [forward,left,up]=point;
    if(forward<.4||forward>20)continue;
    const key=`${Math.floor(forward/.35)},${Math.floor(left/.35)}`;
    let column=columns.get(key);
    if(!column) {column={heights:new Set(),points:[]};columns.set(key,column);}
    column.heights.add(Math.floor(up/.25));
    column.points.push(point);
  }
  const faces=[];
  for(const column of columns.values())
    if(column.heights.size>=3)faces.push(...column.points);
  return faces;
}

function visibleLidarScans(now) {
  while(lidarHistory.length && now-lidarHistory[0].at>=LIDAR_PERSIST_MS)
    lidarHistory.shift();
  return lidarHistory;
}

async function pollLidar() {
  try {
    const response=await fetch('/api/lidar',{cache:'no-store'});
    if(!response.ok)throw new Error(`L2 HTTP ${response.status}`);
    const scan=await response.json();
    if(scan.stamp_ns!==lastLidarStamp) {
      scan.local_received_ms=Date.now();
      if(showLidar)lidarHistory.push({at:scan.local_received_ms,
                                    points:scan.points,
                                    faces:verticalFacePoints(scan.points)});
      lastLidarStamp=scan.stamp_ns;
      latestLidar=scan;
    }
  } catch(error) { latestLidar=null; }
  const live=latestLidar && Date.now()-latestLidar.local_received_ms<1500;
  $('lidar-status').textContent=live ?
    `L2 ${latestLidar.source_points} PTS · UNCALIBRATED` : 'L2 OFFLINE · UNCALIBRATED';
  $('lidar-status').classList.toggle('offline',!live);
  renderActive();
  setTimeout(pollLidar,100);
}

function loadMono(source, image, generation) {
  if (mode !== source || generation !== monoGeneration || !image.isConnected) return;
  image.onload = () => setTimeout(() => loadMono(source, image, generation), 65);
  image.onerror = () => setTimeout(() => loadMono(source, image, generation), 350);
  image.src = `/api/mono/${source}.jpg?t=${Date.now()}`;
}

function rangeColor(rangeM) {
  if(!Number.isFinite(rangeM))return '#9aa9b4';
  // Red within 1.25 m, then sweep through warning colors to cyan at 8 m.
  const t=Math.max(0,Math.min(1,(rangeM-1.25)/6.75));
  return `hsl(${Math.round(t*190)} 95% 60%)`;
}

function drawTargetReticle(ctx, x, y, radius, color, held=false) {
  ctx.save();ctx.translate(x,y);ctx.strokeStyle=color;ctx.lineCap='round';
  ctx.globalAlpha=held ? .35 : .3;ctx.lineWidth=1.5;
  ctx.beginPath();ctx.arc(0,0,radius,0,Math.PI*2);ctx.stroke();
  ctx.globalAlpha=held ? .55 : .96;ctx.lineWidth=Math.max(2.5,radius*.16);
  ctx.shadowColor=color;ctx.shadowBlur=held ? 3 : 9;
  for(const [start,end] of [[-1.42,-.46],[1.72,2.67]]) {
    ctx.beginPath();ctx.arc(0,0,radius,start,end);ctx.stroke();
  }
  ctx.shadowBlur=0;ctx.globalAlpha=held ? .45 : .7;ctx.lineWidth=1.4;
  ctx.beginPath();ctx.arc(0,0,radius*.4,0,Math.PI*2);ctx.stroke();
  ctx.beginPath();ctx.moveTo(-radius*.3,-radius*.3);
  ctx.lineTo(radius*.3,radius*.3);ctx.stroke();
  ctx.restore();
}
function drawHud(canvas, scene, darkBackground) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (darkBackground) {
    ctx.fillStyle = '#07111d'; ctx.fillRect(0,0,W,H);
    ctx.strokeStyle = 'rgba(102,216,231,.10)'; ctx.lineWidth = 1;
    for(let x=0;x<=W;x+=W/8) {ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(let y=0;y<=H;y+=H/6) {ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
  }
  if (scene?.age_ms == null || scene.age_ms > 1200) {
    ctx.font = '18px ui-monospace,monospace';ctx.fillStyle = '#91b6c7';
    ctx.fillText('AWAITING CAMERA METADATA', 34, 58);return;
  }
  if (scene.zoom_region_xyxy_norm) {
    const [x0,y0,x1,y1]=scene.zoom_region_xyxy_norm;
    ctx.strokeStyle='#f6ce69';ctx.lineWidth=2;ctx.setLineDash([12,10]);
    ctx.strokeRect(x0*W,y0*H,(x1-x0)*W,(y1-y0)*H);ctx.setLineDash([]);
    ctx.font='15px ui-monospace,monospace';ctx.fillStyle='#f6ce69';
    ctx.fillText('ZOOM WINDOW',x0*W+8,Math.max(22,y0*H-8));
  }
  const objects=[...(scene.objects || [])].sort((a,b)=>b.detector_score-a.detector_score);
  const labels=[];
  for (let index=0; index<objects.length; index++) {
    const obj=objects[index];
    const [x0,y0,x1,y1]=obj.bbox_xyxy_norm;
    const cx=(x0+x1)*W/2,cy=(y0+y1)*H/2;
    const color=rangeColor(obj.range_m);
    drawTargetReticle(ctx,cx,cy,30,color,obj.track_state==='held');
    for (const outline of obj.mask_outlines || []) {
      if (outline.length<3) continue;
      ctx.beginPath();outline.forEach(([px,py],i)=>i?
        ctx.lineTo(px*W,py*H):ctx.moveTo(px*W,py*H));
      ctx.closePath();ctx.strokeStyle=color;ctx.globalAlpha=.32;
      ctx.lineWidth=1.1;ctx.stroke();ctx.globalAlpha=1;
    }
    if (index>=6) continue; // Remaining targets stay visible in the index panel.
    const title=`T${String(obj.track_id).padStart(3,'0')} ${obj.label.toUpperCase()}`;
    const range=obj.range_m==null?'--':`${obj.range_m.toFixed(2)}M`;
    ctx.font='700 19px ui-monospace,monospace';
    const labelW=Math.min(350,Math.max(170,ctx.measureText(title).width+95));
    const tx=Math.min(Math.max(8,cx+42),W-labelW-8),ty=Math.max(24,Math.min(H-20,cy));
    const rect=[tx,ty-19,tx+labelW,ty+12];
    if (labels.some(other=>Math.min(rect[2],other[2])-Math.max(rect[0],other[0])>0 &&
        Math.min(rect[3],other[3])-Math.max(rect[1],other[1])>0)) continue;
    labels.push(rect);
    ctx.fillStyle='rgba(5,15,26,.86)';ctx.fillRect(tx,ty-19,labelW,30);
    ctx.fillStyle=color;ctx.fillRect(tx,ty-19,3,30);
    ctx.fillStyle='#e7f2f7';ctx.fillText(title,tx+10,ty+2);
    ctx.font='700 16px ui-monospace,monospace';ctx.fillStyle=color;
    ctx.fillText(range,tx+labelW-ctx.measureText(range).width-8,ty+2);
  }
}

function drawMonoMarkers(canvas, scene, source) {
  if (!canvas) return;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,640,400);
  if (!showLocks||scene?.age_ms==null||scene.age_ms>1200) return;
  const occupied=[];
  for (const obj of [...scene.objects].sort((a,b)=>b.detector_score-a.detector_score)) {
    const marker=obj.mono_markers?.[source];if(!marker) continue;
    const x=marker[0]*640,y=marker[1]*400;
    const color=rangeColor(obj.range_m);
    drawTargetReticle(ctx,x,y,10,color,obj.track_state==='held');
    if(trainingMode && obj.mono_evidence?.[source]) {
      const evidence=obj.mono_evidence[source];
      const [x0,y0,x1,y1]=evidence.bbox_xyxy_norm;
      ctx.strokeStyle=evidence.agrees?'#76e4a6':'#ff8c72';
      ctx.lineWidth=1.5;ctx.setLineDash([5,3]);
      ctx.strokeRect(x0*640,y0*400,(x1-x0)*640,(y1-y0)*400);
      ctx.setLineDash([]);
    }
    const range=obj.range_m==null?'--':`${obj.range_m.toFixed(1)}m`;
    const label=`T${obj.track_id} ${obj.label} ${range}`;
    ctx.font='9px ui-monospace,monospace';const tw=ctx.measureText(label).width;
    const options=[[x+9,y-9],[x-tw-9,y-9],[x+9,y+16],[x-tw-9,y+16]];
    let best=null,cost=Infinity;
    for(const [ox,oy] of options) {
      const tx=Math.min(Math.max(3,ox),640-tw-5),ty=Math.min(Math.max(12,oy),395);
      const rect=[tx-2,ty-10,tx+tw+2,ty+3];
      const overlap=occupied.reduce((sum,r)=>sum+
        Math.max(0,Math.min(rect[2],r[2])-Math.max(rect[0],r[0]))*
        Math.max(0,Math.min(rect[3],r[3])-Math.max(rect[1],r[1])),0);
      if(overlap<cost){cost=overlap;best=[tx,ty,rect];}
    }
    const [tx,ty,rect]=best;occupied.push(rect);
    ctx.fillStyle='rgba(5,15,26,.85)';ctx.fillRect(tx-2,ty-10,tw+4,13);
    ctx.fillStyle=color;ctx.fillText(label,tx,ty);
  }
}

function drawSpatialMap(scene) {
  const canvas=$('spatial-map'),ctx=canvas.getContext('2d');
  const displayW=Math.max(280,Math.round(canvas.clientWidth||canvas.width));
  const displayH=Math.max(160,Math.round(canvas.clientHeight||canvas.height));
  if(canvas.width!==displayW||canvas.height!==displayH) {
    canvas.width=displayW;canvas.height=displayH;
  }
  const W=canvas.width,H=canvas.height,cx=W/2,originY=H-20;
  const pxPerM=Math.max(8,Math.min((H-38)/9,(W-32)/16));
  ctx.fillStyle='#071522';ctx.fillRect(0,0,W,H);
  ctx.strokeStyle='rgba(102,216,231,.17)';ctx.lineWidth=1;
  for(let meters=2;meters<=8;meters+=2){
    ctx.beginPath();ctx.arc(cx,originY,meters*pxPerM,Math.PI,2*Math.PI);ctx.stroke();
  }
  ctx.beginPath();ctx.moveTo(cx,0);ctx.lineTo(cx,H);ctx.stroke();
  ctx.fillStyle='#66d8e7';ctx.beginPath();ctx.arc(cx,originY,4,0,Math.PI*2);ctx.fill();
  if(showLidar) {
    const now=Date.now();
    for(const scan of visibleLidarScans(now)) {
      const alpha=.2+.6*(1-(now-scan.at)/LIDAR_PERSIST_MS);
      ctx.globalAlpha=alpha;
      for(const [forward,left] of scan.faces) {
        const px=cx-left*pxPerM,py=originY-forward*pxPerM;
        if(px>=2&&px<W-2&&py>=2&&py<H-2) {
          ctx.fillStyle=rangeColor(Math.hypot(forward,left));
          const size=H>300?3:2;ctx.fillRect(px,py,size,size);
        }
      }
      ctx.globalAlpha=1;
    }
  }
  if(scene?.age_ms==null||scene.age_ms>1200)return;
  for(const obj of scene.objects||[]) {
    if(!obj.xyz_mm)continue;
    const [x,,z]=obj.xyz_mm;
    const px=cx+x/1000*pxPerM,py=originY-z/1000*pxPerM;
    if(px<5||px>W-5||py<5||py>H-10)continue;
    ctx.fillStyle=rangeColor(obj.range_m);ctx.beginPath();
    ctx.arc(px,py,H>300?5:3,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#9fd4df';ctx.font=`${Math.max(9,Math.round(H/35))}px ui-monospace,monospace`;
    ctx.fillText(String(obj.track_id),px+5,py-3);
  }
}

function updateTargetIndex(scene) {
  const list=$('target-list');list.replaceChildren();
  const live=scene?.age_ms!=null&&scene.age_ms<=1200;
  const identitiesLive=latestIdentities?.age_s!=null&&
    latestIdentities.age_s<2&&Date.now()-latestIdentities.local_received_ms<2000;
  const objects=live?[...scene.objects].sort((a,b)=>{
    const state=(a.track_state==='tracked'?0:1)-(b.track_state==='tracked'?0:1);
    if(state)return state;
    const distanceA=Number.isFinite(a.range_m)?a.range_m:Infinity;
    const distanceB=Number.isFinite(b.range_m)?b.range_m:Infinity;
    return distanceA-distanceB || b.detector_score-a.detector_score;
  }):[];
  $('index-title').textContent=indexMode==='nearest'?
    (trainingMode?'RGB + MONO EVIDENCE':'TARGET INDEX'):'LONGEST IDS / ORIN';
  $('index-mode').textContent=indexMode==='nearest'?'LONGEST IDS':'NEAREST';
  $('target-count').value=String(indexMode==='nearest'?objects.length:
    identitiesLive?latestIdentities.longest_recent.length:0).padStart(2,'0');
  $('range-count').textContent=`RANGE ${objects.filter(o=>o.range_m!=null).length}/${objects.length}`;
  $('scene-age').textContent=live?`AGE ${scene.age_ms}MS`:'AGE --';
  if(indexMode==='longest') {
    if(!identitiesLive) {
      const p=document.createElement('p');p.className='empty';
      p.textContent='Waiting for Orin identity data…';list.append(p);return;
    }
    const table=document.createElement('div');table.className='identity-table';
    const columns=document.createElement('div');columns.className='identity-columns';
    for(const heading of ['GLOBAL ID','RGB YOLO',trainingMode?'MONO L / R':'MODEL 2']) {
      const cell=document.createElement('span');cell.textContent=heading;columns.append(cell);
    }
    table.append(columns);
    for(const identity of latestIdentities.longest_recent) {
      const row=document.createElement('div');row.className='identity-row';
      const id=document.createElement('div');id.className='global-id';
      id.textContent=`G${String(identity.global_id).padStart(3,'0')}`;
      const duration=document.createElement('small');
      duration.textContent=`${identity.observed_seconds.toFixed(1)}S SEEN`;
      id.append(document.createElement('br'),duration);
      const yolo=document.createElement('div');
      const label=document.createElement('strong');
      label.textContent=identity.label.toUpperCase();yolo.append(label);
      const detail=document.createElement('small');
      detail.textContent=identity.alternate_label?
        `NN ${Math.round((identity.detector_score??0)*100)}% · ALT ${identity.alternate_label.toUpperCase()}`:
        `NN ${identity.detector_score==null?'--':Math.round(identity.detector_score*100)+'%'}`;
      yolo.append(detail);
      const second=document.createElement('div');second.className='model-pending';
      if(trainingMode) second.append(evidenceStrip(identity));
      else second.textContent='AWAITING MODEL';
      row.append(id,yolo,second);table.append(row);
    }
    list.append(table);return;
  }
  if(!objects.length){const p=document.createElement('p');p.className='empty';
    p.textContent=live?'No targets in this pass':'Waiting for scene metadata…';list.append(p);return;}
  for(const obj of objects.slice(0,12)) {
    const card=document.createElement('div');card.className='target-card';
    const color=rangeColor(obj.range_m);card.style.borderLeftColor=color;
    const id=document.createElement('span');id.className='id';
    id.style.color=color;
    const globalId=identitiesLive?
      latestIdentities.source_to_global[String(obj.track_id)]:null;
    id.textContent=(globalId?`G${String(globalId).padStart(3,'0')} / `:'')+
      `T${String(obj.track_id).padStart(3,'0')} / ${obj.track_state.toUpperCase()}`;
    const range=document.createElement('span');range.className='range';
    range.style.color=color;
    range.textContent=obj.range_m==null?'R --':`${obj.range_m.toFixed(2)} M`;
    const label=document.createElement('span');label.className='label';label.textContent=obj.label;
    const meta=document.createElement('span');meta.className='meta';
    meta.textContent=`NN ${Math.round(obj.detector_score*100)}% · DEPTH ${Math.round(obj.depth_valid_fraction*100)}%`;
    card.append(id,range,label,meta);
    const alternate=document.createElement('span');alternate.className='alternate';
    alternate.textContent=obj.alternate_label?
      `ALT ${obj.alternate_label.toUpperCase()} · ${Math.round(obj.alternate_evidence_share*100)}% TEMPORAL EVIDENCE`:
      'ALT -- · NO COMPETING CLASS YET';
    card.append(alternate);list.append(card);
    if(trainingMode) card.append(evidenceStrip(obj));
  }
}
function evidenceStrip(obj) {
  const strip=document.createElement('div');strip.className='evidence-strip';
  const rgb=document.createElement('span');rgb.className='agree';
  rgb.textContent=`+ RGB ${obj.label?.toUpperCase()||'--'} ${obj.detector_score==null?'--':Math.round(obj.detector_score*100)+'%'}`;
  strip.append(rgb);
  for(const [name,title] of [['left','L'],['right','R']]) {
    const evidence=obj.mono_evidence?.[name];
    const cell=document.createElement('span');
    cell.className=evidence?(evidence.agrees?'agree':'disagree'):'unknown';
    cell.textContent=evidence?
      `${evidence.agrees?'+':'−'} ${title} ${evidence.label.toUpperCase()} ${Math.round(evidence.score*100)}%`:
      `? ${title} NO MATCH`;
    strip.append(cell);
  }
  return strip;
}
$('index-mode').addEventListener('click',()=>{
  indexMode=indexMode==='nearest'?'longest':'nearest';
  updateTargetIndex(latestScene);
});
async function pollIdentities() {
  try {
    const response=await fetch('/api/identities',{cache:'no-store'});
    if(!response.ok)throw new Error(`Identity HTTP ${response.status}`);
    latestIdentities=await response.json();
    latestIdentities.local_received_ms=Date.now();
  } catch(error) {latestIdentities=null;}
  updateTargetIndex(latestScene);
  setTimeout(pollIdentities,250);
}

function renderActive() {
  const live=latestScene?.age_ms!=null&&latestScene.age_ms<=1200;
  if(mode==='color') {
    const canvas=viewerFrame?._hudCanvas;
    if(canvas) {
      canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
      if(pipMain==='video') {
        if(showLocks)drawHud(canvas,latestScene,false);
        drawLidar(canvas);
      }
    }
  } else if(mode==='left'||mode==='right') {
    const canvas=view.querySelector('.mono-pane canvas');
    if(pipMain==='video')drawMonoMarkers(canvas,latestScene,mode);
    else canvas?.getContext('2d').clearRect(0,0,640,400);
  } else if(mode==='detections') {
    drawHud(view.querySelector('canvas'),latestScene,true);
    drawLidar(view.querySelector('canvas'));
  }
  updateTargetIndex(latestScene);
  drawSpatialMap(latestScene);
  setConnection(live?'CAMERA LIVE':'NO SCENE DATA',live);
  $('frame-status').textContent=live?
    `FRAME ${latestScene.frame_id} · NN ${latestScene.result_fps?.toFixed(1)??'--'}/S`:
    'FRAME --';
}
async function pollTelemetry() {
  try {
    const response=await fetch('/api/scene',{cache:'no-store'});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    latestScene=smoothScene(await response.json());
  } catch(error) {latestScene=null;console.warn('Scene metadata unavailable',error);}
  renderActive();setTimeout(pollTelemetry,100);
}
setMode('color');
pollTelemetry();
pollLidar();
pollIdentities();
