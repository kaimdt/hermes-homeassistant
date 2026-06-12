/* Hermes Chat Card — Local Lovelace Card (no external deps) */
class HermesChatCard extends HTMLElement {
  constructor() { super(); this._apiUrl = "http://192.168.2.150:9119/api/plugins/github-bot/ha/chat"; }

  setConfig(config) { if (config.api_url) this._apiUrl = config.api_url; }

  set hass(hass) {
    if (!this._built) {
      this.innerHTML = `
        <style>
          .hc-root{display:flex;flex-direction:column;height:500px;background:var(--primary-background-color,#1c1c1c);border-radius:12px;overflow:hidden;font-family:var(--paper-font-body1)}
          .hc-header{padding:12px 16px;background:var(--sidebar-background-color,#1a1a1a);border-bottom:1px solid var(--divider-color,#333);font-size:13px;font-weight:600;color:var(--primary-text-color,#e0e0e0)}
          .hc-msgs{flex:1;overflow-y:auto;padding:12px}
          .hc-msg{max-width:80%;padding:8px 12px;border-radius:12px;margin-bottom:8px;font-size:13px;line-height:1.5}
          .hc-msg.user{margin-left:auto;background:var(--accent-color,#03a9f4);color:#fff}
          .hc-msg.bot{background:var(--card-background-color,#2a2a2a);color:var(--primary-text-color,#e0e0e0)}
          .hc-ts{font-size:9px;color:var(--secondary-text-color,#777);margin-top:2px}
          .hc-input-row{display:flex;gap:8px;padding:8px 12px;border-top:1px solid var(--divider-color,#333)}
          .hc-input{flex:1;padding:8px 12px;background:var(--card-background-color,#2a2a2a);border:1px solid var(--divider-color,#333);border-radius:8px;color:var(--primary-text-color,#e0e0e0);font-size:13px;outline:none}
          .hc-send{padding:8px 16px;background:var(--accent-color,#03a9f4);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer}
          .hc-typing{font-size:10px;color:var(--secondary-text-color,#777);padding:4px 12px}
          @keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
          .hc-msg{animation:fadeIn .2s}
        </style>
        <div class="hc-root">
          <div class="hc-header">🤖 Hermes AI</div>
          <div class="hc-msgs"></div>
          <div class="hc-typing" style="display:none">Hermes denkt nach...</div>
          <div class="hc-input-row">
            <input class="hc-input" placeholder="Nachricht an Hermes...">
            <button class="hc-send">Senden</button>
          </div>
        </div>
      `;
      this._msgs = this.querySelector(".hc-msgs");
      this._typing = this.querySelector(".hc-typing");
      this._input = this.querySelector(".hc-input");
      
      this.querySelector(".hc-send").onclick = () => this._send();
      this._input.onkeydown = (e) => { if (e.key === "Enter") this._send(); };
      
      this._addMsg("Hallo! Ich bin Hermes. Frag mich was du willst — Smart Home, Fragen, Hilfe.", "bot");
      this._built = true;
    }
  }

  _addMsg(text, role) {
    const div = document.createElement("div");
    div.className = "hc-msg " + role;
    div.textContent = text;
    const ts = document.createElement("div");
    ts.className = "hc-ts";
    ts.textContent = new Date().toLocaleTimeString();
    div.appendChild(ts);
    this._msgs.appendChild(div);
    this._msgs.scrollTop = this._msgs.scrollHeight;
  }

  async _send() {
    const txt = this._input.value.trim();
    if (!txt) return;
    this._addMsg(txt, "user");
    this._input.value = "";
    this._typing.style.display = "block";

    try {
      const res = await fetch(this._apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: txt, user: "kaimdt" }),
      });
      const data = await res.json();
      this._typing.style.display = "none";
      this._addMsg(data.response || data.error || "Keine Antwort", "bot");
    } catch (e) {
      this._typing.style.display = "none";
      this._addMsg("Fehler: " + e.message, "bot");
    }
  }

  getCardSize() { return 4; }
}

customElements.define("hermes-chat-card", HermesChatCard);
