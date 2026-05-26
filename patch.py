
with open('templates/index.html', 'r') as f:
    content = f.read()

# 1. Insert lead modal before </div><!-- /app -->
lead_modal = '''
<!-- LEAD CAPTURE MODAL -->
<div id="lead-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:999;align-items:center;justify-content:center;backdrop-filter:blur(3px);">
  <div style="background:#fff;border-radius:12px;padding:28px;width:90%;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,.18);animation:fade-up .25s ease;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      <div style="width:36px;height:36px;background:#0a0a0a;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </div>
      <div>
        <div style="font-size:14.5px;font-weight:700;color:#0a0a0a">Stay Connected</div>
        <div style="font-size:11.5px;color:#888">Sigma India · sigmaindia.in</div>
      </div>
      <button onclick="dismissLead()" style="margin-left:auto;background:transparent;border:none;cursor:pointer;color:#aaa;font-size:22px;line-height:1;padding:0">&#215;</button>
    </div>
    <p id="lead-prompt-text" style="font-size:13.5px;color:#444;line-height:1.6;margin:14px 0"></p>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div>
        <label style="font-size:11.5px;font-weight:600;color:#555;display:block;margin-bottom:4px">Your Name</label>
        <input id="lead-name" type="text" placeholder="Enter your name" style="width:100%;padding:9px 12px;border:1.5px solid #e0e0e0;border-radius:7px;font-size:13.5px;font-family:inherit;outline:none;transition:border-color .15s" onfocus="this.style.borderColor='#0a0a0a'" onblur="this.style.borderColor='#e0e0e0'"/>
      </div>
      <div>
        <label style="font-size:11.5px;font-weight:600;color:#555;display:block;margin-bottom:4px">Phone Number</label>
        <input id="lead-phone" type="tel" placeholder="+91 XXXXX XXXXX" style="width:100%;padding:9px 12px;border:1.5px solid #e0e0e0;border-radius:7px;font-size:13.5px;font-family:inherit;outline:none;transition:border-color .15s" onfocus="this.style.borderColor='#0a0a0a'" onblur="this.style.borderColor='#e0e0e0'"/>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-top:16px">
      <button onclick="submitLead()" style="flex:1;padding:10px;background:#0a0a0a;color:#fff;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:background .14s" onmouseover="this.style.background='#1a1a1a'" onmouseout="this.style.background='#0a0a0a'">Submit</button>
      <button onclick="dismissLead()" style="padding:10px 18px;background:#f3f3f3;color:#555;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;">Skip</button>
    </div>
  </div>
</div>
'''
content = content.replace('<!-- DUMMY PLACEHOLDER IMAGE -->', lead_modal + '\n<!-- DUMMY PLACEHOLDER IMAGE -->')

# 2. Replace script init block
old_init = "const DUMMY = document.getElementById('dummy-img').src;\n\n// Load config on startup to apply banner / brand name\nfetch('/config-public').then(r=>r.json()).then(cfg=>{\n  if (cfg.brand_name) {\n    document.getElementById('brand-name').textContent   = cfg.brand_name;\n    document.getElementById('welcome-title').textContent= cfg.brand_name;\n    document.title = cfg.brand_name;\n  }\n  if (cfg.welcome_message) {\n    const el = document.getElementById('welcome-custom-msg');\n    if(el){ el.textContent=cfg.welcome_message; el.style.display='block'; }\n  }\n  if (cfg.offer_banner && cfg.offer_banner.trim()) {\n    const ob = document.getElementById('offer-banner');\n    ob.textContent    = cfg.offer_banner;\n    ob.style.display  = 'block';\n  }\n}).catch(()=>{});\n\n// Textarea auto-resize\nconst ta = document.getElementById('user-input');\nta.addEventListener('input', function(){\n  this.style.height='auto';\n  this.style.height=Math.min(this.scrollHeight,160)+'px';\n});\nta.addEventListener('keydown',function(e){\n  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submitMessage();}\n});\n\nfunction submitMessage(){\n  const v=ta.value.trim(); if(!v)return;\n  ta.value=''; ta.style.height='auto';\n  sendMessage(v);\n}\n\nfunction sendMessage(msg){\n  hideWelcome(); hideChips();\n  addUserMsg(msg); showThinking(); setBusy(true);\n  fetch('/chat',{\n    method:'POST',headers:{'Content-Type':'application/json'},\n    body:JSON.stringify({message:msg})\n  }).then(r=>r.json()).then(d=>{removeThinking();addBotMsg(d);setBusy(false);})\n  .catch(()=>{\n    removeThinking();\n    addBotMsg({text:\"Sorry, something went wrong. Please try again.\",products:[],prices:[],dealers:[]});\n    setBusy(false);\n  });\n}"

new_init = """const DUMMY = document.getElementById('dummy-img').src;

// Lead capture state
let LEAD_CFG = { collect: false, gap: 3, prompt: '' };
let userMsgCount = 0;
let leadCaptured = false;
let leadDismissed = false;

// Load config on startup
fetch('/config-public').then(r=>r.json()).then(cfg=>{
  if (cfg.brand_name) {
    document.getElementById('brand-name').textContent   = cfg.brand_name;
    document.getElementById('welcome-title').textContent= cfg.brand_name;
    document.title = cfg.brand_name;
  }
  if (cfg.welcome_message) {
    const el = document.getElementById('welcome-custom-msg');
    if(el){ el.textContent=cfg.welcome_message; el.style.display='block'; }
  }
  if (cfg.offer_banner && cfg.offer_banner.trim()) {
    const ob = document.getElementById('offer-banner');
    ob.textContent   = cfg.offer_banner;
    ob.style.display = 'block';
  }
  LEAD_CFG.collect = !!cfg.collect_user_data;
  LEAD_CFG.gap     = parseInt(cfg.user_data_message_gap) || 3;
  LEAD_CFG.prompt  = cfg.collect_user_prompt || 'May I have your name and phone number so our team can assist you better?';
  document.getElementById('lead-prompt-text').textContent = LEAD_CFG.prompt;
}).catch(()=>{});

// Textarea auto-resize
const ta = document.getElementById('user-input');
ta.addEventListener('input', function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,160)+'px';
});
ta.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submitMessage();}
});

function submitMessage(){
  const v=ta.value.trim(); if(!v)return;
  ta.value=''; ta.style.height='auto';
  sendMessage(v);
}

function sendMessage(msg){
  hideWelcome(); hideChips();
  addUserMsg(msg); showThinking(); setBusy(true);
  userMsgCount++;
  fetch('/chat',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg})
  }).then(r=>r.json()).then(d=>{
    removeThinking(); addBotMsg(d); setBusy(false);
    if (LEAD_CFG.collect && !leadCaptured && !leadDismissed && userMsgCount > 0 && userMsgCount % LEAD_CFG.gap === 0) {
      setTimeout(() => showLeadModal(), 900);
    }
  }).catch(()=>{
    removeThinking();
    addBotMsg({text:"Sorry, something went wrong. Please try again.",products:[],prices:[],dealers:[]});
    setBusy(false);
  });
}

function showLeadModal() {
  const m = document.getElementById('lead-modal');
  m.style.display = 'flex';
  setTimeout(()=>document.getElementById('lead-name').focus(), 100);
}
function dismissLead() {
  document.getElementById('lead-modal').style.display = 'none';
  leadDismissed = true;
}
function submitLead() {
  const name  = document.getElementById('lead-name').value.trim();
  const phone = document.getElementById('lead-phone').value.trim();
  if (!name && !phone) { dismissLead(); return; }
  fetch('/save-lead',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, phone})
  }).then(()=>{
    leadCaptured = true;
    document.getElementById('lead-modal').style.display = 'none';
    const inner = document.getElementById('messages-inner');
    const row = document.createElement('div');
    row.className='msg-row bot';
    row.innerHTML=avatarBotHtml()+'<div class="msg-body"><div class="bubble bot"><p>Thank you'+(name?' '+name:'')+'! Our team will reach out to you shortly. How else can I help you?</p></div><div class="msg-time">'+nowTime()+' · Sigma AI Assistant</div></div>';
    inner.appendChild(row); scrollBottom();
  }).catch(()=>{ dismissLead(); });
}"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("Script block replaced successfully")
else:
    print("WARNING: could not find exact script block, will do line-based replacement")
    # fallback: just write new_init after "const DUMMY..."
    content = content.replace(
        "const DUMMY = document.getElementById('dummy-img').src;",
        new_init
    )

with open('templates/index.html', 'w') as f:
    f.write(content)
print("Done. File size:", len(content))
