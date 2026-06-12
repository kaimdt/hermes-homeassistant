/* Hermes Chat for Home Assistant — embeddable iframe page */
(function(){
var S=window.__HERMES_PLUGIN_SDK__;if(!S||!window.__HERMES_PLUGINS__)return;
var h=S.React.createElement, r=S.hooks.useRef, U=S.hooks.useState, E=S.hooks.useEffect;
var tk=window.__HERMES_SESSION_TOKEN__||"", bp=(window.__HERMES_BASE_PATH__||"")+"/api/plugins/github-bot";
var haEndpoint=bp+"/ha/chat";

function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");}

function App(){
  var el=r(null), msgs=U([]), input=U(""), sending=U(false);
  var endRef=r(null);
  
  E(function(){
    msgs[1]([{role:"assistant",text:"Hello! I'm Hermes. How can I help you today? ✨",ts:new Date().toISOString()}]);
  },[]);

  function send(){
    var txt=input[0].trim(); if(!txt||sending[0]) return;
    msgs[1](msgs[0].concat([{role:"user",text:txt,ts:new Date().toISOString()}]));
    input[1](""); sending[1](true);
    var x=new XMLHttpRequest();
    x.open("POST",haEndpoint,true);
    if(tk) x.setRequestHeader("Authorization","Bearer "+tk);
    x.setRequestHeader("Content-Type","application/json");
    x.onload=function(){
      try{
        var d=JSON.parse(x.responseText);
        msgs[1](function(prev){return prev.concat([{role:"assistant",text:d.response||d.error||"No response",ts:new Date().toISOString()}])});
      }catch(e){
        msgs[1](function(prev){return prev.concat([{role:"assistant",text:"Error: "+String(e),ts:new Date().toISOString()}])});
      }
      sending[1](false);
      setTimeout(function(){if(endRef.current) endRef.current.scrollIntoView({behavior:"smooth"})},100);
    };
    x.onerror=function(){msgs[1](function(prev){return prev.concat([{role:"assistant",text:"Connection error",ts:new Date().toISOString()}])});sending[1](false)};
    x.send(JSON.stringify({message:txt,user:"kaimdt"}));
  }

  E(function(){if(endRef.current) endRef.current.scrollIntoView({behavior:"smooth"})},[msgs[0].length]);

  return h("div",{style:{display:"flex",flexDirection:"column",height:"100%",background:"#0d1117",color:"#c9d1d9",fontFamily:"-apple-system,BlinkMacSystemFont,sans-serif",fontSize:"14px"}},
    h("div",{style:{padding:"12px 16px",borderBottom:"1px solid #21262d",fontSize:"11px",fontWeight:600,color:"#8b949e",textTransform:"uppercase",letterSpacing:".05em"}},"Hermes Chat"),
    h("div",{style:{flex:1,overflowY:"auto",padding:"8px 12px"}},
      msgs[0].map(function(m,i){
        var isUser=m.role==="user";
        return h("div",{key:i,style:{display:"flex",flexDirection:"column",alignItems:isUser?"flex-end":"flex-start",marginBottom:"8px"}},
          h("div",{style:{maxWidth:"85%",padding:"8px 12px",borderRadius:"12px",background:isUser?"#238636":"#21262d",color:isUser?"#fff":"#c9d1d9",fontSize:"13px",lineHeight:"1.5"}},m.text),
          h("div",{style:{fontSize:"10px",color:"#484f58",marginTop:"2px",padding:"0 4px"}},new Date(m.ts).toLocaleTimeString())
        );
      }),
      h("div",{ref:endRef})
    ),
    h("div",{style:{padding:"8px 12px",borderTop:"1px solid #21262d",display:"flex",gap:"8px"}},
      h("input",{style:{flex:1,padding:"8px 12px",background:"#161b22",border:"1px solid #30363d",borderRadius:"8px",color:"#c9d1d9",fontSize:"13px",outline:"none"},placeholder:"Message Hermes...",value:input[0],onChange:function(e){input[1](e.target.value)},onKeyDown:function(e){if(e.key==="Enter") send()}}),
      h("button",{style:{padding:"8px 16px",background:"#238636",color:"#fff",border:"none",borderRadius:"8px",fontSize:"13px",fontWeight:600,cursor:sending[0]?"wait":"pointer"},onClick:send,disabled:sending[0]},sending[0]?"...":"Send")
    )
  );
}

window.__HERMES_PLUGINS__.register("ha-chat",App);
})();
