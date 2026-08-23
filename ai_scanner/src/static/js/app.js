const state={capturedBlob:null,capturedBlobs:[],selectedEffect:'none',stream:null,filter:'all',selectedDocs:[],galleryDocs:[],currentResult:null,currentView:'dashboard',navHistory:[],batchJobId:null,batchItems:[]};
var scanActive=false;

/* ---- IN-APP CONFIRM / PROMPT ---- */
function showConfirm(msg,onConfirm){
  var d=document.getElementById('dialog');
  document.getElementById('dialog-title').textContent='CONFIRM';
  document.getElementById('dialog-msg').textContent=msg;
  document.getElementById('dialog-input-wrap').style.display='none';
  document.getElementById('dialog-ok').style.display='';
  document.getElementById('dialog-ok').innerHTML='<i class="lucide icon-check"></i> CONFIRM';
  d.classList.add('show');
  document.getElementById('dialog-ok').onclick=function(){d.classList.remove('show');if(onConfirm)onConfirm()};
  document.getElementById('dialog-cancel').onclick=function(){d.classList.remove('show')};
}
function showChoice(msg,okLabel,cancelLabel,onOk,onCancel){
  var d=document.getElementById('dialog');
  document.getElementById('dialog-title').textContent='CHOICE';
  document.getElementById('dialog-msg').textContent=msg;
  document.getElementById('dialog-input-wrap').style.display='none';
  document.getElementById('dialog-ok').style.display='';
  document.getElementById('dialog-ok').innerHTML='<i class="lucide icon-check"></i> '+(okLabel||'OK');
  document.getElementById('dialog-cancel').innerHTML='<i class="lucide icon-x"></i> '+(cancelLabel||'CANCEL');
  d.classList.add('show');
  document.getElementById('dialog-ok').onclick=function(){d.classList.remove('show');if(onOk)onOk()};
  document.getElementById('dialog-cancel').onclick=function(){d.classList.remove('show');if(onCancel)onCancel()};
}
function showPrompt(msg,onConfirm,defaultVal){
  var d=document.getElementById('dialog');
  document.getElementById('dialog-title').textContent='INPUT';
  document.getElementById('dialog-msg').textContent=msg;
  document.getElementById('dialog-input-wrap').style.display='';
  var inp=document.getElementById('dialog-input');
  inp.value=defaultVal||'';
  document.getElementById('dialog-ok').style.display='';
  document.getElementById('dialog-ok').innerHTML='<i class="lucide icon-check"></i> OK';
  d.classList.add('show');
  inp.focus();inp.select();
  document.getElementById('dialog-ok').onclick=function(){var v=inp.value.trim();d.classList.remove('show');if(onConfirm)onConfirm(v)};
  document.getElementById('dialog-cancel').onclick=function(){d.classList.remove('show');if(onConfirm)onConfirm('')};
  inp.onkeydown=function(e){if(e.key==='Enter')document.getElementById('dialog-ok').click()};
}

/* ---- LOCAL STORAGE PERSISTENCE ---- */
function saveState(){
  try{localStorage.setItem('scanner_view',state.currentView)}catch(e){}
}
function restoreState(){
  try{
    var v=localStorage.getItem('scanner_view');
    if(v&&['dashboard','scanner','gallery','ai','settings'].includes(v))switchView(v);
  }catch(e){}
}

/* ---- NAVIGATION HISTORY ---- */
function goBack(){
  if(state.navHistory.length>1){
    state.navHistory.pop();
    switchView(state.navHistory.pop()||'dashboard');
  }else{switchView('dashboard')}
}
function updateBackBtn(){
  var b=document.getElementById('btn-back');
  b.classList.toggle('show',state.navHistory.length>1);
}

function toast(m,t){
  var c=document.getElementById('toast-c');
  var e=document.createElement('div');
  e.className='toast'+(t==='err'?' err':t==='warn'?' warn':'');
  e.innerHTML='<span class="toast-ic"><i class="lucide '+(t==='err'?'lucide-circle-x':t==='warn'?'lucide-triangle-alert':'lucide-circle-check')+'"></i></span> '+m;
  c.appendChild(e);
  setTimeout(function(){e.style.opacity='0';setTimeout(function(){e.remove()},300)},3500);
}

/* ---- NAVIGATION ---- */
var navTimer;
function switchView(v){
  if(state.currentView===v)return;
  if(state.navHistory[state.navHistory.length-1]!==state.currentView)
    state.navHistory.push(state.currentView);
  state.currentView=v;
  saveState();
  updateBackBtn();
  document.querySelectorAll('.nav-item').forEach(function(b){b.classList.toggle('active',b.dataset.view===v)});
  document.querySelectorAll('.hud-tab').forEach(function(b){b.classList.toggle('active',b.dataset.tab===v)});
  document.querySelectorAll('.view').forEach(function(x){x.classList.toggle('active',x.id==='view-'+v)});
  var t={dashboard:'DASHBOARD',scanner:'SCANNER',gallery:'VAULT',ai:'AI ASSISTANT',settings:'CONFIG'};
  var tag=document.querySelector('.brand-tag');
  if(tag)tag.innerHTML='<strong>AI SCANNER</strong> // '+(t[v]||'NEXUS-OS');
  closeSidebar();
  clearTimeout(navTimer);
  navTimer=setTimeout(function(){
    if(v==='gallery')loadGallery();
    if(v==='dashboard'){loadDashboard();loadActivity()}
    if(v==='settings')loadSettings();
    if(v==='ai')ensureAiView();
  },50);
}

/* ---- CLOCK ---- */
function updateClock(){
  var d=new Date();
  document.getElementById('hud-clock').textContent=
    String(d.getHours()).padStart(2,'0')+':'+
    String(d.getMinutes()).padStart(2,'0')+':'+
    String(d.getSeconds()).padStart(2,'0');
}
setInterval(updateClock,1000);updateClock();

/* ---- LOADER ---- */
function showLoader(text,sub){
  document.getElementById('loader-text').textContent=text||'PROCESSING...';
  document.getElementById('loader-sub').textContent=sub||'AI ANALYZING DOCUMENT';
  var bar=document.getElementById('loader-bar');bar.style.width='0%';
  document.getElementById('loader').classList.add('show');
  var w=0;
  var iv=setInterval(function(){w+=Math.random()*12;if(w>85)w=85;bar.style.width=w+'%'},400);
  document.getElementById('loader')._iv=iv;
}
function hideLoader(){
  document.getElementById('loader').classList.remove('show');
  var iv=document.getElementById('loader')._iv;if(iv)clearInterval(iv);
  var bar=document.getElementById('loader-bar');bar.style.width='100%';
  setTimeout(function(){bar.style.width='0%'},500);
}

/* ---- DASHBOARD ---- */
function loadDashboard(){
  fetch('/stats').then(function(r){return r.json()}).then(function(s){
    var te=Object.entries(s.type_counts||{});
    document.getElementById('stat-grid').innerHTML=
      '<div class="stat-card"><div class="stat-top"><div class="stat-icon" style="background:rgba(255,248,231,0);color:var(--gold)"><i class="lucide icon-files"></i></div></div><div class="stat-number">'+s.total+'</div><div class="stat-label">Documents</div><div class="stat-footer" style="color:var(--gold)">• active</div></div>'+
      '<div class="stat-card"><div class="stat-top"><div class="stat-icon" style="background:var(--burgundy-dim);color:var(--burgundy)"><i class="lucide icon-shapes"></i></div></div><div class="stat-number">'+s.types+'</div><div class="stat-label">Types</div><div class="stat-footer" style="color:var(--burgundy);font-family:var(--font-mono);font-size:0.5rem">'+(te.map(function(x){return x[0]+':'+x[1]}).join(' · ')||'—')+'</div></div>'+
      '<div class="stat-card"><div class="stat-top"><div class="stat-icon" style="background:var(--rust-dim);color:var(--rust)"><i class="lucide icon-hard-drive"></i></div></div><div class="stat-number">'+s.total_size+'</div><div class="stat-label">Storage</div><div class="stat-footer" style="color:var(--rust)">• '+s.total+' files</div></div>'+
      '<div class="stat-card"><div class="stat-top"><div class="stat-icon" style="background:rgba(45,74,59,0.1);color:var(--emerald)"><i class="lucide icon-scan-line"></i></div></div><div class="stat-number">'+s.total+'</div><div class="stat-label">Processed</div><div class="stat-footer" style="color:var(--emerald)">• scanned</div></div>';
    document.getElementById('dash-total').textContent=s.total;
    document.getElementById('hud-storage').innerHTML='<strong>STORAGE</strong> '+s.total_size;
    document.getElementById('gallery-count').textContent=s.total;
    document.getElementById('gallery-total').textContent=s.total;
    var sd=document.getElementById('sb-docs');if(sd)sd.textContent=s.total;
    var ss=document.getElementById('sb-storage');if(ss)ss.textContent=s.total_size;
  }).catch(function(){});
  fetch('/history').then(function(r){return r.json()}).then(function(docs){
    var rg=document.getElementById('recent-grid');
    if(!docs.length)rg.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-tertiary);font-family:var(--font-classic);font-size:0.7rem;font-style:italic">No scans yet — begin with the Scanner</div>';
    else rg.innerHTML=docs.slice(0,6).map(function(d){
      var ap=aesc(d.path);
      var isPdf=(d.kind==='pdf')||/\.pdf$/i.test(d.name||'');
      var thumb=isPdf
        ?'<div class="doc-thumb" style="display:flex;align-items:center;justify-content:center;background:var(--paper);color:var(--burgundy);font-size:30px"><i class="lucide icon-file-text"></i></div>'
        :'<img class="doc-thumb" src="'+d.image_url+'" loading="lazy" onerror="this.outerHTML=\'<div style=\\\'display:flex;align-items:center;justify-content:center;height:100%;font-size:28px;color:var(--text-tertiary);opacity:.4;background:var(--bg-deep)\\\'><i class=\\\'lucide icon-image-off\\\'></i></div>\'">';
      return '<div class="doc-card" data-path="'+ap+'" data-name="'+aesc(d.name)+'" data-url="'+aesc(d.image_url)+'" data-size="'+aesc(d.size)+'" data-folder="'+aesc(d.folder)+'" data-kind="'+((d.kind==='pdf')||isPdf?'pdf':'image')+'" onclick="openPreview(this)">'+
        thumb+
        '<div class="doc-overlay"><button onclick="event.stopPropagation();window.open(\''+d.image_url+'\',\'_blank\')"><i class="lucide icon-download"></i></button>'+
        '<button onclick="event.stopPropagation();openPreview(this)"><i class="lucide icon-eye"></i></button>'+
        '<button onclick="event.stopPropagation();deleteDoc(this)"><i class="lucide icon-trash-2"></i></button></div>'+
        '<div class="doc-meta"><div class="doc-name">'+d.name+'</div><div class="doc-sub"><span>'+d.folder+'</span><span>'+d.size+'</span></div></div></div>';
    }).join('');
  }).catch(function(){});
}
function loadActivity(){
  fetch('/activity').then(function(r){return r.json()}).then(function(entries){
    var feed=document.getElementById('feed-list');
    if(!entries.length)feed.innerHTML='<div style="text-align:center;padding:20px;color:var(--text-tertiary);font-family:var(--font-classic);font-size:0.65rem;font-style:italic">No recent activity</div>';
    else feed.innerHTML=entries.map(function(e){
      return '<div class="feed-item"><span class="feed-dot" style="background:'+(e.action==='Scanned'?'var(--gold)':'var(--burgundy)')+';color:'+(e.action==='Scanned'?'var(--gold)':'var(--burgundy)')+'"></span>'+
        '<div class="feed-text"><strong>'+e.action+'</strong> '+e.file+'<div class="feed-sub">→ '+e.folder+'</div></div>'+
        '<span class="feed-time">'+e.time+'</span></div>';
    }).join('');
  }).catch(function(){});
}

/* ---- SCANNER ---- */
document.querySelectorAll('.effect-btn').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('.effect-btn').forEach(function(x){x.classList.remove('active')});
    this.classList.add('active');state.selectedEffect=this.dataset.effect;
    if(state.batchJobId||state.batchItems.length){
      startBatchProcessing();
    }else if(state.capturedBlob){
      updatePreview();
    }
  });
});
document.querySelectorAll('#view-scanner .toggle').forEach(function(t){
  t.addEventListener('click',function(){
    if(state.batchJobId||state.batchItems.length)startBatchProcessing();
  });
});
document.getElementById('btn-close-cam').addEventListener('click',function(e){
  e.stopPropagation();closeCamera();
  document.getElementById('dz-placeholder').style.display='';
});
function shutterSound(){
  try{
    var actx=new(window.AudioContext||window.webkitAudioContext)();
    var g=actx.createGain();g.connect(actx.destination);g.gain.value=0.15;
    // Noise burst for shutter click
    var bf=actx.createBuffer(1,actx.sampleRate*0.06,actx.sampleRate);
    var d=bf.getChannelData(0);
    for(var i=0;i<d.length;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/d.length,4);
    var src=actx.createBufferSource();src.buffer=bf;src.connect(g);
    src.start(0);
    // Sine blip for metallic ring
    var osc=actx.createOscillator();osc.type='sine';osc.frequency.value=1800;
    var g2=actx.createGain();g2.gain.setValueAtTime(0.08,actx.currentTime);
    g2.gain.exponentialRampToValueAtTime(0.001,actx.currentTime+0.06);
    osc.connect(g2);g2.connect(actx.destination);
    osc.start(0);osc.stop(actx.currentTime+0.06);
  }catch(e){}
}
function captureFromCam(){
  var v=document.getElementById('video'),c=document.getElementById('canvas');
  if(!v.videoWidth)return;
  shutterSound();
  // Flash brackets on manual capture
  ['vb-tl','vb-tr','vb-bl','vb-br'].forEach(function(id){
    var el=document.getElementById(id);
    if(el){el.style.borderColor='var(--emerald)';el.style.boxShadow='0 0 20px rgba(45,74,59,0.6)'}
  });
  setTimeout(function(){
    ['vb-tl','vb-tr','vb-bl','vb-br'].forEach(function(id){
      var el=document.getElementById(id);
      if(el){el.style.borderColor='var(--gold)';el.style.boxShadow=''}
    });
  },300);
  c.width=v.videoWidth;c.height=v.videoHeight;
  c.getContext('2d').drawImage(v,0,0,c.width,c.height);
  c.toBlob(function(b){
    state.capturedBlobs.push(b);
    state.capturedBlob=b;
    addFilmstripThumb(b,state.capturedBlobs.length);
  },'image/jpeg',0.85);
}

function addFilmstripThumb(blob,idx){
  var cnt=state.capturedBlobs.length;
  document.getElementById('capture-count-badge').textContent=cnt;
  document.getElementById('btn-process-captures').disabled=false;
  document.getElementById('btn-process').disabled=false;
  var wrap=document.getElementById('filmstrip-thumbs');
  var div=document.createElement('div');div.className='filmstrip-thumb';
  div.dataset.idx=idx-1;
  var img=document.createElement('img');img.src=URL.createObjectURL(blob);
  var num=document.createElement('span');num.className='thumb-num';num.textContent='#'+cnt;
  var del=document.createElement('button');del.className='thumb-del';del.innerHTML='<i class="lucide icon-x"></i>';
  del.onclick=function(e){e.stopPropagation();
    var i=parseInt(div.dataset.idx);
    state.capturedBlobs.splice(i,1);
    div.remove();
    // renumber remaining
    var thumbs=wrap.querySelectorAll('.filmstrip-thumb');
    thumbs.forEach(function(t,n){
      t.dataset.idx=n;
      t.querySelector('.thumb-num').textContent='#'+(n+1);
    });
    var remaining=state.capturedBlobs.length;
    document.getElementById('capture-count-badge').textContent=remaining;
    if(!remaining){
      document.getElementById('btn-process-captures').disabled=true;
      document.getElementById('btn-process').disabled=true;
    }
  };
  div.appendChild(img);div.appendChild(num);div.appendChild(del);
  wrap.appendChild(div);
  wrap.scrollLeft=wrap.scrollWidth;
  toast('Captured #'+cnt);
}
/* ---- CAMERA SYSTEM ---- */
var cameraDevices=[];
var autoCaptureTimer=null,autoCaptureActive=false;
var cameraPermissionPending=false;

function isSecureContext(){
  return window.isSecureContext||location.hostname==='localhost'||location.hostname==='127.0.0.1';
}

/* UNIVERSAL CAMERA FALLBACK: <input type=file capture> opens the NATIVE OS camera app.
   Works on every device/browser (HTTP, LAN IP, webviews, old browsers) — no getUserMedia needed. */
function openNativeCameraFallback(reason){
  var inp=document.getElementById('native-capture');
  if(!inp)return false;
  toast(reason+' — OPENING DEVICE CAMERA INSTEAD','warn');
  inp.click();
  return true;
}

function requestCameraPermission(callback){
  if(cameraPermissionPending)return;
  cameraPermissionPending=true;
  toast('REQUESTING CAMERA PERMISSION...');
  navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(function(stream){
    stream.getTracks().forEach(function(t){t.stop()});
    cameraPermissionPending=false;
    toast('CAMERA PERMISSION GRANTED');
    if(callback)callback();
  }).catch(function(e){
    cameraPermissionPending=false;
    var msg=e.message||'';
    if(msg.includes('NotFound')||msg.includes('No device')){
      toast('NO CAMERA FOUND on this device','err');
    }else{
      openNativeCameraFallback('LIVE VIEW UNAVAILABLE ('+(msg||'permission denied')+')');
    }
    if(callback)callback();
  });
}

function refreshCameraList(callback){
  if(!navigator.mediaDevices||!navigator.mediaDevices.enumerateDevices)return;
  navigator.mediaDevices.enumerateDevices().then(function(devices){
    cameraDevices=devices.filter(function(x){return x.kind==='videoinput'});
    var sel=document.getElementById('cam-device-select');
    sel.innerHTML=cameraDevices.map(function(d,i){
      return '<option value="'+d.deviceId+'">'+(d.label||'CAM '+(i+1))+'</option>';
    }).join('');
    if(!cameraDevices.length){
      sel.innerHTML='<option value="">— NO CAMERAS —</option>';
    }
    if(callback)callback();
  }).catch(function(){});
}

function showCameraUI(s){
  var v=document.getElementById('video');
  state.stream=s;
  v.srcObject=s;v.setAttribute('playsinline','');v.setAttribute('autoplay','');v.setAttribute('muted','');
  v.play().catch(function(){});
  document.getElementById('cam-view').style.display='flex';
  document.getElementById('cam-view').style.width='100%';
  document.getElementById('dz-placeholder').style.display='none';
  document.getElementById('btn-close-cam').style.display='';
  document.getElementById('vf-overlay').classList.add('active');
  document.getElementById('capture-filmstrip').style.display='';
  document.getElementById('cam-selector-wrap').style.display='';
  document.getElementById('shutter-btn').classList.add('active');
  document.getElementById('btn-open-cam').innerHTML='<i class="lucide icon-x"></i> CLOSE CAMERA';
  document.getElementById('btn-open-cam').style.background='var(--crimson)';
  refreshCameraList();
  if(!isSecureContext()){
    var w=document.getElementById('https-warning');
    if(w)w.style.display='flex';
  }
  startAutoDetect();
}

function tryCamera(method,callback){
  // Method 1: rear camera with constraints
  // Method 2: basic video fallback
  var constraints;
  if(method===1){
    constraints={video:{facingMode:'environment',width:{ideal:640},height:{ideal:480}},audio:false};
  }else{
    constraints={video:true,audio:false};
  }
  navigator.mediaDevices.getUserMedia(constraints).then(function(s){
    showCameraUI(s);
    if(callback)callback(true);
  }).catch(function(e){
    if(callback)callback(false,e);
  });
}

function startCamera(deviceId){
  // If a specific deviceId is given, use it directly
  if(deviceId&&deviceId!=='__any__'){
    var constraints={video:{deviceId:{exact:deviceId},width:{ideal:640},height:{ideal:480}},audio:false};
    navigator.mediaDevices.getUserMedia(constraints).then(function(s){
      showCameraUI(s);
    }).catch(function(e){
      var msg=e.message||'';
      if(msg.includes('NotFound')||msg.includes('deviceId')){
        refreshCameraList(function(){
          if(cameraDevices.length){toast('SWITCHED');startCamera(cameraDevices[0].deviceId)}
          else toast('NO CAMERA','err');
        });
      }else if(msg.includes('NotAllowed')||msg.includes('Permission')){
        openNativeCameraFallback('CAMERA BLOCKED — ALLOW ACCESS OR USE DEVICE CAMERA');
      }else{
        toast('CAMERA: '+msg,'err');
      }
    });
    return;
  }

  // No deviceId — try Method 1 (rear camera), fallback to Method 2 (basic)
  tryCamera(1,function(ok,err){
    if(!ok){
      var msg=err&&err.message||'';
      if(msg.includes('facingMode')||msg.includes('Overconstrained')||msg.includes('constraint')){
        toast('REAR CAMERA UNAVAILABLE — TRYING DEFAULT');
        tryCamera(2,function(ok2,err2){
          if(!ok2){
            var msg2=err2&&err2.message||'';
            if(msg2.includes('NotAllowed')||msg2.includes('Permission')){
              openNativeCameraFallback('CAMERA BLOCKED — USING DEVICE CAMERA');
            }else{
              toast('CAMERA: '+msg2,'err');
            }
          }
        });
      }else if(msg.includes('NotAllowed')||msg.includes('Permission')){
        openNativeCameraFallback('CAMERA BLOCKED — USING DEVICE CAMERA');
      }else{
        toast('CAMERA: '+msg,'err');
      }
    }
  });
}

document.getElementById('btn-open-cam').addEventListener('click',function(e){
  e.stopPropagation();e.preventDefault();
  if(state.stream){closeCamera();return}

  /* Cross-platform strategy:
     1) HTTPS + modern browser -> live getUserMedia view (best UX)
     2) Anything else (HTTP, LAN IP, old browser, webview) -> native OS camera app
        via hidden <input capture>, which is universally supported. */
  if(!isSecureContext()){
    openNativeCameraFallback('LIVE CAMERA NEEDS HTTPS');
    return;
  }
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    openNativeCameraFallback('THIS BROWSER LACKS THE CAMERA API');
    return;
  }

  // Step 1: try to get permission silently (grants enumerateDevices labels)
  requestCameraPermission(function(){
    // Step 2: refresh the device list now that we have permission
    refreshCameraList(function(){
      // Step 3: try method 1 (rear camera) first; if fails, method 2 (basic)
      startCamera(null);
    });
  });
});

document.getElementById('cam-device-select').addEventListener('change',function(){
  if(state.stream){
    state.stream.getTracks().forEach(function(t){t.stop()});state.stream=null;
  }
  setTimeout(function(){startCamera(document.getElementById('cam-device-select').value)},300);
});

/* ---- PHONE CAMERA BUTTON (tries getUserMedia first, falls back to native input) ---- */
function dataURLtoBlob(dataURL){
  var parts=dataURL.split(','),
      mime=parts[0].match(/:(.*?);/)[1],
      bin=atob(parts[1]),arr=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
  return new Blob([arr],{type:mime});
}
function phoneCameraCapture(){
  if(state.stream){closeCamera();return}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    // No API at all (HTTP/old browser) — native camera input works everywhere
    openNativeCameraFallback('THIS BROWSER LACKS THE CAMERA API');
    return;
  }
  // Try getUserMedia first (opens actual camera on supported browsers)
  navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(function(s){
    // Success — use the stream (same as OPEN CAMERA)
    showCameraUI(s);
    toast('CAMERA READY');
  }).catch(function(){
    // Failed (permission, etc.) — fall back to native capture input
    openNativeCameraFallback('LIVE CAMERA UNAVAILABLE');
  });
}

function startAutoDetect(){
  autoCaptureActive=true;
  var v=document.getElementById('video');
  var prevPixels=null,stillFrames=0;
  var CAPTURE_THRESHOLD=8; // higher = more stable required
  var STILL_FRAMES_NEEDED=6; // frames object must be steady before capture
  var detectCanvas=document.createElement('canvas'); // OFFSCREEN - never touches the capture canvas
  var dctx=detectCanvas.getContext('2d');
  var lastDetectPost=0,detectPending=false;
  var lastDocDetected=null;
  var brackets=['vb-tl','vb-tr','vb-bl','vb-br'];

  // REAL edge detection (server-side Canny contour) every ~700ms.
  // This is step ONE of the pipeline: edges -> crop -> enhance -> OCR.
  function postAutoDetect(){
    if(!v.videoWidth||!autoCaptureActive||detectPending)return;
    var now=Date.now();
    if(now-lastDetectPost<700)return;
    lastDetectPost=now;
    var tw=180,th=Math.round(180*v.videoHeight/v.videoWidth);
    detectCanvas.width=tw;detectCanvas.height=th;
    dctx.drawImage(v,0,0,tw,th);
    var jpg=detectCanvas.toDataURL('image/jpeg',0.6);
    detectPending=true;
    var fd=new FormData();
    fd.append('image',dataURLtoBlob(jpg),'frame.jpg');
    fetch('/api/auto-detect',{method:'POST',body:fd})
      .then(function(r){return r.json()})
      .then(function(d){
        detectPending=false;
        if(!d||typeof d.document_detected!=='boolean')return;
        lastDocDetected=d.document_detected;
        // Telemetry shows REAL detection state now
        var tel=document.getElementById('tel-edge');
        if(tel)tel.textContent=d.document_detected?'DOC LOCKED':(diffState==='STEADY'?'STEADY':'SCANNING');
        // Solid emerald brackets only when a real document quad is locked
        brackets.forEach(function(id){
          var el=document.getElementById(id);
          if(el){el.style.borderColor=d.document_detected?'var(--emerald)':'var(--gold)';
                 el.style.boxShadow=d.document_detected?'0 0 14px rgba(45,74,59,0.45)':''}
        });
      })
      .catch(function(){detectPending=false});
  }

  var diffState='MOVING';
  autoCaptureTimer=setInterval(function(){
    if(!v.videoWidth||!autoCaptureActive)return;
    // Grab a tiny thumbnail (80x60) for fast pixel comparison
    var tw=80,th=60;
    detectCanvas.width=tw;detectCanvas.height=th;
    dctx.drawImage(v,0,0,tw,th);
    try{
      var data=dctx.getImageData(0,0,tw,th).data;
    }catch(e){return}

    // Compute difference from previous frame
    var diff=0;
    if(prevPixels){
      for(var i=0;i<data.length;i+=4){
        var gray=(data[i]+data[i+1]+data[i+2])/3;
        var prevGray=(prevPixels[i]+prevPixels[i+1]+prevPixels[i+2])/3;
        diff+=Math.abs(gray-prevGray);
      }
      diff/=(tw*th); // average per-pixel difference
    }
    prevPixels=data;

    // Also compute average brightness (to know if something is in frame)
    var totalBright=0;
    for(var i=0;i<data.length;i+=4){
      totalBright+=(data[i]+data[i+1]+data[i+2])/3;
    }
    var avgBright=totalBright/(tw*th);

    // Update telemetry
    diffState=diff<CAPTURE_THRESHOLD?'STEADY':'MOVING';
    if(lastDocDetected!==true){ // DOC LOCKED label set by server response
      document.getElementById('tel-edge').textContent=lastDocDetected===false&&diffState==='STEADY'?'OBJECT STEADY':diffState;
    }
    document.getElementById('tel-blur').textContent='Δ'+diff.toFixed(1);
    document.getElementById('tel-glare').textContent='LV'+avgBright.toFixed(0);

    // Kick off real edge detection in parallel (non-blocking)
    postAutoDetect();

    // Bracket pulse animation while the object is steady
    if(diff<CAPTURE_THRESHOLD&&avgBright>30&&avgBright<240){
      stillFrames++;
      // Animate brackets while document is steady
      var pulse=stillFrames/STILL_FRAMES_NEEDED;
      var opacity=0.4+pulse*0.6;
      var color=(lastDocDetected===true)?'var(--emerald)':(pulse>0.5?'var(--emerald)':'var(--gold)');
      var size=36+pulse*8;
      brackets.forEach(function(id){
        var el=document.getElementById(id);
        if(el){el.style.opacity=opacity;el.style.borderColor=color;el.style.width=size+'px';el.style.height=size+'px'}
      });
      // AUTO-CAPTURE GATE: edges must have been checked first. Documents are
      // captured as soon as the quad locks; any other object (2D/3D) captures
      // once it holds still. Cropping/enhancement happen server-side next.
      var gateOpen=(lastDocDetected===true&&stillFrames>=Math.min(2,STILL_FRAMES_NEEDED))
                  ||(lastDocDetected!==null&&stillFrames>=STILL_FRAMES_NEEDED);
      if(gateOpen){
        stillFrames=0;
        shutterSound();
        // Flash brackets on capture
        brackets.forEach(function(id){
          var el=document.getElementById(id);
          if(el){el.style.borderColor='var(--emerald)';el.style.boxShadow='0 0 20px rgba(45,74,59,0.6)'}
        });
        setTimeout(function(){
          brackets.forEach(function(id){
            var el=document.getElementById(id);
            if(el){el.style.borderColor='var(--gold)';el.style.boxShadow='';el.style.width='36px';el.style.height='36px';el.style.opacity='1'}
          });
        },300);
        // Capture full-res frame from the LIVE video element directly,
        // never from the tiny analysis canvas
        var bigC=document.createElement('canvas');
        bigC.width=v.videoWidth;bigC.height=v.videoHeight;
        bigC.getContext('2d').drawImage(v,0,0);
        bigC.toBlob(function(bigBlob){
          state.capturedBlobs.push(bigBlob);
          state.capturedBlob=bigBlob;
          addFilmstripThumb(bigBlob,state.capturedBlobs.length);
        },'image/jpeg',0.85);
      }
    }else{
      stillFrames=0;
      brackets.forEach(function(id){
        var el=document.getElementById(id);
        if(el){el.style.opacity='1';el.style.borderColor=lastDocDetected===true?'var(--emerald)':'var(--gold)';el.style.width='36px';el.style.height='36px';el.style.boxShadow=''}
      });
    }
  },200); // faster check interval
}
function stopAutoDetect(){
  autoCaptureActive=false;
  if(autoCaptureTimer){clearInterval(autoCaptureTimer);autoCaptureTimer=null}
  document.getElementById('tel-edge').textContent='--';
}
function closeCamera(){
  stopAutoDetect();
  if(state.stream){state.stream.getTracks().forEach(function(t){t.stop()});state.stream=null}
  document.getElementById('cam-view').style.display='none';
  document.getElementById('btn-close-cam').style.display='none';
  document.getElementById('vf-overlay').classList.remove('active');
  document.getElementById('capture-filmstrip').style.display='none';
  document.getElementById('cam-selector-wrap').style.display='none';
  document.getElementById('shutter-btn').classList.remove('active');
  document.getElementById('btn-open-cam').innerHTML='<i class="lucide icon-camera"></i> OPEN CAMERA';
  document.getElementById('btn-open-cam').style.background='';
}

function processAllCaptures(){
  startBatchProcessing();
}

/* ---- BATCH PROCESSING (upload → original preview → PROCESS applies settings → DONE saves) ---- */
function startBatchProcessing(){
  var files=state.capturedBlobs.filter(function(b){return b});
  if(!files.length){toast('NO FILES','warn');return}
  setScannerTick('PROCESSING '+files.length+' FILE(S)...',true);
  state.batchPdfAsked=false;
  showLoader('PROCESSING...','AI ANALYZING '+files.length+' FILE(S)');
  var fd=new FormData();
  for(var i=0;i<files.length;i++){
    var f=files[i];
    fd.append('files',f,(f.name||('capture_'+(i+1)+'.jpg')));
  }
  fd.append('auto_crop',document.getElementById('tog-crop').classList.contains('on')?'true':'false');
  fd.append('shadow_removal',document.getElementById('tog-shadow').classList.contains('on')?'true':'false');
  fd.append('enhance',document.getElementById('tog-enhance').classList.contains('on')?'true':'false');
  fd.append('effect',state.selectedEffect);
  fd.append('use_google_vision',document.getElementById('tog-vision').classList.contains('on')?'true':'false');
  fd.append('use_handwriting',document.getElementById('tog-handwriting').classList.contains('on')?'true':'false');
  fd.append('dewarp',document.getElementById('tog-dewarp').classList.contains('on')?'true':'false');
  fetch('/api/batch/process',{method:'POST',body:fd})
    .then(function(r){return r.json()})
    .then(function(data){
      hideLoader();
      if(data.error){toast(data.error,'err');return}
      state.batchJobId=data.job_id;
      state.batchItems=data.items||[];
      renderBatchStrip(data.items,data.errors||[]);
      if(!state.batchItems.length){toast('NO FILES COULD BE PROCESSED','err');return}
      if(state.batchItems.length>1){
        if(!state.batchPdfAsked){
          state.batchPdfAsked=true;
          showChoice(
            state.batchItems.length+' FILES READY — CONVERT ALL TO A SINGLE PDF, OR SAVE THEM AS SEPARATE IMAGES?',
            'PDF + SAVE','IMAGES + SAVE',
            function(){doneSaveBatch(true)},
            function(){doneSaveBatch(false)});
        }else{
          document.getElementById('done-bar').style.display='flex';
        }
      }else{
        document.getElementById('done-bar').style.display='flex';
        updateBatchHint();
        toast('PROCESSED — make changes or press DONE to save');
      }
      updateBatch();
      setScannerTick('READY — '+state.batchItems.length+' PROCESSED',false);
    })
    .catch(function(e){hideLoader();toast('PROCESS ERROR: '+e.message,'err');setScannerTick('PROCESS ERROR',true)});
}
function renderBatchStrip(items,errors){
  var strip=document.getElementById('batch-strip');
  var wt={none:'',grayscale:'(GRAY)',binarize:'(B&W)',sharpen:'(SHARP)',invert:'(INVERT)',enhance:'(ENH)'};
  strip.innerHTML=items.map(function(it){
    var label=it.title||it.name||it.key;
    if(it.kind==='pdf'){
      return '<div class="filmstrip-thumb" title="'+esc(label)+'"><div style="width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:var(--cream);color:var(--burgundy);font-size:22px"><i class="lucide icon-file-text"></i></div><span class="thumb-num">PDF</span></div>';
    }
    return '<div class="filmstrip-thumb" title="'+esc(label)+'"><img src="'+it.url+'"><span class="thumb-num">'+(wt[state.selectedEffect]||'')+'</span></div>';
  }).join('');
  document.getElementById('batch-strip-count').textContent=items.length;
  document.getElementById('done-bar').style.display='flex';
  updateBatchHint();
  if(items.length){
    var last=items[items.length-1];
    if(last.url){
      document.getElementById('preview-img').src=last.url;
      document.getElementById('scan-preview').classList.add('active');
      document.getElementById('dz-placeholder').style.display='none';
    }
  }
}
function updateBatch(){
  var n=state.capturedBlobs.filter(function(b){return b}).length;
  var cnt=document.getElementById('batch-strip-count');
  if(cnt)cnt.textContent=n;
  var pb=document.getElementById('btn-process');
  if(pb)pb.disabled=n===0;
  updateBatchHint();
}
function updateBatchHint(){
  var lbl=document.getElementById('batch-status-label');
  if(!lbl)return;
  var bar=document.getElementById('done-bar');
  if(state.batchJobId&&state.batchItems.length){
    lbl.innerHTML='<i class="lucide icon-badge-check" style="vertical-align:-1px"></i> READY — effect settings applied &amp; pending save';
  }else if(state.capturedBlobs.length){
    lbl.innerHTML='<i class="lucide icon-eye" style="vertical-align:-1px"></i> ORIGINAL PREVIEW — tune settings &amp; press PROCESS';
  }else{
    lbl.innerHTML='AWAITING FILES';
  }
}
function setScannerTick(txt,busy){
  var el=document.getElementById('sb-tick-label');
  var dot=document.querySelector('#sb-scan-tick .dot');
  if(el)el.textContent=txt;
  if(dot){dot.className='dot '+(busy?'busy':'on')}
}
function doneSaveBatch(asPdf){
  if(!state.batchJobId||!state.batchItems.length){toast('NOTHING TO SAVE — press PROCESS first','warn');return}
  if(asPdf===undefined&&state.batchItems.length>1){
    showChoice(
      state.batchItems.length+' FILES READY — CONVERT ALL TO A SINGLE PDF, OR SAVE THEM AS SEPARATE IMAGES?',
      'PDF + SAVE','IMAGES + SAVE',
      function(){doneSaveBatch(true)},
      function(){doneSaveBatch(false)});
    return;
  }
  showLoader('SAVING...',asPdf?'GENERATING PDF...':'COMMITTING TO ARCHIVE');
  fetch('/api/batch/done',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({job_id:state.batchJobId,keys:state.batchItems.map(function(it){return it.key}),as_pdf:!!asPdf})})
    .then(function(r){return r.json()})
    .then(function(data){
      hideLoader();
      if(data.error){toast(data.error,'err');return}
      var n=data.count||0;
      toast(asPdf?'PDF SAVED: '+data.pdf_name:'SAVED '+n+' FILES TO VAULT');
      resetBatch();
      loadGallery();loadDashboard();
    })
    .catch(function(e){hideLoader();toast('SAVE ERROR: '+e.message,'err')});
}
function cancelBatch(){
  var n=state.capturedBlobs.filter(function(b){return b}).length;
  resetBatch();
  document.getElementById('filmstrip-thumbs').innerHTML='';
  document.getElementById('preview-img').removeAttribute('src');
  document.getElementById('scan-preview').classList.remove('active');
  document.getElementById('dz-placeholder').style.display='';
  state.capturedBlobs=[];state.capturedBlob=null;
  document.getElementById('btn-process-captures').disabled=true;
  document.getElementById('capture-count-badge').textContent='0';
  if(n)toast('CANCELLED — '+n+' FILE(S) DISCARDED','warn');
}
function retakeBatch(){
  cancelBatch();
  closeCamera();
  var oc=document.getElementById('btn-open-cam');
  setTimeout(function(){oc.click()},50);
}
function reuploadBatch(){
  cancelBatch();
  var fi2=document.getElementById('file-input');
  fi2.value='';
  fi2.click();
}
function resetBatch(){
  document.getElementById('done-bar').style.display='none';
  document.getElementById('batch-strip').innerHTML='';
  state.batchJobId=null;state.batchItems=[];state.batchPdfAsked=false;
  updateBatch();
}

var dz=document.getElementById('drop-zone'),fi=document.getElementById('file-input');
dz.addEventListener('click',function(e){
  if(document.getElementById('dz-placeholder').style.display!=='none'&&document.getElementById('cam-view').style.display!=='flex')fi.click();
});
dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('dragover')});
dz.addEventListener('dragleave',function(){dz.classList.remove('dragover')});
dz.addEventListener('drop',function(e){
  e.preventDefault();dz.classList.remove('dragover');
  var fl=[].slice.call(e.dataTransfer.files);
  if(fl.length)handleFiles(fl);else toast('DROP FILES','err');
});
fi.addEventListener('change',function(e){if(e.target.files.length)handleFiles([].slice.call(e.target.files))});
function handleFiles(files){
  var supported=files.filter(function(f){return f.type&&f.type.startsWith('image/')||f.name.match(/\.(png|jpe?g|bmp|webp|tiff?|pdf|docx?|xlsx?|csv|tsv|ppt|pptx|txt|md|rtf|log)$/i)});
  var skipped=files.length-supported.length;
  if(skipped)toast('SKIPPED '+skipped+' UNSUPPORTED FILE(S)','warn');
  if(!supported.length){toast('NO SUPPORTED FILES','err');return}
  supported.forEach(function(f){
    state.capturedBlobs.push(f);
    state.capturedBlob=f;
    addFilmstripThumb(f,state.capturedBlobs.length);
    if(!document.getElementById('scan-preview').classList.contains('active')){
      document.getElementById('preview-img').src=URL.createObjectURL(f);
      document.getElementById('scan-preview').classList.add('active');
    }
  });
  document.getElementById('dz-placeholder').style.display='none';
document.getElementById('btn-process').disabled=false;
  document.getElementById('batch-strip-count').textContent=state.capturedBlobs.length;
  document.getElementById('done-bar').style.display='flex';
  document.getElementById('done-bar').classList.add('origin');
  updateBatch();
}
function handleFile(f){
  state.capturedBlob=f;
  state.capturedBlobs.push(f);
  var cnt=state.capturedBlobs.length;
  document.getElementById('capture-count-badge').textContent=cnt;
  document.getElementById('btn-process-captures').disabled=false;
  document.getElementById('preview-img').src=URL.createObjectURL(f);
  document.getElementById('scan-preview').classList.add('active');
  document.getElementById('dz-placeholder').style.display='none';
  document.getElementById('btn-process').disabled=false;
  document.getElementById('batch-strip-count').textContent=cnt;
document.getElementById('done-bar').style.display='flex';
  document.getElementById('done-bar').classList.add('origin');
  updateBatch();
}
// Native camera capture handler (works on ALL phones, no getUserMedia needed)
document.getElementById('native-capture').addEventListener('change',function(e){
  var f=e.target.files[0];
  if(!f)return;
  handleFile(f);
  toast('PHOTO CAPTURED #'+state.capturedBlobs.length);
  this.value='';
});
// Post-process save/download
var processedResults=[];
function saveProcessedResults(){
  // Results are already saved by /scan/advanced — this notifies user
  var n=processedResults.length;
  if(!n){toast('No processed results','warn');return}
  toast('SAVED '+n+' document'+(n>1?'s':'')+' TO VAULT');
  document.getElementById('post-process-actions').style.display='none';
  processedResults=[];
  loadGallery();
}
function downloadLastResult(){
  if(!processedResults.length){toast('No results','warn');return}
  var last=processedResults[processedResults.length-1];
  if(last&&last.image_url) window.location.href=last.image_url;
}
function updatePreview(){
  if(!state.capturedBlob)return;
  var fd=new FormData();fd.append('image',state.capturedBlob,'p.jpg');
  fd.append('effect',state.selectedEffect);
  fd.append('auto_crop',document.getElementById('tog-crop').classList.contains('on')?'true':'false');
  fd.append('shadow_removal',document.getElementById('tog-shadow').classList.contains('on')?'true':'false');
  fetch('/effects/preview',{method:'POST',body:fd}).then(function(r){if(r.ok)return r.blob()}).then(function(b){if(b)document.getElementById('preview-img').src=URL.createObjectURL(b)}).catch(function(){});
}
document.getElementById('btn-process').addEventListener('click',function(){
  if(!state.capturedBlobs.length)return;
  startBatchProcessing();
});
function showResults(r){
  document.getElementById('result-panel').style.display='block';
  document.getElementById('scanner-grid').classList.add('full');
  var t=r.classification.type.charAt(0).toUpperCase()+r.classification.type.slice(1);
  document.getElementById('result-title').textContent=t;
  var b=document.getElementById('result-badge');b.style.display='';
  b.className='badge '+(r.quality.quality_pass?'badge-green':'badge-red');
  b.textContent=r.quality.quality_pass?'PASS':'FAIL';
  var cp=document.getElementById('result-compare');
  var h='';
  if(r.original_url)h+='<div class="img-box"><img src="'+r.original_url+'"><span class="img-label">ORIGINAL</span></div>';
  if(r.image_url)h+='<div class="img-box"><img src="'+r.image_url+'"><span class="img-label">ENHANCED</span></div>';
  cp.innerHTML=h;
  var conf=(r.classification.confidence*100).toFixed(0);
  document.getElementById('result-grid').innerHTML=
    '<div class="stat-card" style="padding:10px"><div style="color:var(--burgundy);font-size:1rem;font-weight:700;font-family:var(--font-display)">'+t+'</div><div class="stat-label">Type</div></div>'+
    '<div class="stat-card" style="padding:10px"><div style="font-size:1rem;font-weight:700">'+conf+'%</div><div class="stat-label">Confidence</div></div>'+
    '<div class="stat-card" style="padding:10px"><div style="font-size:1rem;font-weight:700">'+(r.dimensions||'--')+'</div><div class="stat-label">Dimensions</div></div>'+
    '<div class="stat-card" style="padding:10px"><div style="font-size:1rem;font-weight:700">'+(r.file_size||'--')+'</div><div class="stat-label">Size</div></div>'+
    '<div class="stat-card" style="padding:10px"><div style="font-size:1rem;font-weight:700">'+r.ocr_length+'</div><div class="stat-label">Text</div></div>'+
    '<div class="stat-card" style="padding:10px"><div style="font-size:1rem;font-weight:700;color:'+(r.quality.quality_pass?'var(--emerald)':'var(--crimson)')+'"><i class="lucide icon-'+(r.quality.quality_pass?'badge-check':'badge-x')+'" style="vertical-align:-1px"></i></div><div class="stat-label">Quality</div></div>';
  var det=document.getElementById('result-details');
  var dh='<div class="ctrl-group" style="margin-top:4px"><h4>Details</h4>';
  dh+='<div class="toggle-row"><span>FILENAME</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+r.filename+'</span></div>';
  dh+='<div class="toggle-row"><span>BRIGHTNESS</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+r.quality.brightness+'</span></div>';
  dh+='<div class="toggle-row"><span>LIGHTING</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+(r.quality.good_lighting?'PASS':'POOR')+'</span></div>';
  dh+='<div class="toggle-row"><span>BLUR</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+r.quality.blur_score+'</span></div>';
  dh+='<div class="toggle-row"><span>OCR CONF</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+(r.ocr.confidence*100).toFixed(0)+'%</span></div>';
  var ex=r.classification.extracted_data||{};
  if(Object.keys(ex).length) for(var k in ex) dh+='<div class="toggle-row"><span>'+k.toUpperCase()+'</span><span style="font-family:var(--font-mono);font-size:0.55rem;color:var(--text-tertiary)">'+ex[k]+'</span></div>';
  dh+='</div>';det.innerHTML=dh;
  var od=document.getElementById('result-ocr');
  if(r.ocr.text) od.innerHTML='<div class="ctrl-group"><h4>OCR Text</h4><div style="background:var(--cream);padding:6px 8px;border-radius:var(--radius-sm);font-family:var(--font-mono);font-size:0.55rem;line-height:1.5;max-height:120px;overflow-y:auto;white-space:pre-wrap;color:var(--text-secondary);margin-top:4px;border:1px solid rgba(201,169,110,0.06)">'+esc(r.ocr.text)+'</div></div>';
  else od.innerHTML='';
  state.lastOcrText=r.ocr.text||'';
  var ra=document.getElementById('result-ai');
  if(ra)ra.innerHTML='<div style="display:flex;gap:6px;flex-wrap:wrap">'+
    '<button class="ai-chip" onclick="aiResultSummary()"><i class="lucide icon-sparkles"></i> AI Summary</button>'+
    '<button class="ai-chip" onclick="aiCaptureTips()"><i class="lucide icon-lightbulb"></i> Capture Tips</button>'+
    '</div>';
  if(state.autoSummarize&&state.lastOcrText)setTimeout(aiResultSummary,300);
  var qd=document.getElementById('result-qr');
  if(r.qr_codes&&r.qr_codes.length) qd.innerHTML='<div class="ctrl-group"><h4>QR / Barcodes</h4>'+r.qr_codes.map(function(q){return '<div style="background:var(--cream);padding:4px 6px;border-radius:4px;margin-top:3px;font-family:var(--font-mono);font-size:0.55rem;word-break:break-all;border:1px solid rgba(201,169,110,0.06)"><strong>'+q.type+':</strong> '+q.data+'</div>';}).join('')+'</div>';
  else qd.innerHTML='';
  document.getElementById('btn-dl').onclick=function(){window.open(r.image_url,'_blank')};
  var cb=document.getElementById('btn-cloud');
  if(r.saved_path){cb.style.display='';cb.dataset.path=(r.saved_path.split('documents\\').pop()||r.saved_path.split('documents/').pop())}else cb.style.display='none';
  state.lastDocPath=cb.dataset.path||null;
  var ab=document.getElementById('btn-ai-insights');
  if(ab)ab.classList.toggle('disabled',!r.ocr.text);
}
function cloudUploadFromResult(){
  var cb=document.getElementById('btn-cloud');
  var path=cb.dataset.path;
  if(!path){toast('NO SAVED PATH','err');return}
  showPrompt('PROVIDER (google_drive, dropbox, onedrive, all):',function(v){
    if(v==='all'||!v){cloudUpload(path,'google_drive');cloudUpload(path,'dropbox');cloudUpload(path,'onedrive')}
    else cloudUpload(path,v);
  });
}
function resetScanner(){
  document.getElementById('result-panel').style.display='none';
  document.getElementById('scanner-grid').classList.remove('full');
  document.getElementById('scan-preview').classList.remove('active');
  document.getElementById('dz-placeholder').style.display='';
  document.getElementById('filmstrip-thumbs').innerHTML='';
  document.getElementById('btn-process-captures').disabled=true;
  state.capturedBlobs=[];
  state.capturedBlob=null;state.currentResult=null;
  resetBatch();
  fi.value='';document.getElementById('btn-process').disabled=true;
  setScannerTick('SCANNER IDLE',false);
}

/* ---- GALLERY / VAULT ---- */
function loadGallery(){
  fetch('/history').then(function(r){return r.json()}).then(function(docs){
    state.galleryDocs=docs;
    document.getElementById('gallery-count').textContent=docs.length;
    document.getElementById('gallery-total').textContent=docs.length;
    var mc=document.getElementById('merged-count');
    if(mc)mc.textContent=docs.filter(function(d){return d.folder==='merged'}).length;
    renderGallery();
  }).catch(function(){toast('VAULT LOAD ERROR','err')});
}
function aesc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function _pathOf(el){
  if(typeof el==='string')return el;
  if(el&&el.getAttribute){
    var p=el.getAttribute('data-path');
    if(p)return p;
    var c=el.closest?el.closest('.doc-card'):null;
    if(c&&c.getAttribute)return c.getAttribute('data-path');
  }
  return null;
}
function renderGallery(){
  var c=document.getElementById('gallery-container');
  var docs=state.galleryDocs;
  if(state.filter!=='all')docs=docs.filter(function(d){return d.folder===state.filter});
  if(!docs.length){
    c.innerHTML='<div style="text-align:center;padding:60px;color:var(--text-tertiary)"><div style="font-size:48px;margin-bottom:8px;opacity:.15;font-family:var(--font-classic)"><i class="lucide icon-archive"></i></div><p style="font-family:var(--font-classic);font-size:0.7rem;font-style:italic">No documents found</p></div>';
    updateMergeBar();return;
  }
  c.innerHTML='<div class="doc-grid">'+docs.map(function(d){
    var s=state.selectedDocs.includes(d.path);
    var ap=aesc(d.path);
    var thumb=d.kind==='pdf'
      ?'<div class="doc-thumb pdf-thumb" style="display:flex;align-items:center;justify-content:center;background:var(--paper);color:var(--burgundy);font-size:30px"><i class="lucide icon-file-text"></i></div>'
      :'<img class="doc-thumb" src="'+d.image_url+'" loading="lazy" onerror="this.outerHTML=\'<div style=\\\'display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);opacity:.4;background:var(--bg-deep)\\\'><i class=\'lucide icon-image-off\'></i></div>\'">';
    return '<div class="doc-card '+(s?'selected':'')+'" data-path="'+ap+'" onclick="toggleDoc(this)">'+
      '<div class="doc-thumb-wrap">'+thumb+
      '<label class="doc-check" title="Select / deselect" data-path="'+ap+'" onclick="event.stopPropagation();toggleDoc(this)"><span><i class="lucide icon-check" style="font-size:11px;pointer-events:none"></i></span></label>'+
      '<div class="doc-overlay"><button onclick="event.stopPropagation();openPreview(this)"><i class="lucide icon-search"></i></button>'+
      '<button onclick="event.stopPropagation();window.open(\''+d.image_url+'\',\'_blank\')"><i class="lucide icon-download"></i></button>'+
      '<button onclick="event.stopPropagation();deleteDoc(this)"><i class="lucide icon-trash-2"></i></button></div></div>'+
      '<div class="doc-meta"><div class="doc-name">'+d.name+'</div><div class="doc-sub"><span>'+d.folder+'</span><span>'+d.size+'</span></div></div></div>';
  }).join('')+'</div>';
  updateMergeBar();
}
function showMergedGallery(){
  state.filter='merged';
  document.querySelectorAll('#filter-group button').forEach(function(b){b.classList.toggle('active',b.dataset.filter==='merged')});
  switchView('gallery');
  loadGallery();
}
function updateMergeBar(){
  var bar=document.getElementById('merge-bar');
  var n=state.selectedDocs.length;
  if(!bar)return;
  bar.style.display=n?'block':'none';
  var cnt=document.getElementById('merge-bar-count');
  if(cnt)cnt.textContent=n;
  var btn=document.getElementById('btn-merge');
  if(btn)btn.style.display=n>=2?'inline-flex':'none';
  var hint=document.getElementById('merge-bar-hint');
  if(hint)hint.textContent=n===1?'SELECT 2+ TO MERGE INTO PDF':'';
  var sa=document.getElementById('btn-select-all');
  if(sa)sa.style.display=(state.filter==='all'||state.galleryDocs.length)?'inline-flex':'none';
}
function selectAllDocs(){
  var docs=state.galleryDocs;
  if(state.filter!=='all')docs=docs.filter(function(d){return d.folder===state.filter});
  var allSelected=docs.length>0&&docs.every(function(d){return state.selectedDocs.includes(d.path)});
  if(allSelected){
    state.selectedDocs=state.selectedDocs.filter(function(p){return !docs.some(function(d){return d.path===p})});
  }else{
    docs.forEach(function(d){if(state.selectedDocs.indexOf(d.path)<0)state.selectedDocs.push(d.path)});
  }
  renderGallery();
}
function clearSelection(){
  state.selectedDocs=[];
  renderGallery();
}
document.querySelectorAll('#filter-group button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('#filter-group button').forEach(function(x){x.classList.remove('active')});
    this.classList.add('active');state.filter=this.dataset.filter;renderGallery();
  });
});
function toggleDoc(el){
  var p=_pathOf(el);
  if(p==null)return;
  var i=state.selectedDocs.indexOf(p);
  if(i>-1)state.selectedDocs.splice(i,1);else state.selectedDocs.push(p);
  renderGallery();
}
function openPreview(el){
  var p=_pathOf(el);
  if(p==null)return;
  var d=state.galleryDocs.find(function(x){return x.path===p||encodeURI(x.path)===p||x.path.replace(/\\/g,'/')===p.replace(/\\/g,'/')});
  if(!d&&el&&el.getAttribute){
    var nm=el.getAttribute('data-name')||p.split('/').pop()||p;
    d={path:p,name:nm,image_url:el.getAttribute('data-url')||('/images/'+p),
       size:el.getAttribute('data-size')||'',folder:el.getAttribute('data-folder')||'document',
       date:el.getAttribute('data-date')||'',kind:el.getAttribute('data-kind')||(/\.pdf$/i.test(p)?'pdf':'image')};
  }
  if(!d)return;
  var isPdf=(d.kind==='pdf')||/\.pdf$/i.test(d.name||'');
  var viewHtml=isPdf
    ?'<div class="preview-image"><iframe src="'+d.image_url+'" style="width:100%;height:100%;min-height:440px;border:none;background:#fff"></iframe></div>'
    :'<div class="preview-image"><img src="'+d.image_url+'" alt="'+d.name+'"></div>';
  document.getElementById('modal-title').textContent=d.name+' // INSPECTOR';
  document.getElementById('modal-body').innerHTML=
    '<div class="preview-grid">'+
    viewHtml+
    '<div class="preview-side">'+
    '<h4>PROPERTIES</h4>'+
    '<div class="preview-prop"><span class="label">FILENAME</span><span class="value">'+d.name+'</span></div>'+
    '<div class="preview-prop"><span class="label">CATEGORY</span><span class="value">'+d.folder+'</span></div>'+
    '<div class="preview-prop"><span class="label">SIZE</span><span class="value">'+d.size+'</span></div>'+
    '<div class="preview-prop"><span class="label">DATE</span><span class="value">'+d.date+'</span></div>'+
    '<div class="preview-prop"><span class="label">PATH</span><span class="value" style="font-size:0.5rem">'+d.path+'</span></div>'+
    '<h4 style="margin-top:14px">RENAME</h4>'+
    '<div style="display:flex;gap:6px"><input type="text" id="rn-input" value="'+d.name+'" style="flex:1;background:var(--bg-card);border:1px solid rgba(0,242,254,0.08);border-radius:var(--radius-sm);padding:6px 10px;color:var(--text-primary);font-family:var(--font-mono);font-size:0.55rem;outline:none">'+
    '<button class="btn btn-primary btn-sm" onclick="renameDoc(\''+d.path+'\')">SAVE</button></div>'+
    '<div class="preview-actions">'+
    '<button class="btn btn-primary" onclick="window.location.href=\''+d.image_url+'\'"><i class="lucide icon-download"></i> DOWNLOAD</button>'+
    '<button class="btn btn-outline" onclick="aiDocAction(\'summarize\',\''+d.path+'\')" title="AI summary of this document"><i class="lucide icon-sparkles"></i> AI SUMMARY</button>'+
    '<button class="btn btn-outline" onclick="aiDocAction(\'key_points\',\''+d.path+'\')" title="Extract key facts with AI"><i class="lucide icon-list"></i> KEY FACTS</button>'+
    '<button class="btn btn-outline" onclick="aiAskPrompt(\''+d.path+'\')" title="Ask the AI about this document"><i class="lucide icon-bot"></i> ASK AI</button>'+
    '<button class="btn btn-outline" onclick="var c=window.location.origin+\''+d.image_url+'\';navigator.clipboard.writeText(c).catch(function(){prompt(\'COPY:\',c)});toast(\'LINK COPIED\')"><i class="lucide icon-link"></i> SHARE</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'google_drive\')"><i class="lucide icon-cloud"></i> DRIVE</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'dropbox\')"><i class="lucide icon-cloudy"></i> DROPBOX</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'onedrive\')"><i class="lucide icon-cloud-download"></i> ONEDRIVE</button>'+
    '<button class="btn btn-danger" onclick="deleteDoc(\''+d.path+'\');closeModal()"><i class="lucide icon-trash-2"></i> DELETE</button>'+
    '<button class="btn btn-outline" onclick="closeModal()"><i class="lucide icon-x"></i> CLOSE</button></div></div></div>';
  document.getElementById('modal').classList.add('show');
}
function closeModal(){document.getElementById('modal').classList.remove('show')}
function renameDoc(p){
  var n=document.getElementById('rn-input').value.trim();
  if(!n){toast('ENTER A NAME','warn');return}
  fetch('/documents/'+p+'/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})})
    .then(function(r){return r.json()})
    .then(function(d){if(d.renamed){toast('RENAMED');closeModal();loadGallery();loadDashboard()}else toast('RENAME FAILED','err')})
    .catch(function(){toast('ERROR','err')});
}
function deleteDoc(el){
  var p=_pathOf(el);
  if(p==null)return;
  showConfirm('DELETE THIS DOCUMENT?',function(){_deleteDoc(p)});
}
function _deleteDoc(p){
  fetch('/documents/'+p,{method:'DELETE'}).then(function(r){return r.json()})
    .then(function(d){if(d.deleted){toast('DELETED');state.selectedDocs=state.selectedDocs.filter(function(x){return x!==p});loadGallery();loadDashboard()}else toast('DELETE FAILED','err')})
    .catch(function(){toast('ERROR','err')});
}

/* ---- PDF MERGE ---- */
function mergeToPdf(){
  if(state.selectedDocs.length<2){if(document.getElementById('view-gallery').classList.contains('active'))toast('SELECT 2+ DOCUMENTS TO MERGE','warn');return}
  showLoader('GENERATING PDF...','MERGING '+state.selectedDocs.length+' DOCUMENTS');
  fetch('/pdf/merge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:state.selectedDocs})})
    .then(function(r){return r.json()})
    .then(function(d){hideLoader();if(d.error){toast(d.error,'err');return}
      toast('PDF: '+d.name);
      state.selectedDocs=[];
      state.filter='merged';
      document.querySelectorAll('#filter-group button').forEach(function(b){b.classList.toggle('active',b.dataset.filter==='merged')});
      loadGallery();
      showMergeResult(d);
    })
    .catch(function(e){hideLoader();toast('PDF MERGE FAILED','err')});
}
function showMergeResult(d){
  if(!d||!d.url)return;
  var abs=window.location.origin+d.url;
  document.getElementById('modal-title').textContent=d.name+' // MERGED PDF';
  document.getElementById('modal-body').innerHTML=
    '<div class="preview-grid">'+
    '<div class="preview-image"><iframe src="'+d.url+'" style="width:100%;height:440px;border:none;border-radius:8px;background:#fff"></iframe></div>'+
    '<div class="preview-side">'+
    '<h4>MERGED PDF</h4>'+
    '<div class="preview-prop"><span class="label">FILENAME</span><span class="value">'+esc(d.name)+'</span></div>'+
    '<div class="preview-prop"><span class="label">SIZE</span><span class="value">'+esc(d.size||'--')+'</span></div>'+
    '<div class="preview-prop"><span class="label">FOLDER</span><span class="value">merged</span></div>'+
    '<h4 style="margin-top:14px">ACTIONS</h4>'+
    '<div class="preview-actions">'+
    '<button class="btn btn-primary" onclick="window.open(\''+d.url+'\',\'_blank\')"><i class="lucide icon-eye"></i> VIEW</button>'+
    '<button class="btn btn-outline" onclick="window.location.href=\''+d.url+'\'"><i class="lucide icon-download"></i> DOWNLOAD</button>'+
    '<button class="btn btn-outline" onclick="shareDoc(\''+esc(d.name)+'\',\''+d.url+'\')"><i class="lucide icon-share-2"></i> SHARE</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'google_drive\')"><i class="lucide icon-cloud"></i> DRIVE</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'dropbox\')"><i class="lucide icon-cloudy"></i> DROPBOX</button>'+
    '<button class="btn btn-outline" onclick="cloudUpload(\''+d.path+'\',\'onedrive\')"><i class="lucide icon-cloud-download"></i> ONEDRIVE</button>'+
    '<button class="btn btn-danger" onclick="deleteDoc(\''+d.path+'\');closeModal()"><i class="lucide icon-trash-2"></i> DELETE</button>'+
    '<button class="btn btn-outline" onclick="closeModal()"><i class="lucide icon-x"></i> CLOSE</button></div></div></div>';
  document.getElementById('modal').classList.add('show');
}
function shareDoc(name,url){
  var abs=window.location.origin+url;
  if(navigator.share){
    navigator.share({title:name||'Document',url:abs}).catch(function(){});
    return;
  }
  var nameE=encodeURIComponent(name||'Document');
  var textE=encodeURIComponent((name||'Document')+' - '+abs);
  var linkE=encodeURIComponent(abs);
  document.getElementById('modal-title').textContent='SHARE // '+name;
  document.getElementById('modal-body').innerHTML=
    '<div class="preview-grid"><div class="preview-side" style="max-width:100%">'+
    '<h4>SHARE OPTIONS</h4>'+
    '<div class="preview-actions">'+
    '<button class="btn btn-primary" onclick="window.open(\'https://wa.me/?text='+textE+'\',\'_blank\')"><i class="lucide icon-message-circle"></i> WHATSAPP</button>'+
    '<button class="btn btn-outline" onclick="window.open(\'https://t.me/share/url?url='+linkE+'&text='+nameE+'\',\'_blank\')"><i class="lucide icon-send"></i> TELEGRAM</button>'+
    '<button class="btn btn-outline" onclick="window.open(\'mailto:?subject='+nameE+'&body='+textE+'\')"><i class="lucide icon-mail"></i> EMAIL</button>'+
    '<button class="btn btn-outline" onclick="navigator.clipboard.writeText(\''+abs+'\').then(function(){toast(\'LINK COPIED\');closeModal()}).catch(function(){prompt(\'COPY LINK:\',\''+abs+'\')})"><i class="lucide icon-copy"></i> COPY LINK</button>'+
    '<button class="btn btn-outline" onclick="closeModal()"><i class="lucide icon-x"></i> CLOSE</button></div>'+
    '<div class="toggle-row" style="margin-top:10px"><span>LINK</span><span style="font-family:var(--font-mono);font-size:0.5rem;color:var(--text-tertiary);word-break:break-all">'+abs+'</span></div>'+
    '<p style="font-family:var(--font-classic);font-size:0.55rem;font-style:italic;color:var(--text-tertiary);margin-top:8px">Tip: for sharing outside this machine, upload to DRIVE / DROPBOX / ONEDRIVE first — those produce public links.</p>'+
    '</div></div>';
  document.getElementById('modal').classList.add('show');
}

/* ---- SEARCH ---- */
function doSearch(){
  var q=document.getElementById('search-input').value.trim();
  if(!q)return;
  fetch('/search?q='+encodeURIComponent(q)).then(function(r){return r.json()})
    .then(function(docs){
      switchView('gallery');
      state.galleryDocs=docs;state.filter='all';
      document.querySelectorAll('#filter-group button').forEach(function(b){b.classList.toggle('active',b.dataset.filter==='all')});
      renderGallery();toast('FOUND '+docs.length+' RESULT'+(docs.length!==1?'S':''));
    }).catch(function(){toast('SEARCH FAILED','err')});
}

/* ---- CLOUD ---- */
function loadCloudStatus(){
  fetch('/cloud/status').then(function(r){return r.json()}).then(function(d){
    var list=document.getElementById('cloud-status-list');
    var labels={google_drive:'GOOGLE DRIVE',dropbox:'DROPBOX',onedrive:'ONEDRIVE'};
    var icons={google_drive:'<i class="lucide icon-cloud"></i>',dropbox:'<i class="lucide icon-package"></i>',onedrive:'<i class="lucide icon-monitor"></i>'};
    list.innerHTML=Object.entries(d.providers).map(function(x){
      var k=x[0],v=x[1];
      var usageHtml='';
      if(v.connected) usageHtml='<span class="cloud-usage">'+((v.usage)||'0 KB')+'</span>';
      var folderBtn=v.connected?'<button class="btn btn-outline btn-xs" onclick="cloudFolder(\''+k+'\')" title="Open AI_Scanner folder"><i class="lucide icon-folder-open"></i> VIEW FOLDER</button>':'';
      return '<div class="toggle-row"><span>'+icons[k]+' '+labels[k]+'</span>'+
        '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end">'+
        usageHtml+folderBtn+
        (v.connected?'<span class="cloud-badge ok">CONFIGURED</span><button class="btn btn-outline btn-xs" onclick="cloudDisconnect(\''+k+'\')">DISCONNECT</button>'
        :v.configured?'<span class="cloud-badge warn">OFFLINE</span><button class="btn btn-primary btn-xs" onclick="cloudAuth(\''+k+'\')">CONNECT</button>'
        :'<span class="cloud-badge no">UNCONFIGURED</span><button class="btn btn-primary btn-xs" onclick="cloudAuth(\''+k+'\')"><i class="lucide icon-plug"></i> CONNECT</button>')+'</div></div>';
    }).join('');
  }).catch(function(){});
}
function cloudFolder(provider){
  fetch('/cloud/folder/'+provider).then(function(r){return r.json()}).then(function(d){
    if(d.url) window.open(d.url,'_blank');
    else toast('FOLDER NOT AVAILABLE','warn');
  }).catch(function(){toast('FOLDER LOOKUP FAILED','err')});
}
function cloudAuth(provider){
  fetch('/cloud/auth/'+provider).then(function(r){return r.json()}).then(function(d){
    if(d.connected){toast(labelsFor(provider)+' CONNECTED');loadCloudStatus();return}
    if(d.error){
      if(/not configured/i.test(d.error)){
        showConfirm(labelsFor(provider)+' NEEDS APP KEYS FIRST — ADD YOUR OWN CLIENT ID/SECRET IN API KEYS, THEN CONNECT',function(){switchView('settings')});
      }else{
        toast(d.error,'err');
      }
      return;
    }
    if(d.auth_url){
      window.open(d.auth_url,'_blank','width=600,height=700');
      if(provider==='google_drive'||provider==='onedrive'){
        toast('COMPLETE AUTHORIZATION IN THE POPUP...');
        var tries=0;
        var t=setInterval(function(){
          tries++;
          fetch('/cloud/status').then(function(r){return r.json()}).then(function(d2){
            if(d2.providers&&d2.providers[provider]&&d2.providers[provider].connected){
              clearInterval(t);toast(labelsFor(provider)+' CONNECTED');loadCloudStatus();
            }else if(tries>120){
              clearInterval(t);
              fetch('/cloud/status').then(function(r){return r.json()}).then(function(d2){
                var uri=(d2.providers&&d2.providers[provider]&&d2.providers[provider].redirect_uri)||'';
                if(provider==='google_drive'){
                  uri=uri||'http://localhost:5000/auth/google/callback';
                  showConfirm('GOOGLE BLOCKED THE LOGIN. OPEN https://console.cloud.google.com/apis/credentials -> EDIT YOUR OAUTH CLIENT -> AUTHORIZED REDIRECT URIs -> ADD EXACTLY:\n\n'+uri+'\n\n(NO trailing slash, port 5000. Save, then try CONNECT again.)',function(){loadCloudStatus()});
                }else if(provider==='onedrive'){
                  uri=uri||'http://localhost:5000/cloud/callback/onedrive';
                  showConfirm('ONEDRIVE BLOCKED THE LOGIN. OPEN https://portal.azure.com -> App registrations -> your app -> Authentication -> Web redirect URIs -> ADD EXACTLY:\n\n'+uri+'\n\nThen save and try CONNECT again.',function(){loadCloudStatus()});
                }else{
                  uri=uri||'http://localhost:5000/cloud/callback/dropbox';
                  showConfirm('DROPBOX BLOCKED THE LOGIN. OPEN https://www.dropbox.com/developers/apps -> your app -> Permissions -> Redirect URIs -> ADD EXACTLY:\n\n'+uri+'\n\nSave, then try CONNECT again.',function(){loadCloudStatus()});
                }
              }).catch(function(){loadCloudStatus()});
            }
          }).catch(function(){});
        },1500);
      }else{
        showPrompt('PASTE AUTHORIZATION CODE:',function(code){
          if(!code)return;
          fetch('/cloud/callback/'+provider+'?code='+encodeURIComponent(code))
            .then(function(r){
              if(r.ok){toast('CONNECTED');loadCloudStatus();}
              else{return r.json().then(function(d2){if(d2.error)toast(d2.error,'err')})}
            }).catch(function(){toast('ERROR','err')});
        });
      }
    }
  }).catch(function(e){toast('AUTH FAILED: '+e.message,'err')});
}
function labelsFor(p){return {google_drive:'GOOGLE DRIVE',dropbox:'DROPBOX',onedrive:'ONEDRIVE'}[p]||p.toUpperCase()}
function cloudDisconnect(provider){
  fetch('/cloud/disconnect/'+provider,{method:'POST'}).then(function(r){return r.json()})
    .then(function(d){if(d.disconnected){toast('DISCONNECTED');loadCloudStatus()}}).catch(function(){});
}
function cloudUpload(path,provider){
  fetch('/cloud/upload/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers:[provider]})})
    .then(function(r){return r.json()})
    .then(function(d){if(d.error){toast(d.error,'err');return}
      var link=Object.values(d.results||{})[0];
      if(link){toast('UPLOADED');showConfirm('OPEN IN CLOUD?',function(){window.open(link,'_blank')})}
      else toast('UPLOAD FAILED','err');
    }).catch(function(){toast('UPLOAD ERROR','err')});
}

/* ---- API KEYS ---- */
var KEY_META_UI={
  google_drive_client_id:{label:'GOOGLE DRIVE CLIENT ID',icon:'<i class="lucide icon-cloud"></i>'},
  google_drive_client_secret:{label:'GOOGLE DRIVE SECRET',icon:'<i class="lucide icon-cloud"></i>'},
  dropbox_app_key:{label:'DROPBOX APP KEY',icon:'<i class="lucide icon-package"></i>'},
  dropbox_app_secret:{label:'DROPBOX APP SECRET',icon:'<i class="lucide icon-package"></i>'},
  dropbox_access_token:{label:'DROPBOX ACCESS TOKEN',icon:'<i class="lucide icon-package"></i>'},
  onedrive_client_id:{label:'ONEDRIVE CLIENT ID',icon:'<i class="lucide icon-monitor"></i>'},
  onedrive_client_secret:{label:'ONEDRIVE SECRET',icon:'<i class="lucide icon-monitor"></i>'},
  onedrive_tenant_id:{label:'ONEDRIVE TENANT ID',icon:'<i class="lucide icon-monitor"></i>'},
  google_vision_api_key:{label:'GOOGLE VISION KEY',icon:'<i class="lucide icon-eye"></i>'},
  google_application_credentials:{label:'GOOGLE SERVICE ACCOUNT',icon:'<i class="lucide icon-eye"></i>'},
  ocr_space_api_key:{label:'OCR.SPACE API KEY (FREE)',icon:'<i class="lucide icon-file-text"></i>'},
  ocr_api_key:{label:'OCR API KEY (ocr-api.com)',icon:'<i class="lucide icon-file-text"></i>'},
  azure_vision_key:{label:'AZURE VISION KEY',icon:'<i class="lucide icon-file-text"></i>'},
  azure_vision_endpoint:{label:'AZURE VISION ENDPOINT',icon:'<i class="lucide icon-file-text"></i>'},
  groq_api_key:{label:'AI MODEL (GROQ)',icon:'<i class="lucide icon-sparkles"></i>'},
};
var KEY_SETUP_GUIDE=[
  {icon:'<i class="lucide icon-sparkles"></i>',label:'AI MODEL (GROQ)',keys:['groq_api_key'],
   get:'https://console.groq.com/keys',tip:'Powers AI chat for every visitor — free tier, no credit card. Set as Render env var GROQ_API_KEY for persistence'},
  {icon:'<i class="lucide icon-eye"></i>',label:'GOOGLE VISION OCR',keys:['google_vision_api_key'],
   get:'https://console.cloud.google.com/apis/credentials',tip:'Enables cloud OCR — enable the Cloud Vision API then create an API key'},
  {icon:'<i class="lucide icon-cloud"></i>',label:'GOOGLE DRIVE SYNC',keys:['google_drive_client_id','google_drive_client_secret'],
   get:'https://console.cloud.google.com/apis/credentials',tip:'Backup scans to your own Drive. Requires an OAUTH CLIENT ID + SECRET (or the credentials JSON) — an API key will NOT work here'},
  {icon:'<i class="lucide icon-package"></i>',label:'DROPBOX SYNC',keys:['dropbox_app_key','dropbox_app_secret'],
   get:'https://www.dropbox.com/developers/apps',tip:'Create an app in the Dropbox Developer Console for full access'},
  {icon:'<i class="lucide icon-monitor"></i>',label:'ONEDRIVE SYNC',keys:['onedrive_client_id','onedrive_client_secret','onedrive_tenant_id'],
   get:'https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps',tip:'Register an app in Azure → add client ID, secret & tenant'},
  {icon:'<i class="lucide icon-file-text"></i>',label:'OCR.SPACE (FREE FALLBACK)',keys:['ocr_space_api_key'],
   get:'https://ocr.space/ocrapi',tip:'Free OCR tier — grab a key at ocr.space/ocrapi'},
  {icon:'<i class="lucide icon-sparkles"></i>',label:'AZURE VISION OCR',keys:['azure_vision_key','azure_vision_endpoint'],
   get:'https://portal.azure.com/#create/microsoft.cognitiveservices',tip:'Optional AI OCR — create an Azure Computer Vision resource & copy Key/Endpoint'},
];
function renderKeySetupGuide(keys){
  var el=document.getElementById('setup-key-guide');
  if(!el)return;
  var have={};
  (keys||[]).forEach(function(k){have[k.name]=k.configured});
  el.innerHTML=KEY_SETUP_GUIDE.map(function(g){
    var missing=g.keys.filter(function(k){return !have[k]});
    var done=!missing.length;
    var badge=done
      ?'<span class="cloud-badge ok">CONFIGURED</span>'
      :'<span class="cloud-badge warn">'+missing.length+' KEY'+(missing.length>1?'S':'')+' MISSING</span>';
    var selKey=done?g.keys[0]:(missing[0]||g.keys[0]);
    var addBtn=done
      ?'<button class="btn btn-outline btn-xs" style="font-size:0.48rem;padding:4px 7px" onclick="showAddKeyForm('+JSON.stringify(selKey)+')"><i class="lucide icon-edit"></i> UPDATE</button>'
      :'<button class="btn btn-primary btn-xs" style="font-size:0.48rem;padding:4px 7px" onclick="showAddKeyForm('+JSON.stringify(selKey)+')"><i class="lucide icon-plus"></i> ADD</button>';
    return '<div class="toggle-row" style="align-items:flex-start">'+
      '<span style="display:flex;flex-direction:column;gap:2px"><span>'+g.icon+' '+g.label+'</span>'+
      '<span style="font-family:var(--font-mono);font-size:0.45rem;color:var(--text-tertiary);font-weight:400">'+g.tip+'</span></span>'+
      '<div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap">'+badge+
      '<a href="'+g.get+'" target="_blank" rel="noopener" class="btn btn-outline btn-xs" style="font-size:0.48rem;padding:4px 7px"><i class="lucide icon-external-link"></i> GET KEY</a>'+
      addBtn+
      '</div></div>';
  }).join('');
}
function maskForDisplay(m){
  m=m||'****';
  if(m.length>34)return m.slice(0,8)+'…'+m.slice(-4);
  return m;
}
function loadApiKeys(){
  fetch('/api/keys').then(function(r){return r.json()}).then(function(keys){
    renderKeySetupGuide(keys);
    var list=document.getElementById('api-keys-list');
    var configured=keys.filter(function(k){return k.configured});
    if(!configured.length){list.innerHTML='';return}
    list.innerHTML=configured.map(function(k){
      return '<div class="toggle-row"><span style="flex:1;min-width:0;white-space:normal">'+KEY_META_UI[k.name]?.icon+' '+KEY_META_UI[k.name]?.label+'</span>'+
        '<div style="display:flex;gap:6px;align-items:center;min-width:0;max-width:100%;flex-wrap:wrap"><code class="code" style="max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+(k.masked_value||'')+'">'+(k.configured?maskForDisplay(k.masked_value):'****')+'</code>'+
        '<button class="btn btn-danger btn-xs" onclick="deleteApiKey(\''+k.name+'\')" style="padding:1px 6px;flex-shrink:0"><i class="lucide icon-x"></i></button></div></div>';
    }).join('');
  }).catch(function(){});
}
function showAddKeyForm(preselect){
  var sel=document.getElementById('ak-service');sel.innerHTML='';
  Object.entries(KEY_META_UI).forEach(function(x){
    var opt=document.createElement('option');opt.value=x[0];
    opt.textContent=x[1].icon+' '+x[1].label;sel.appendChild(opt);
  });
  if(preselect&&KEY_META_UI[preselect])sel.value=preselect;
  document.getElementById('ak-value').value='';
  var form=document.getElementById('api-key-form');
  form.style.display='block';
  document.getElementById('btn-add-key').style.display='none';
  form.scrollIntoView({behavior:'smooth',block:'nearest'});
  sel.focus();
}
function saveApiKey(){
  var name=document.getElementById('ak-service').value;
  var value=document.getElementById('ak-value').value.trim();
  if(!value){toast('ENTER A KEY','warn');return}
  fetch('/api/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,value:value})})
    .then(function(r){return r.json()})
    .then(function(d){if(d.error){toast(d.error,'err');return}
      toast('KEY SAVED');
      document.getElementById('api-key-form').style.display='none';
      document.getElementById('btn-add-key').style.display='';
      loadApiKeys();loadCloudStatus();
    }).catch(function(){toast('ERROR SAVING KEY','err')});
}
function deleteApiKey(name){
  showConfirm('DELETE '+KEY_META_UI[name]?.label+'?',function(){_deleteApiKey(name)});return;
}
function _deleteApiKey(name){
  fetch('/api/keys/'+name,{method:'DELETE'}).then(function(r){return r.json()})
    .then(function(d){if(d.deleted){toast('KEY DELETED');loadApiKeys();loadCloudStatus()}else toast('DELETE FAILED','err')})
    .catch(function(){toast('ERROR','err')});
}

/* ---- SETTINGS ---- */
function loadSettings(){
  fetch('/stats').then(function(r){return r.json()}).then(function(s){
    document.getElementById('set-count').textContent=s.total+' DOCUMENTS';
    document.getElementById('set-size').textContent=s.total_size;
  }).catch(function(){});
  fetch('/api/storage/path').then(function(r){return r.json()}).then(function(d){
    document.getElementById('storage-path-display').textContent=d.path||'data/documents/';
  }).catch(function(){});
  loadCloudStatus();loadApiKeys();
}
function browseStorageFolder(){
  // Try modern File System Access API first
  if('showDirectoryPicker' in window){
    window.showDirectoryPicker().then(function(dir){
      var path=dir.name;
      document.getElementById('storage-path-display').textContent=path;
      saveStoragePathToBackend(path);
    }).catch(function(err){
      if(err.name!='AbortError') fallbackFolderPicker();
    });
  }else{
    fallbackFolderPicker();
  }
}
function fallbackFolderPicker(){
  document.getElementById('folder-picker').click();
}
function handleFolderPick(input){
  if(input.files&&input.files.length){
    var path=input.files[0].webkitRelativePath.split('/')[0];
    var fullPath=input.files[0].path || input.files[0].webkitRelativePath;
    // Try to extract a reasonable parent path
    var idx=fullPath.indexOf(path);
    var parentPath=idx>=0?fullPath.substring(0,idx)+path:path;
    document.getElementById('storage-path-display').textContent=parentPath||path;
    saveStoragePathToBackend(parentPath||path);
  }
  input.value='';
}
function saveStoragePathToBackend(path){
  fetch('/api/storage/path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path})})
    .then(function(r){return r.json()}).then(function(d){
      if(d.saved){toast('Storage path: '+path);loadSettings()}
      else toast('Failed to save path','err');
    }).catch(function(){toast('Error saving path','err')});
}

/* ---- SEARCH INPUT ---- */
document.getElementById('search-input').addEventListener('keydown',function(e){if(e.key==='Enter')doSearch()});

/* ---- UTILS ---- */
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
function toggleSidebar(){document.getElementById('sidebar').classList.toggle('open');document.getElementById('sidebar-overlay').classList.toggle('show')}
function closeSidebar(){document.getElementById('sidebar').classList.remove('open');document.getElementById('sidebar-overlay').classList.remove('show')}

/* ---- OCR STATUS ---- */
function loadOcrStatus(){
  fetch('/api/ocr/status').then(function(r){return r.json()}).then(function(s){
    var badge=document.getElementById('ocr-status-badge');
    var eng;
    if(s.tesseract){eng='TESSERACT';badge.innerHTML='<span style="color:var(--emerald)"><i class="lucide icon-check" style="font-size:0.6em"></i> Tesseract</span>';}
    else if(s.google_vision){eng='GOOGLE VISION';badge.innerHTML='<span style="color:var(--gold)"><i class="lucide icon-check" style="font-size:0.6em"></i> Google Vision</span>';}
    else {eng='NONE';badge.innerHTML='<span style="color:var(--crimson)"><i class="lucide icon-x" style="font-size:0.6em"></i> Not available</span>';}
    var sb=document.getElementById('sb-ocr');if(sb)sb.textContent=eng;
  }).catch(function(){
    document.getElementById('ocr-status-badge').innerHTML='<span style="color:var(--crimson)"><i class="lucide icon-x" style="font-size:0.6em"></i> Error</span>';
    var sb=document.getElementById('sb-ocr');if(sb)sb.textContent='ERROR';
  });
}

/* ---- REAL-TIME POLLING (reduced on mobile) ---- */
var realtimeIntervals=[];
var isTouchDevice='ontouchstart' in window||navigator.maxTouchPoints>0;
var pollInterval=isTouchDevice?30000:8000;
realtimeIntervals.push(setInterval(function(){
  if(document.getElementById('view-dashboard').classList.contains('active')){
    loadDashboard();loadActivity();
  }
}, pollInterval));
realtimeIntervals.push(setInterval(function(){
  if(document.getElementById('view-gallery').classList.contains('active')){
    loadGallery();
  }
}, isTouchDevice?40000:12000));
realtimeIntervals.push(setInterval(function(){
  if(document.getElementById('view-settings').classList.contains('active')){
    loadCloudStatus();
  }
}, pollInterval));

/* ---- KEYBOARD SHORTCUTS ---- */
document.addEventListener('keydown',function(e){
  if(e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key==='Escape'){
    if(document.getElementById('modal').classList.contains('show')){closeModal();e.preventDefault()}
    else if(document.getElementById('loader').classList.contains('show')){hideLoader()}
    else if(state.stream){document.getElementById('btn-close-cam').click();e.preventDefault()}
    else if(state.stream){closeCamera();e.preventDefault()}
    else if(document.getElementById('scan-preview').classList.contains('active')){resetScanner();e.preventDefault()}
    else if(state.currentView!=='dashboard'){goBack();e.preventDefault()}
  }
  if(e.key==='Enter'){
    if(document.getElementById('view-scanner').classList.contains('active')&&!document.getElementById('btn-process').disabled)
      document.getElementById('btn-process').click();
  }
  var navMap={'1':'dashboard','2':'scanner','3':'gallery','4':'ai','5':'settings'};
  if(e.key in navMap&&document.getElementById('view-'+navMap[e.key])){
    switchView(navMap[e.key]);e.preventDefault();
  }
});

/* ---- MOUSE TRACKING (disabled on touch) ---- */
var mg=document.getElementById('mouse-glow'),mgTimer;
if(!isTouchDevice){
  document.addEventListener('mousemove',function(e){
    mg.style.left=e.clientX+'px';mg.style.top=e.clientY+'px';
    mg.classList.add('show');
    clearTimeout(mgTimer);
    mgTimer=setTimeout(function(){mg.classList.remove('show')},3000);
  });
}else{mg.style.display='none'}

/* ---- KEYBOARD HINT AUTO-HIDE ---- */
setTimeout(function(){
  var kh=document.getElementById('kbd-hint');
  if(kh)kh.style.opacity='0.15';
},10000);

/* ---- QUICK LOGIN SESSION ---- */
function getSessionCookie(name){
  var m=document.cookie.match(new RegExp('(?:^|; )'+name+'=([^;]*)'));
  return m?decodeURIComponent(m[1]):'';
}
function applySession(){
  var name=getSessionCookie('user_name');
  if(!name){window.location.href='/login';return}
  var mode=getSessionCookie('user_mode');
  var label=document.getElementById('user-name');
  if(label)label.textContent=name;
  var role=document.querySelector('.info .role');
  if(role)role.textContent=(mode==='guest')?'GUEST VISITOR // TEMP ID':(mode==='register'?'REGISTERED // ARCHIVE KEEPER':'ARCHIVE KEEPER');
  document.title='AI SCANNER // '+name.toUpperCase();
  var av=document.getElementById('avatar-img');
  if(av){
    av.onerror=function(){av.onerror=null;av.src='/static/images/logo.svg'};
    av.src='/api/profile/avatar?t='+Date.now();
  }
}
function uploadAvatar(input){
  var f=input.files&&input.files[0];
  if(!f)return;
  if(!/^image\//.test(f.type)){toast('IMAGE ONLY','warn');return}
  var fd=new FormData();
  fd.append('avatar',f);
  showLoader('UPLOADING...','SETTING PROFILE PICTURE');
  fetch('/api/profile/avatar',{method:'POST',body:fd}).then(function(r){return r.json()})
    .then(function(d){
      hideLoader();
      if(d.error){toast(d.error,'err');return}
      var av=document.getElementById('avatar-img');
      if(av)av.src='/api/profile/avatar?t='+Date.now();
      toast('PROFILE PICTURE UPDATED');
    }).catch(function(){hideLoader();toast('UPLOAD FAILED','err')});
  input.value='';
}
function logoutSession(){
  showConfirm('EXIT THE ARCHIVE?',function(){
    fetch('/api/logout',{method:'POST'}).catch(function(){}).finally(function(){
      window.location.href='/login';
    });
  });
}

/* ---- BLUETOOTH CAMERA ---- */
var bluetoothScanTimer=null;
/* ---- BLUETOOTH CAMERA (QR-FIRST PAIRING) ---- */
var bluetoothSelectedDevice=null;
var bluetoothSessionToken=null;
var bluetoothPollTimer=null;
var bluetoothLiveTimer=null;

function openBluetoothPanel(){
  // Show the QR pairing popup
  var modal=document.getElementById('bluetooth-modal');
  if(modal)modal.classList.add('show');
  regenerateBluetoothQR();
}

function closeBluetoothModal(){
  var modal=document.getElementById('bluetooth-modal');
  if(modal)modal.classList.remove('show');
  // Leaving the popup also stops the live view on the device
  stopBluetoothPolling();
  stopBluetoothLive();
  stopBluetoothScan();
}

function setBtStatus(msg,color){
  var el=document.getElementById('bt-status-text');
  if(el){
    el.textContent=msg;
    el.style.color=color||'var(--text-secondary)';
  }
}

function regenerateBluetoothQR(){
  var qrImg=document.getElementById('bt-qr-img');
  var qrLoading=document.getElementById('bt-qr-loading');
  var qrMeta=document.getElementById('bt-qr-meta');
  if(qrImg)qrImg.style.display='none';
  if(qrLoading)qrLoading.style.display='block';
  if(qrMeta)qrMeta.style.display='none';
  setBtStatus('Generating pairing code...','var(--gold)');

  stopBluetoothPolling();
  stopBluetoothLive();

  fetch('/api/bluetooth/pairing',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    width:640,height:480,quality:85,auto_capture:true,interval:2
  })})
    .then(function(r){return r.json()})
    .then(function(data){
      if(data.error){
        setBtStatus('FAILED: '+data.error,'var(--crimson)');
        if(qrLoading)qrLoading.innerHTML='<span style="color:var(--crimson)">'+esc(data.error)+'</span>';
        return;
      }
      bluetoothSessionToken=data.token;
      var pidEl=document.getElementById('bt-pair-id');
      var expEl=document.getElementById('bt-qr-expiry');
      if(pidEl)pidEl.textContent=data.pairing_id;
      if(expEl)expEl.textContent=Math.floor(data.expires_in/60)+' min';
      if(qrImg){qrImg.src=data.qr_code;qrImg.style.display='block'}
      if(qrLoading)qrLoading.style.display='none';
      if(qrMeta)qrMeta.style.display='block';
      setBtStatus('Waiting for device to scan the code...','var(--emerald)');
      startBluetoothPolling();
    })
    .catch(function(e){
      setBtStatus('QR ERROR: '+e.message,'var(--crimson)');
      if(qrLoading)qrLoading.innerHTML='<span style="color:var(--crimson)">'+esc(e.message)+'</span>';
    });
}

function startBluetoothPolling(){
  stopBluetoothPolling();
  bluetoothPollTimer=setInterval(function(){
    if(!bluetoothSessionToken)return;
    fetch('/api/bluetooth/pairing/'+bluetoothSessionToken)
      .then(function(r){return r.json()})
      .then(function(data){
        if(data.error){
          setBtStatus(data.error,'var(--crimson)');
          stopBluetoothPolling();
          return;
        }
        var pairStep=document.getElementById('bt-pair-step');
        var connectedState=document.getElementById('bt-connected-state');
        if(data.connected){
          if(pairStep)pairStep.style.display='none';
          if(connectedState)connectedState.style.display='block';
          var nameEl=document.getElementById('bt-connected-name');
          var idEl=document.getElementById('bt-connected-id');
          if(nameEl)nameEl.textContent=data.device_name||'Bluetooth device';
          if(idEl)idEl.textContent=data.pairing_id;
          setBtStatus('Connected to '+data.device_name+' — showing live feed','var(--emerald)');
          stopBluetoothPolling();
          showBtLiveFeed();
        }else{
          setBtStatus('Waiting for device to scan the code... (expires in '+data.expires_in+'s)','var(--emerald)');
        }
      })
      .catch(function(){});
  },2000);
}

function stopBluetoothPolling(){
  if(bluetoothPollTimer){clearInterval(bluetoothPollTimer);bluetoothPollTimer=null}
}

function showBtLiveFeed(){
  var feed=document.getElementById('bt-live-feed');
  if(!feed)return;
  feed.style.display='block';
  var nameEl=document.getElementById('bt-live-name');
  if(nameEl)nameEl.textContent=bluetoothSessionToken?('paired'):'device';
  stopBluetoothLive();
  bluetoothLiveTimer=setInterval(function(){
    if(!bluetoothSessionToken)return;
    fetch('/api/bluetooth/pairing/'+bluetoothSessionToken+'/frame')
      .then(function(r){return r.json()})
      .then(function(data){
        var img=document.getElementById('bt-live-img');
        if(data && data.image && img){
          img.src=data.image;
          var nm=document.getElementById('bt-live-name');
          if(nm && data.device_name)nm.textContent=data.device_name;
        }
      })
      .catch(function(){});
  },400);
}

function stopBluetoothLive(){
  if(bluetoothLiveTimer){clearInterval(bluetoothLiveTimer);bluetoothLiveTimer=null}
  var feed=document.getElementById('bt-live-feed');
  if(feed)feed.style.display='none';
}

function toggleBtAdvanced(){
  var adv=document.getElementById('bt-advanced');
  if(adv){
    var show=adv.style.display==='none';
    adv.style.display=show?'block':'none';
  }
}

function stopBtCamera(){
  // Tell the device to close its camera app, then hide the live view
  if(bluetoothSessionToken){
    fetch('/api/bluetooth/pairing/'+bluetoothSessionToken+'/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:'stop'})})
      .catch(function(){});
  }
  stopBluetoothLive();
  toast('DEVICE CAMERA CLOSED');
  setBtStatus('Device camera closed — scan again to reconnect','var(--gold)');
}

function captureBluetoothFrame(){
  if(!bluetoothSessionToken){
    toast('NO DEVICE PAIRED','warn');
    return;
  }
  showLoader('CAPTURING...','REQUESTING FRAME FROM BLUETOOTH CAMERA');
  fetch('/api/bluetooth/pairing/'+bluetoothSessionToken+'/frame')
    .then(function(r){return r.json()})
    .then(function(data){
      hideLoader();
      if(data.error){
        toast('CAPTURE FAILED: '+data.error,'err');
        return;
      }
      if(!data.image){
        toast('NO FRAME YET — IS THE DEVICE SENDING?','warn');
        return;
      }
      handleBluetoothImage(data.image);
      toast('CAPTURED FROM BLUETOOTH CAMERA');
    })
    .catch(function(e){
      hideLoader();
      toast('CAPTURE ERROR: '+e.message,'err');
    });
}

function disconnectBluetooth(){
  // Closing the connection must also close the camera app on the device
  if(bluetoothSessionToken){
    fetch('/api/bluetooth/pairing/'+bluetoothSessionToken+'/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:'stop'})})
      .then(function(){
        return fetch('/api/bluetooth/pairing/'+bluetoothSessionToken,{method:'DELETE'});
      })
      .catch(function(){
        fetch('/api/bluetooth/pairing/'+bluetoothSessionToken,{method:'DELETE'}).catch(function(){});
      });
  }
  bluetoothSessionToken=null;
  bluetoothSelectedDevice=null;
  stopBluetoothPolling();
  stopBluetoothLive();

  var connectedState=document.getElementById('bt-connected-state');
  var pairStep=document.getElementById('bt-pair-step');
  if(connectedState)connectedState.style.display='none';
  if(pairStep)pairStep.style.display='block';
  setBtStatus('Disconnected');
  toast('DISCONNECTED');
}

function scanBluetoothDevices(){
  var btn=document.getElementById('btn-bt-scan');
  var stopBtn=document.getElementById('btn-bt-stop-scan');
  var devicesEl=document.getElementById('bluetooth-devices');
  
  if(btn)btn.style.display='none';
  if(stopBtn)stopBtn.style.display='';
  if(devicesEl)devicesEl.innerHTML='<div style="padding:12px;text-align:center;color:var(--gold)"><i class="lucide icon-loader" style="animation:spin 1s linear infinite"></i> Scanning...</div>';
  
  fetch('/api/bluetooth/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({duration:10})})
    .then(function(r){return r.json()})
    .then(function(data){
      if(btn)btn.style.display='';
      if(stopBtn)stopBtn.style.display='none';
      
      if(data.error){
        if(devicesEl)devicesEl.innerHTML='<div style="padding:12px;text-align:center;color:var(--crimson)">Error: '+data.error+'</div>';
        toast('SCAN FAILED: '+data.error,'err');
        return;
      }
      
      var devices=data.devices||[];
      if(devices.length===0){
        if(devicesEl)devicesEl.innerHTML='<div style="padding:12px;text-align:center;color:var(--text-tertiary);font-family:var(--font-classic);font-size:0.65rem;font-style:italic">No Bluetooth cameras found</div>';
        toast('NO DEVICES FOUND');
        return;
      }
      
      if(devicesEl){
        devicesEl.innerHTML=devices.map(function(d){
          var isCamera=d.is_camera;
          return '<div class="bt-device" data-address="'+d.address+'" data-name="'+esc(d.name)+'" onclick="selectBluetoothDevice(this)" style="padding:10px;border-bottom:1px solid rgba(201,169,110,0.05);cursor:pointer;display:flex;align-items:center;gap:8px">'+
            '<i class="lucide '+(isCamera?'icon-camera':'icon-bluetooth')+'" style="color:'+(isCamera?'var(--emerald)':'var(--gold)')+';font-size:1.2rem"></i>'+
            '<div style="flex:1">'+
              '<div style="font-family:var(--font-mono);font-size:0.55rem;font-weight:600">'+esc(d.name)+'</div>'+
              '<div style="font-family:var(--font-mono);font-size:0.45rem;color:var(--text-tertiary)">'+d.address+' | RSSI: '+d.rssi+'dBm'+(d.battery!==null?' | Battery: '+d.battery+'%':'')+'</div>'+
              '<div style="font-family:var(--font-mono);font-size:0.4rem;color:var(--text-tertiary)">'+(d.services&&d.services.length?'Services: '+d.services.slice(0,3).join(', '):'')+'</div>'+
            '</div>'+
            '<span class="badge '+(isCamera?'badge-green':'badge-gray')+'" style="font-size:0.45rem">'+(isCamera?'CAMERA':'DEVICE')+'</span>'+
          '</div>';
        }).join('');
      }
      toast('FOUND '+devices.length+' DEVICE(S)');
    })
    .catch(function(e){
      if(btn)btn.style.display='';
      if(stopBtn)stopBtn.style.display='none';
      if(devicesEl)devicesEl.innerHTML='<div style="padding:12px;text-align:center;color:var(--crimson)">Error: '+e.message+'</div>';
      toast('SCAN ERROR: '+e.message,'err');
    });
}

function stopBluetoothScan(){
  var btn=document.getElementById('btn-bt-scan');
  var stopBtn=document.getElementById('btn-bt-stop-scan');
  if(btn)btn.style.display='';
  if(stopBtn)stopBtn.style.display='none';
}

function selectBluetoothDevice(el){
  document.querySelectorAll('.bt-device').forEach(function(d){d.classList.remove('selected')});
  el.classList.add('selected');
  bluetoothSelectedDevice={
    address:el.dataset.address,
    name:el.dataset.name
  };
  toast('SELECTED: '+bluetoothSelectedDevice.name);
}

function handleBluetoothImage(dataUrl){
  var img=new Image();
  img.onload=function(){
    var canvas=document.createElement('canvas');
    canvas.width=img.width;
    canvas.height=img.height;
    canvas.getContext('2d').drawImage(img,0,0);
    canvas.toBlob(function(blob){
      state.capturedBlobs.push(blob);
      state.capturedBlob=blob;
      addFilmstripThumb(blob,state.capturedBlobs.length);
      document.getElementById('dz-placeholder').style.display='none';
      document.getElementById('btn-process').disabled=false;
      document.getElementById('done-bar').style.display='flex';
      document.getElementById('done-bar').classList.add('origin');
      updateBatch();
    },'image/jpeg',0.85);
  };
  img.src=dataUrl;
}

/* ---- AI ASSISTANT (free local models, no API keys) ---- */
var aiState={history:[],booted:false,contextDoc:null,autoSummarize:false};
function loadAiStatus(force){
  fetch('/api/ai/status'+(force?'?refresh=1':'')).then(function(r){return r.json()}).then(function(s){
    var sb=document.getElementById('sb-ai');
    var badge=document.getElementById('ai-engine-badge');
    var det=document.getElementById('ai-engine-detail');
    var setEng=document.getElementById('set-ai-engine');
    var dashEng=document.getElementById('dash-ai-engine');
    var eng=s.engine||'builtin';
    var label=eng==='ollama'?'OLLAMA':eng==='transformer'?'FLAN-T5':'BASIC';
    if(sb){
      if(eng==='ollama'){sb.innerHTML='<span style="color:var(--emerald)">OLLAMA</span>'}
      else if(eng==='transformer'){sb.innerHTML='<span style="color:var(--gold)">FLAN-T5</span>'}
      else{sb.innerHTML='<span style="color:var(--gold)">BASIC</span>'}
    }
    if(setEng)setEng.textContent=label+(s.model?' · '+s.model:'');
    if(dashEng)dashEng.textContent=label;
    if(badge){
      var cls=eng==='ollama'?'ok':eng==='transformer'?'mid':'basic';
      badge.className='ai-engine-badge '+cls;
      badge.innerHTML='<span class="dot on"></span> '+(s.detail||'BUILT-IN HELPER').toUpperCase();
    }
    if(det){
      var h='<div>ENGINE <span style="color:var(--gold)">'+eng.toUpperCase()+'</span></div>';
      if(s.model)h+='<div>MODEL <span style="color:var(--emerald)">'+esc(s.model)+'</span></div>';
      if(s.ollama&&s.ollama.installed){
        h+='<div style="margin-top:4px;color:var(--emerald)">Ollama running · '+s.ollama.models.length+' model(s)</div>';
      }else{
        h+='<div style="margin-top:4px">Ollama: not detected</div>';
        h+='<div>Transformers pkg: '+(s.transformer&&s.transformer.package?'<span style="color:var(--emerald)">yes</span>':'no')+'</div>';
        h+='<div>'+esc(s.transformer&&s.transformer.downloaded?'flan-t5 cached locally':'flan-t5 downloads once (~300 MB), then offline')+'</div>';
      }
      det.innerHTML=h;
    }
    if(s.config&&typeof s.config.auto_summarize!=='undefined'){
      var tg=document.getElementById('tog-ai-auto');
      if(tg)tg.classList.toggle('on',!!s.config.auto_summarize);
      aiState.autoSummarize=!!s.config.auto_summarize;
    }
  }).catch(function(){
    var sb=document.getElementById('sb-ai');if(sb)sb.textContent='ERROR';
    var b=document.getElementById('ai-engine-badge');if(b)b.innerHTML='STATUS ERROR';
  });
}
function ensureAiView(){
  if(!aiState.booted){
    aiState.booted=true;
    loadAiStatus();
    aiBubble('assistant',"Hello! I'm your local AI assistant — free, open-source and fully offline. I can summarize documents, answer questions about their content, or explain any scanner feature.\n\nTry a quick action below, or ask me something!");
    var inp=document.getElementById('ai-input');
    if(inp&&!inp._bound){inp._bound=true;inp.addEventListener('keydown',function(e){if(e.key==='Enter')aiSend()})}
  }
}
function aiBubble(role,text,meta){
  var wrap=document.getElementById('ai-msgs');
  if(!wrap)return;
  var el=document.createElement('div');
  el.className='ai-msg '+(role==='user'?'user':'bot');
  var ic=role==='user'?'icon-user':'icon-bot';
  el.innerHTML='<span class="ai-msg-ic"><i class="lucide '+ic+'"></i></span>'+
    '<div class="ai-msg-body">'+aesc(text).replace(/\n/g,'<br>')+
    (meta?'<div class="ai-msg-meta">'+aesc(meta)+'</div>':'')+'</div>';
  wrap.appendChild(el);
  wrap.scrollTop=wrap.scrollHeight;
}
function aiTyping(on){
  var wrap=document.getElementById('ai-msgs');
  if(!wrap)return;
  var t=document.getElementById('ai-typing');
  if(on){
    if(!t){
      t=document.createElement('div');
      t.id='ai-typing';t.className='ai-msg bot';
      t.innerHTML='<span class="ai-msg-ic"><i class="lucide icon-bot"></i></span><div class="ai-msg-body"><span class="ai-dot"></span><span class="ai-dot"></span><span class="ai-dot"></span></div>';
      wrap.appendChild(t);
    }
    wrap.scrollTop=wrap.scrollHeight;
  }else if(t)t.remove();
}
function aiClearChat(){
  aiState.history=[];
  var m=document.getElementById('ai-msgs');
  if(m)m.innerHTML='';
  aiBubble('assistant','Conversation cleared. What can I help you with?');
}
/* AI fetch with cold-start wait: free tiers (Render) sleep after ~15 min idle
   and this container is heavy (torch+OpenCV imports), so a cold boot can take
   30-60s+. Poll a lightweight endpoint until the server answers (max ~90s),
   then fire the real request. */
function aiWaitServer(deadline,cb){
  fetch('/api/session').then(function(r){
    if(r.ok){cb(true);return}
    throw new Error('warming');
  }).catch(function(){
    if(Date.now()<deadline){
      toast('SERVER WAKING UP (FREE TIER COLD START)...','warn');
      setTimeout(function(){aiWaitServer(deadline,cb)},5000);
    }else{
      cb(false);
    }
  });
}
function aiFetchRetry(url,opts,onDone,onFail){
  aiWaitServer(Date.now()+90000,function(up){
    if(!up){onFail();return}
    fetch(url,opts).then(function(r){return r.json()}).then(onDone).catch(onFail);
  });
}
function aiSend(presetText){
  var inp=document.getElementById('ai-input');
  var text=(presetText||inp.value||'').trim();
  if(!text)return;
  inp.value='';
  ensureAiView();
  aiBubble('user',text);
  aiTyping(true);
  var payload={message:text,history:aiState.history.slice(-6)};
  if(aiState.contextDoc&&aiState.contextDoc.path)payload.doc_path=aiState.contextDoc.path;
  aiFetchRetry('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)},function(d){
      aiTyping(false);
      var reply=d.reply||'No reply.';
      aiState.history.push({role:'user',content:text});
      aiState.history.push({role:'assistant',content:reply});
      var meta='engine: '+d.engine+(d.model?' · '+d.model:'');
      if(d.grounded)meta+=' · ✓ verified from your vault';
      aiBubble('assistant',reply,meta);
    },function(){
      aiTyping(false);
      aiBubble('assistant','Connection error — the server may be waking up or restarting. Wait ~1 minute and try again.');
    });
}
function _aiDocRequest(action,path,question){
  ensureAiView();
  switchView('ai');
  aiState.contextDoc={path:path};
  var body={action:action,doc_path:path};
  if(question)body.question=question;
  aiTyping(true);
  return new Promise(function(resolve){
    aiFetchRetry('/api/ai/document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},function(d){
      aiTyping(false);
      if(!d||d.error){aiBubble('assistant',(d&&d.error)||'AI request failed.');resolve(null);return}
      var label=action==='ask'?'Answer about "'+path.split('/').pop()+'"':
                action==='key_points'?'Key facts from "'+path.split('/').pop()+'"':
                'Summary of "'+path.split('/').pop()+'"';
      aiState.history.push({role:'user',content:label});
      aiState.history.push({role:'assistant',content:d.reply});
      aiBubble('assistant',label+':\n'+d.reply,'engine: '+d.engine);
      resolve(d);
    },function(){
      aiTyping(false);
      aiBubble('assistant','Connection error — the server may be waking up. Try again in ~1 minute.');
      resolve(null);
    });
  });
}
function aiDocAction(action,path){_aiDocRequest(action,path)}
function aiAskPrompt(path){
  showPrompt('ASK AI — YOUR QUESTION ABOUT THIS DOCUMENT:',function(q){
    if(q)_aiDocRequest('ask',path,q);
  });
}
function _lastDocPath(){
  if(state.lastDocPath)return state.lastDocPath;
  return null;
}
function aiQuickSummarize(){
  var p=_lastDocPath();
  if(!p){toast('NO SCANS YET — PROCESS A DOCUMENT FIRST','warn');return}
  _aiDocRequest('summarize',p);
}
function aiAskLastDoc(){
  var p=_lastDocPath();
  if(!p){toast('NO SCANS YET — PROCESS A DOCUMENT FIRST','warn');return}
  aiAskPrompt(p);
}
function aiFromResult(){
  if(!state.currentResult||!(state.currentResult.ocr&&state.currentResult.ocr.text)){toast('NO OCR TEXT TO ASK ABOUT','warn');return}
  switchView('ai');ensureAiView();
  var p=_lastDocPath();
  if(p)_aiDocRequest('summarize',p);
  else{aiBubble('assistant','I see the last scan has text but was not saved yet. Press SAVE TO VAULT first, then I can summarize it.');}
}

/* ---- AI IN EVERY SECTION ---- */
function aiDashOverview(){
  var out=document.getElementById('dash-ai-output');
  var btn=document.getElementById('btn-dash-ai');
  if(!out)return;
  btn.disabled=true;
  out.innerHTML='<span style="color:var(--gold)"><i class="lucide icon-loader" style="animation:spin 1s linear infinite"></i> Analyzing archive...</span>';
  aiFetchRetry('/api/ai/insights',{method:'POST'},function(d){
      btn.disabled=false;
      out.innerHTML='<span class="dash-ai-text">'+aesc(d.overview||'No overview available.')+'</span>'+
        '<div style="margin-top:5px;font-family:var(--font-mono);font-size:0.42rem;color:var(--text-tertiary)">ENGINE: '+aesc(d.engine||'builtin').toUpperCase()+'</div>';
    },function(){
      btn.disabled=false;
      out.textContent='AI overview failed — the server may be waking up. Try again in ~1 minute.';
    });
}
function _renderResultAi(html){
  var box=document.getElementById('result-ai');
  if(box)box.innerHTML=html;
}
function aiResultSummary(){
  var t=state.lastOcrText;
  if(!t){toast('NO OCR TEXT TO SUMMARIZE','warn');return}
  _renderResultAi('<div class="ctrl-group"><h4><i class="lucide icon-sparkles"></i> AI Summary</h4><div class="result-ai-body"><span style="color:var(--gold)"><i class="lucide icon-loader" style="animation:spin 1s linear infinite"></i> Summarizing...</div></div></div>');
  fetch('/api/ai/document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'summarize',text:t})})
    .then(function(r){return r.json()})
    .then(function(d){
      _renderResultAi('<div class="ctrl-group"><h4><i class="lucide icon-sparkles"></i> AI Summary</h4><div class="result-ai-body">'+aesc(d.reply||d.error||'—')+'</div><div style="font-family:var(--font-mono);font-size:0.42rem;color:var(--text-tertiary);margin-top:3px">ENGINE: '+aesc(d.engine||'').toUpperCase()+'</div></div>');
    })
    .catch(function(){_renderResultAi('')});
}
function aiCaptureTips(){
  var r=state.currentResult;
  if(!r||!r.quality){toast('PROCESS A SCAN FIRST','warn');return}
  var msg='My scan quality: blur '+r.quality.blur_score+', brightness '+r.quality.brightness+
    ', lighting '+(r.quality.good_lighting?'good':'poor')+'. Give short practical tips to capture a better scan.';
  aiState.history.push({role:'user',content:msg});
  fetch('/api/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,history:[]})})
    .then(function(x){return x.json()})
    .then(function(d){
      _renderResultAi('<div class="ctrl-group"><h4><i class="lucide icon-lightbulb"></i> Capture Tips</h4><div class="result-ai-body">'+aesc(d.reply||'—')+'</div></div>');
    })
    .catch(function(){toast('TIPS FAILED','err')});
}
function toggleAiAuto(el){
  el.classList.toggle('on');
  var on=el.classList.contains('on');
  aiState.autoSummarize=on;
  fetch('/api/ai/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({auto_summarize:on})})
    .then(function(){toast(on?'AUTO-SUMMARIZE ON':'AUTO-SUMMARIZE OFF')})
    .catch(function(){toast('SAVE FAILED','err')});
}
function aiBriefingSelected(){
  if(!state.selectedDocs.length){toast('SELECT DOCUMENTS FIRST','warn');return}
  showLoader('AI BRIEFING...','READING '+Math.min(state.selectedDocs.length,5)+' DOCUMENTS');
  fetch('/api/ai/document',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'summarize',doc_paths:state.selectedDocs.slice(0,5)})})
    .then(function(r){return r.json().then(function(d){return {ok:r.ok,d:d}})})
    .then(function(res){
      hideLoader();
      if(!res.ok||res.d.error){toast(res.d.error||'BRIEFING FAILED','err');return}
      document.getElementById('modal-title').textContent='AI BRIEFING // '+res.d.doc_name.toUpperCase();
      document.getElementById('modal-body').innerHTML=
        '<div style="background:var(--cream);border:1px solid var(--gold-dim);border-radius:var(--radius-md);padding:12px;font-family:var(--font-body);font-size:0.68rem;line-height:1.6;color:var(--ink)">'+aesc(res.d.reply).replace(/\n/g,'<br>')+'</div>'+
        '<div style="margin-top:6px;font-family:var(--font-mono);font-size:0.45rem;color:var(--text-tertiary)">ENGINE: '+aesc(res.d.engine||'').toUpperCase()+' · FREE LOCAL MODEL</div>';
      document.getElementById('modal').classList.add('show');
    })
    .catch(function(){hideLoader();toast('BRIEFING FAILED','err')});
}

/* ---- INIT ---- */
applySession();
restoreState();
loadDashboard();loadActivity();
loadOcrStatus();loadAiStatus();
// Boot splash: dissolve the intro logo screen
setTimeout(function(){
  var bs=document.getElementById('boot-splash');
  if(bs)bs.classList.add('done');
},2200);
// Try to discover cameras without permission (works on some browsers)
refreshCameraList();