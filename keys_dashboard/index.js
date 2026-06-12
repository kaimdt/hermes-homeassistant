/* API Keys Dashboard */
(function(){
var S=window.__HERMES_PLUGIN_SDK__;if(!S||!window.__HERMES_PLUGINS__)return;
var h=S.React.createElement, r=S.hooks.useRef, U=S.hooks.useState, E=S.hooks.useEffect;
var tk=window.__HERMES_SESSION_TOKEN__||"", bp=(window.__HERMES_BASE_PATH__||"")+"/api/plugins/github-bot";

function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");}

function App(){
  var el=r(null), keys=U([]), showCreate=U(false), msg=U("");
  E(function(){loadKeys()},[]);

  function loadKeys(){
    var x=new XMLHttpRequest();
    x.open("GET",bp+"/api-keys",true);
    if(tk) x.setRequestHeader("Authorization","Bearer "+tk);
    x.onload=function(){try{keys[1](JSON.parse(x.responseText).keys||[])}catch(e){}}
    x.send();
  }

  function createKey(name){
    var x=new XMLHttpRequest();
    x.open("POST",bp+"/api-keys",true);
    if(tk) x.setRequestHeader("Authorization","Bearer "+tk);
    x.setRequestHeader("Content-Type","application/json");
    x.onload=function(){try{var d=JSON.parse(x.responseText);if(d.key){msg[1](d.key);showCreate[1](false)}loadKeys()}catch(e){}}
    x.send(JSON.stringify({name:name}));
  }

  function revokeKey(id){
    var x=new XMLHttpRequest();
    x.open("DELETE",bp+"/api-keys/"+id,true);
    if(tk) x.setRequestHeader("Authorization","Bearer "+tk);
    x.onload=function(){loadKeys()}
    x.send();
  }

  return h("div",{style:{position:"absolute",inset:0,background:"#041c1c",color:"#ffe6cb",fontFamily:"Inter,sans-serif",fontSize:"13px",display:"flex",flexDirection:"column"}},
    h("div",{style:{padding:"16px 20px",borderBottom:"1px solid rgba(255,230,203,.08)",display:"flex",alignItems:"center",justifyContent:"space-between"}},
      h("div",{style:{display:"flex",alignItems:"center",gap:"12px"}},
        h("div",{style:{fontSize:"11px",fontWeight:700,letterSpacing:".06em",color:"rgba(255,230,203,.5)",textTransform:"uppercase"}},"API Keys"),
        h("div",{style:{fontSize:"9px",color:"rgba(255,230,203,.25)"}},keys[0].length+" keys")),
      h("button",{onClick:function(){showCreate[1](true);msg[1]("")},style:{background:"rgba(74,222,128,.1)",color:"rgba(74,222,128,.8)",border:"1px solid rgba(74,222,128,.15)",borderRadius:"5px",padding:"6px 14px",cursor:"pointer",fontFamily:"inherit",fontSize:"11px",fontWeight:600}},"+ New Key")
    ),
    showCreate[0] && h("div",{style:{padding:"16px 20px",borderBottom:"1px solid rgba(255,230,203,.05)",display:"flex",alignItems:"center",gap:"8px"}},
      h("input",{placeholder:"Key name (e.g. Home Assistant)",onKeyDown:function(e){if(e.key==="Enter")createKey(e.target.value)},style:{flex:1,padding:"6px 10px",background:"rgba(255,230,203,.03)",border:"1px solid rgba(255,230,203,.1)",borderRadius:"5px",color:"#ffe6cb",fontSize:"12px",outline:"none",fontFamily:"inherit"}}),
      h("button",{onClick:function(){var inp=document.querySelector("input");if(inp)createKey(inp.value)},style:{padding:"6px 14px",background:"rgba(74,222,128,.12)",color:"rgba(74,222,128,.8)",border:"none",borderRadius:"5px",cursor:"pointer",fontFamily:"inherit",fontSize:"11px"}},"Create"),
      h("button",{onClick:function(){showCreate[1](false)},style:{padding:"6px 14px",background:"none",color:"rgba(255,230,203,.3)",border:"none",cursor:"pointer",fontFamily:"inherit",fontSize:"11px"}},"Cancel")
    ),
    msg[0] && h("div",{style:{padding:"10px 20px",background:"rgba(74,222,128,.05)",borderBottom:"1px solid rgba(74,222,128,.1)",fontSize:"11px",fontFamily:"monospace",wordBreak:"break-all",display:"flex",alignItems:"center",gap:"8px"}},
      h("span",{style:{color:"rgba(74,222,128,.6)",fontWeight:600}},"New key:"),msg[0],
      h("span",{style:{color:"rgba(239,68,68,.6)",fontSize:"10px"}},"Copy now — won't be shown again")
    ),
    h("div",{style:{flex:1,overflowY:"auto",padding:"16px 20px"}},
      keys[0].length===0 && h("div",{style:{textAlign:"center",padding:40,color:"rgba(255,230,203,.15)"}},
        h("div",{style:{fontSize:32,marginBottom:8}},"🔑"),
        h("div",{style:{fontSize:12}},"No API keys yet. Click '+ New Key' to create one.")),
      keys[0].map(function(k){
        return h("div",{key:k.id,style:{padding:"12px 16px",border:"1px solid rgba(255,230,203,.06)",borderRadius:"8px",marginBottom:"8px",display:"flex",alignItems:"center",justifyContent:"space-between"}},
          h("div",null,
            h("div",{style:{fontSize:"13px",fontWeight:600,color:"rgba(255,230,203,.85)"}},k.name),
            h("div",{style:{fontSize:"10px",color:"rgba(255,230,203,.3)",marginTop:"2px"}},
              "Created: "+String(k.created).slice(0,10)+" · Last used: "+String(k.last_used))),
          h("button",{onClick:function(){if(confirm("Revoke '"+k.name+"'?"))revokeKey(k.id)},style:{fontSize:"9px",padding:"3px 8px",background:"none",color:"rgba(239,68,68,.4)",border:"1px solid rgba(239,68,68,.2)",borderRadius:"4px",cursor:"pointer",fontFamily:"inherit"}},"Revoke")
        );
      })
    )
  );
}

window.__HERMES_PLUGINS__.register("api-keys",App);
})();
