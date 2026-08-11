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
    if(v&&['dashboard','scanner','gallery','settings'].includes(v))switchView(v);
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
  var t={dashboard:'DASHBOARD',scanner:'SCANNER',gallery:'VAULT',settings:'CONFIG'};
  var tag=document.querySelector('.brand-tag');
  if(tag)tag.innerHTML='<strong>AI SCANNER</strong> // '+(t[v]||'NEXUS-OS');
  closeSidebar();
  clearTimeout(navTimer);
  navTimer=setTimeout(function(){
    if(v==='gallery')loadGallery();
    if(v==='dashboard'){loadDashboard();loadActivity()}
    if(v==='settings')loadSettings();
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
      return '<div class="doc-card" onclick="openPreview(\''+d.path+'\')">'+
        '<img class="doc-thumb" src="'+d.image_url+'" loading="lazy" onerror="this.outerHTML=\'<div style=\\\'display:flex;align-items:center;justify-content:center;height:100%;font-size:28px;color:var(--text-tertiary);opacity:.4;background:var(--bg-deep)\\\'><i class=\\\'lucide icon-image-off\\\'></i></div>\'">'+
        '<div class="doc-overlay"><button onclick="event.stopPropagation();window.open(\''+d.image_url+'\',\'_blank\')"><i class="lucide icon-download"></i></button>'+
        '<button onclick="event.stopPropagation();openPreview(\''+d.path+'\')"><i class="lucide icon-eye"></i></button>'+
        '<button onclick="event.stopPropagation();deleteDoc(\''+d.path+'\')"><i class="lucide icon-trash-2"></i></button></div>'+
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
    if(msg.includes('NotAllowed')||msg.includes('Permission')||msg.includes('permission')){
      toast('CAMERA BLOCKED — allow camera access in browser settings, or use HTTPS','err');
    }else if(msg.includes('NotFound')||msg.includes('No device')){
      toast('NO CAMERA FOUND on this device','err');
    }else{
      toast('CAMERA: '+msg,'err');
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
        toast('CAMERA BLOCKED — use HTTPS or allow camera access','err');
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
              toast('CAMERA BLOCKED — use HTTPS or allow camera access','err');
            }else{
              toast('CAMERA: '+msg2,'err');
            }
          }
        });
      }else if(msg.includes('NotAllowed')||msg.includes('Permission')){
        toast('CAMERA BLOCKED — use HTTPS or allow camera access','err');
      }else{
        toast('CAMERA: '+msg,'err');
      }
    }
  });
}

document.getElementById('btn-open-cam').addEventListener('click',function(e){
  e.stopPropagation();e.preventDefault();
  if(state.stream){closeCamera();return}

  // Check HTTPS FIRST — on HTTP, mediaDevices is often null, so order matters
  if(!isSecureContext()){
    toast('CAMERA REQUIRES HTTPS — add --ngrok flag or deploy with HTTPS','err');
    return;
  }
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    toast('Your browser does not support camera API. Use Chrome or Edge.','err');return
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
function phoneCameraCapture(){
  if(state.stream){closeCamera();return}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    // No API at all — fall back to native capture input immediately
    document.getElementById('native-capture').click();
    return;
  }
  // Try getUserMedia first (opens actual camera on supported browsers)
  navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(function(s){
    // Success — use the stream (same as OPEN CAMERA)
    showCameraUI(s);
    toast('CAMERA READY');
  }).catch(function(){
    // Failed (HTTP, permission, etc.) — fall back to native capture input
    document.getElementById('native-capture').click();
  });
}

function startAutoDetect(){
  autoCaptureActive=true;
  var v=document.getElementById('video'),c=document.getElementById('canvas'),ctx=c.getContext('2d');
  var prevPixels=null,stillFrames=0;
  var CAPTURE_THRESHOLD=8; // higher = more stable required
  var STILL_FRAMES_NEEDED=6; // frames document must be steady before capture

  autoCaptureTimer=setInterval(function(){
    if(!v.videoWidth||!autoCaptureActive)return;
    // Grab a tiny thumbnail (80x60) for fast pixel comparison
    var tw=80,th=60;
    c.width=tw;c.height=th;
    ctx.drawImage(v,0,0,tw,th);
    var data=ctx.getImageData(0,0,tw,th).data;

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
    document.getElementById('tel-edge').textContent=diff<CAPTURE_THRESHOLD?'STEADY':'MOVING';
    document.getElementById('tel-blur').textContent='Δ'+diff.toFixed(1);
    document.getElementById('tel-glare').textContent='LV'+avgBright.toFixed(0);

    // Corner bracket edge-detection animation
    var brackets=['vb-tl','vb-tr','vb-bl','vb-br'];
    if(diff<CAPTURE_THRESHOLD&&avgBright>30&&avgBright<240){
      stillFrames++;
      // Animate brackets while document is steady
      var pulse=stillFrames/STILL_FRAMES_NEEDED;
      var opacity=0.4+pulse*0.6;
      var color=pulse>0.5?'var(--emerald)':'var(--gold)';
      var size=36+pulse*8;
      brackets.forEach(function(id){
        var el=document.getElementById(id);
        if(el){el.style.opacity=opacity;el.style.borderColor=color;el.style.width=size+'px';el.style.height=size+'px'}
      });
      if(stillFrames>=STILL_FRAMES_NEEDED){
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
        // Capture full-res frame
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
        if(el){el.style.opacity='1';el.style.borderColor='var(--gold)';el.style.width='36px';el.style.height='36px';el.style.boxShadow=''}
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
  var qd=document.getElementById('result-qr');
  if(r.qr_codes&&r.qr_codes.length) qd.innerHTML='<div class="ctrl-group"><h4>QR / Barcodes</h4>'+r.qr_codes.map(function(q){return '<div style="background:var(--cream);padding:4px 6px;border-radius:4px;margin-top:3px;font-family:var(--font-mono);font-size:0.55rem;word-break:break-all;border:1px solid rgba(201,169,110,0.06)"><strong>'+q.type+':</strong> '+q.data+'</div>';}).join('')+'</div>';
  else qd.innerHTML='';
  document.getElementById('btn-dl').onclick=function(){window.open(r.image_url,'_blank')};
  var cb=document.getElementById('btn-cloud');
  if(r.saved_path){cb.style.display='';cb.dataset.path=(r.saved_path.split('documents\\').pop()||r.saved_path.split('documents/').pop())}else cb.style.display='none';
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
    renderGallery();
  }).catch(function(){toast('VAULT LOAD ERROR','err')});
}
function renderGallery(){
  var c=document.getElementById('gallery-container');
  var docs=state.galleryDocs;
  if(state.filter!=='all')docs=docs.filter(function(d){return d.folder===state.filter});
  if(!docs.length){
    c.innerHTML='<div style="text-align:center;padding:60px;color:var(--text-tertiary)"><div style="font-size:48px;margin-bottom:8px;opacity:.15;font-family:var(--font-classic)"><i class="lucide icon-archive"></i></div><p style="font-family:var(--font-classic);font-size:0.7rem;font-style:italic">No documents found</p></div>';
    document.getElementById('btn-merge').style.display='none';return;
  }
  document.getElementById('btn-merge').style.display=state.selectedDocs.length?'inline-flex':'none';
  document.getElementById('merge-n').textContent=state.selectedDocs.length;
  c.innerHTML='<div class="doc-grid">'+docs.map(function(d){
    var s=state.selectedDocs.includes(d.path);
    var sp=JSON.stringify(d.path);
    return '<div class="doc-card '+(s?'selected':'')+'" onclick="toggleDoc('+sp+')">'+
      '<div class="doc-thumb-wrap"><img class="doc-thumb" src="'+d.image_url+'" loading="lazy" onerror="this.outerHTML=\'<div style=\\\'display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);opacity:.4;background:var(--bg-deep)\\\'><i class=\'lucide icon-image-off\'></i></div>\'">'+
      '<div class="doc-overlay"><button onclick="event.stopPropagation();openPreview('+sp+')"><i class="lucide icon-search"></i></button>'+
      '<button onclick="event.stopPropagation();window.open(\''+d.image_url+'\',\'_blank\')"><i class="lucide icon-download"></i></button>'+
      '<button onclick="event.stopPropagation();deleteDoc('+sp+')"><i class="lucide icon-trash-2"></i></button></div></div>'+
      '<div class="doc-meta"><div class="doc-name">'+d.name+'</div><div class="doc-sub"><span>'+d.folder+'</span><span>'+d.size+'</span></div></div></div>';
  }).join('')+'</div>';
}
document.querySelectorAll('#filter-group button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('#filter-group button').forEach(function(x){x.classList.remove('active')});
    this.classList.add('active');state.filter=this.dataset.filter;renderGallery();
  });
});
function toggleDoc(p){
  var i=state.selectedDocs.indexOf(p);
  if(i>-1)state.selectedDocs.splice(i,1);else state.selectedDocs.push(p);
  renderGallery();
}
function openPreview(p){
  var d=state.galleryDocs.find(function(x){return x.path===p||encodeURI(x.path)===p||x.path.replace(/\\/g,'/')===p.replace(/\\/g,'/')});
  if(!d)return;
  document.getElementById('modal-title').textContent=d.name+' // INSPECTOR';
  document.getElementById('modal-body').innerHTML=
    '<div class="preview-grid">'+
    '<div class="preview-image"><img src="'+d.image_url+'" alt="'+d.name+'"></div>'+
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
function deleteDoc(p){
  showConfirm('DELETE THIS DOCUMENT?',function(){_deleteDoc(p)});
}
function _deleteDoc(p){
  fetch('/documents/'+p,{method:'DELETE'}).then(function(r){return r.json()})
    .then(function(d){if(d.deleted){toast('DELETED');state.selectedDocs=state.selectedDocs.filter(function(x){return x!==p});loadGallery();loadDashboard()}else toast('DELETE FAILED','err')})
    .catch(function(){toast('ERROR','err')});
}

/* ---- PDF MERGE ---- */
function mergeToPdf(){
  if(!state.selectedDocs.length){if(document.getElementById('view-gallery').classList.contains('active'))toast('SELECT DOCUMENTS FIRST','warn');return}
  showLoader('GENERATING PDF...','MERGING DOCUMENTS');
  fetch('/pdf/merge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:state.selectedDocs})})
    .then(function(r){return r.json()})
    .then(function(d){hideLoader();if(d.error){toast(d.error,'err');return}toast('PDF: '+d.name);window.location.href=d.url;state.selectedDocs=[];loadGallery()})
    .catch(function(e){hideLoader();toast('PDF MERGE FAILED','err')});
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
      if(v.usage) usageHtml='<span style="font-family:var(--font-mono);font-size:0.5rem;color:var(--text-tertiary)">'+v.usage+'</span>';
      return '<div class="toggle-row"><span>'+icons[k]+' '+labels[k]+'</span>'+
        '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end">'+
        usageHtml+
        (v.connected?'<span class="cloud-badge ok">CONFIGURED</span><button class="btn btn-outline btn-xs" onclick="cloudDisconnect(\''+k+'\')">DISCONNECT</button>'
        :v.configured?'<span class="cloud-badge warn">OFFLINE</span><button class="btn btn-primary btn-xs" onclick="cloudAuth(\''+k+'\')">CONNECT</button>'
        :'<span class="cloud-badge no">UNCONFIGURED</span><button class="btn btn-primary btn-xs" onclick="cloudAuth(\''+k+'\')"><i class="lucide icon-plug"></i> CONNECT</button>')+'</div></div>';
    }).join('');
    list.innerHTML+='<div style="margin-top:6px;text-align:center"><button class="btn btn-outline btn-xs" onclick="checkCloudUsage()" style="font-size:0.5rem"><i class="lucide icon-bar-chart-3"></i> CHECK CLOUD USAGE</button></div>';
  }).catch(function(){});
}
function checkCloudUsage(){
  showLoader('CHECKING...','QUERYING CLOUD STORAGE');
  fetch('/api/cloud/usage').then(function(r){return r.json()}).then(function(d){
    hideLoader();
    var lines=[];
    if(d.google_drive) lines.push('DRIVE: '+d.google_drive);
    if(d.dropbox) lines.push('DROPBOX: '+d.dropbox);
    if(d.onedrive) lines.push('ONEDRIVE: '+d.onedrive);
    if(lines.length) toast(lines.join(' | '));
    else toast('No connected cloud services');
    loadCloudStatus();
  }).catch(function(){hideLoader();toast('Failed to check usage','err')});
}
function cloudAuth(provider){
  fetch('/cloud/auth/'+provider).then(function(r){return r.json()}).then(function(d){
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
      if(provider==='google_drive'){
        toast('COMPLETE AUTHORIZATION IN THE POPUP...');
        var tries=0;
        var t=setInterval(function(){
          tries++;
          fetch('/cloud/status').then(function(r){return r.json()}).then(function(d2){
            if(d2.providers&&d2.providers.google_drive&&d2.providers.google_drive.connected){
              clearInterval(t);toast('GOOGLE DRIVE CONNECTED');loadCloudStatus();
            }else if(tries>120){
              clearInterval(t);
              fetch('/cloud/status').then(function(r){return r.json()}).then(function(d2){
                var uri=(d2.providers&&d2.providers.google_drive&&d2.providers.google_drive.redirect_uri)||'http://localhost:5000/auth/google/callback';
                showConfirm('GOOGLE BLOCKED THE LOGIN. OPEN https://console.cloud.google.com/apis/credentials -> EDIT YOUR OAUTH CLIENT (client id 770914580417-...) -> AUTHORIZED REDIRECT URIs -> ADD EXACTLY:\n\n'+uri+'\n\n(NO trailing slash, port 5000. Save, then try CONNECT again.)',function(){loadCloudStatus()});
              }).catch(function(){loadCloudStatus()});
            }
          }).catch(function(){});
        },1500);
      }else{
        showPrompt('PASTE AUTHORIZATION CODE:',function(code){
          if(code) fetch('/cloud/callback/'+provider+'?code='+encodeURIComponent(code))
            .then(function(r){return r.json()}).then(function(d2){
              if(d2.error)toast(d2.error,'err');else{toast('CONNECTED');loadCloudStatus()}
            }).catch(function(){});
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
};
var KEY_SETUP_GUIDE=[
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
function loadApiKeys(){
  fetch('/api/keys').then(function(r){return r.json()}).then(function(keys){
    renderKeySetupGuide(keys);
    var list=document.getElementById('api-keys-list');
    var configured=keys.filter(function(k){return k.configured});
    if(!configured.length){list.innerHTML='';return}
    list.innerHTML=configured.map(function(k){
      return '<div class="toggle-row"><span>'+KEY_META_UI[k.name]?.icon+' '+KEY_META_UI[k.name]?.label+'</span>'+
        '<div style="display:flex;gap:6px;align-items:center"><code class="code">'+(k.masked_value||'****')+'</code>'+
        '<button class="btn btn-danger btn-xs" onclick="deleteApiKey(\''+k.name+'\')" style="padding:1px 6px"><i class="lucide icon-x"></i></button></div></div>';
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
  var navMap={'1':'dashboard','2':'scanner','3':'gallery','4':'settings'};
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
  var label=document.getElementById('user-name');
  if(label)label.textContent=name;
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

/* ---- INIT ---- */
applySession();
restoreState();
loadDashboard();loadActivity();
loadOcrStatus();
// Boot splash: dissolve the intro logo screen
setTimeout(function(){
  var bs=document.getElementById('boot-splash');
  if(bs)bs.classList.add('done');
},2200);
// Try to discover cameras without permission (works on some browsers)
refreshCameraList();