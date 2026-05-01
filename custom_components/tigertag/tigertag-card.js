/**
 * TigerTag Card v4.0
 * - Logo "link" SVG inline pour Twin Tag
 * - Bouton refresh
 * - Tare masterspool modifiable par bobine
 * - Lieux de stockage dynamiques (depuis config_flow)
 * - Détection automatique des imprimantes Bambu Lab et leurs trays
 * - Envoi via bambu_lab.set_filament (plus de MQTT manuel)
 * - Zéro scintillement (DOM persistant)
 */
const VERSION = "4.0.0";

// SVG "link / chaîne" inspiré de Flaticon #455691
const LINK_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

const CSS = `
:host {
  display: block;
  --tt-green: #1D9E75;
  --tt-red:   #E24B4A;
  --tt-blue:  #185FA5;
  --tt-panel-w: 340px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
.tt { background: var(--lovelace-background, var(--primary-background-color)); }

/* Toolbar */
.tt-toolbar {
  display: flex; gap: 8px; padding: 12px 16px 0;
  align-items: center; flex-wrap: wrap;
}
.tt-title { font-size: 16px; font-weight: 500; color: var(--primary-text-color); flex: none; margin-right: 4px; }
.tt-search {
  flex: 1; min-width: 140px; height: 36px; padding: 0 12px; font-size: 13px;
  border-radius: 8px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color);
  outline: none; transition: border-color .15s;
}
.tt-search:focus { border-color: var(--tt-green); }
.tt-btn-refresh {
  height: 36px; width: 36px; border-radius: 8px; flex-shrink: 0;
  border: 1px solid var(--divider-color); background: var(--card-background-color);
  color: var(--secondary-text-color); cursor: pointer; display: flex;
  align-items: center; justify-content: center; transition: all .15s;
}
.tt-btn-refresh:hover { border-color: var(--tt-green); color: var(--tt-green); }
.tt-btn-refresh.spinning svg { animation: tt-spin .7s linear infinite; }
@keyframes tt-spin { to { transform: rotate(360deg); } }

/* Filtres */
.tt-filters {
  display: flex; gap: 5px; padding: 8px 16px; flex-wrap: wrap;
  border-bottom: 1px solid var(--divider-color);
}
.tt-filter {
  font-size: 11px; padding: 3px 11px; border-radius: 20px;
  border: 1px solid var(--divider-color); background: transparent;
  color: var(--secondary-text-color); cursor: pointer; transition: all .12s; white-space: nowrap;
}
.tt-filter:hover { border-color: var(--tt-green); color: var(--tt-green); }
.tt-filter.active { background: var(--tt-green); color: #fff; border-color: var(--tt-green); }

/* Grille */
.tt-grid-wrap { padding: 12px 16px 16px; }
.tt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(145px, 1fr)); gap: 10px; }
@media (max-width: 480px) { .tt-grid { grid-template-columns: repeat(2, 1fr); } }

/* Carte bobine */
.tt-spool {
  background: var(--card-background-color); border: 1px solid var(--divider-color);
  border-radius: 12px; overflow: hidden; cursor: pointer;
  transition: border-color .12s, transform .1s; position: relative;
}
.tt-spool:hover { border-color: var(--tt-green); transform: translateY(-1px); }
.tt-spool.selected { border: 2px solid var(--tt-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--tt-green) 15%, transparent); }
.tt-spool.low-stock { border-color: var(--tt-red); }
.tt-spool.low-stock.selected { border-color: var(--tt-red); box-shadow: 0 0 0 3px color-mix(in srgb, var(--tt-red) 15%, transparent); }

.tt-spool-img-wrap { width: 100%; aspect-ratio: 1/1; overflow: hidden; position: relative; background: var(--secondary-background-color); }
.tt-spool-img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .2s; }
.tt-spool:hover .tt-spool-img { transform: scale(1.03); }
.tt-spool-color { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.tt-spool-body { padding: 8px 9px 9px; }
.tt-spool-name { font-size: 12px; font-weight: 500; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px; }
.tt-spool-sub  { font-size: 10px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 6px; }
.tt-spool-foot { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.tt-spool-weight { font-size: 12px; font-weight: 500; color: var(--primary-text-color); }
.tt-bar { height: 3px; border-radius: 2px; background: var(--divider-color); margin-top: 6px; }
.tt-bar-fill { height: 100%; border-radius: 2px; }

/* Tags */
.tt-tag { font-size: 9px; padding: 2px 5px; border-radius: 4px; font-weight: 500; white-space: nowrap; }
.tt-tag-plus   { background: #fff3e0; color: #bf360c; }
.tt-tag-base   { background: #e8f5e9; color: #1b5e20; }
.tt-tag-ams    { background: #e1f5ee; color: #0f6e56; }
.tt-tag-room   { background: #e6f1fb; color: var(--tt-blue); }
.tt-tag-refill { background: #fce4ec; color: #880e4f; }
.tt-tag-eco    { background: #e8f5e9; color: #1b5e20; }

/* Badge twin — logo chaîne */
.tt-twin-dot {
  position: absolute; top: 6px; right: 6px;
  height: 20px; padding: 0 5px; border-radius: 10px;
  background: rgba(24,95,165,.8); backdrop-filter: blur(4px);
  display: flex; align-items: center; gap: 3px;
}
.tt-twin-dot svg { width: 11px; height: 11px; color: #fff; }
.tt-twin-dot span { font-size: 9px; font-weight: 500; color: #fff; }

/* Overlay */
.tt-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.35); z-index: 99; }
.tt-overlay.open { display: block; }

/* Panneau */
.tt-panel {
  position: fixed; top: 0; right: 0; bottom: 0; width: var(--tt-panel-w);
  background: var(--card-background-color); border-left: 1px solid var(--divider-color);
  display: flex; flex-direction: column;
  transform: translateX(100%); transition: transform .28s cubic-bezier(.4,0,.2,1);
  overflow: hidden; z-index: 100; box-shadow: -4px 0 24px rgba(0,0,0,.18);
}
.tt-panel.open { transform: translateX(0); }
@media (max-width: 700px) { .tt-panel { width: 100%; border-left: none; } }

.tt-panel-head {
  display: flex; align-items: center; padding: 10px 12px;
  border-bottom: 1px solid var(--divider-color); gap: 8px; flex-shrink: 0;
}
.tt-panel-close {
  width: 28px; height: 28px; border-radius: 50%; border: 1px solid var(--divider-color);
  background: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--secondary-text-color); flex-shrink: 0;
}
.tt-panel-close:hover { background: var(--secondary-background-color); }
.tt-panel-head-name { font-size: 13px; font-weight: 500; color: var(--primary-text-color); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.tt-panel-img-wrap { width: 100%; overflow: hidden; flex-shrink: 0; position: relative; background: var(--secondary-background-color); }
.tt-panel-img   { width: 100%; height: auto; max-height: 240px; object-fit: contain; display: block; }
.tt-panel-color { width: 100%; aspect-ratio: 4/3; max-height: 180px; display: flex; align-items: center; justify-content: center; }
.tt-panel-badges { position: absolute; top: 8px; left: 8px; display: flex; gap: 4px; flex-wrap: wrap; }
.tt-panel-badge { font-size: 9px; padding: 2px 7px; border-radius: 4px; font-weight: 500; backdrop-filter: blur(4px); }

.tt-panel-body { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 14px; }
.tt-section-label { font-size: 10px; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 7px; }

/* Poids */
.tt-weight-box { background: var(--secondary-background-color); border-radius: 8px; padding: 10px; }
.tt-weight-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
.tt-weight-val { font-size: 24px; font-weight: 500; color: var(--primary-text-color); }
.tt-weight-cap { font-size: 11px; color: var(--secondary-text-color); }
.tt-w-bar { height: 4px; border-radius: 2px; background: var(--divider-color); margin-bottom: 8px; }
.tt-w-bar-fill { height: 100%; border-radius: 2px; }
input[type=range].tt-range { width: 100%; margin: 0 0 8px; cursor: pointer; accent-color: var(--tt-green); }
.tt-weight-row2 { display: flex; gap: 6px; margin-bottom: 8px; }
.tt-w-input {
  flex: 1; height: 32px; padding: 0 8px; font-size: 13px;
  border-radius: 6px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); outline: none;
}
.tt-w-input:focus { border-color: var(--tt-green); }
.tt-btn-save {
  height: 32px; padding: 0 14px; border-radius: 6px; border: none;
  background: var(--tt-green); color: #fff; font-size: 12px; font-weight: 500; cursor: pointer;
}
.tt-btn-save:hover { opacity: .85; }
.tt-btn-save:disabled { opacity: .5; cursor: default; }
.tt-w-note { font-size: 11px; color: var(--secondary-text-color); margin-top: 4px; }

/* Tare */
.tt-tare-row { display: flex; gap: 6px; align-items: center; margin-top: 8px; }
.tt-tare-label { font-size: 11px; color: var(--secondary-text-color); white-space: nowrap; }
.tt-tare-input {
  width: 80px; height: 28px; padding: 0 7px; font-size: 12px;
  border-radius: 6px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); outline: none;
}
.tt-tare-input:focus { border-color: var(--tt-green); }
.tt-btn-tare {
  height: 28px; padding: 0 10px; border-radius: 6px;
  border: 1px solid var(--divider-color); background: transparent;
  color: var(--primary-text-color); font-size: 11px; cursor: pointer;
}
.tt-btn-tare:hover { background: var(--secondary-background-color); }

/* Emplacement */
.tt-loc-rows { display: flex; flex-direction: column; gap: 7px; }
.tt-loc-row  { display: flex; align-items: center; gap: 8px; }
.tt-loc-lbl  { font-size: 11px; color: var(--secondary-text-color); width: 44px; flex-shrink: 0; }
.tt-loc-sel  {
  flex: 1; height: 30px; font-size: 12px; padding: 0 7px;
  border-radius: 6px; border: 1px solid var(--divider-color);
  background: var(--card-background-color); color: var(--primary-text-color); outline: none;
}
.tt-loc-sel:focus { border-color: var(--tt-green); }
.tt-btn-ams {
  margin-top: 4px; height: 30px; padding: 0 12px; border-radius: 6px;
  border: 1px solid var(--tt-green); background: transparent; color: var(--tt-green);
  font-size: 11px; font-weight: 500; cursor: pointer; width: 100%;
}
.tt-btn-ams:hover { background: color-mix(in srgb, var(--tt-green) 10%, transparent); }

/* Températures */
.tt-temp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.tt-temp-chip { background: var(--secondary-background-color); border-radius: 7px; padding: 8px; text-align: center; }
.tt-temp-lbl  { font-size: 10px; color: var(--secondary-text-color); margin-bottom: 3px; }
.tt-temp-val  { font-size: 13px; font-weight: 500; color: var(--primary-text-color); }

/* Liens */
.tt-links { display: flex; gap: 5px; flex-wrap: wrap; }
.tt-link-btn { font-size: 11px; padding: 4px 9px; border-radius: 5px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-color); text-decoration: none; display: inline-block; }
.tt-link-btn:hover { background: var(--secondary-background-color); }

/* Info rows */
.tt-info-row { display: flex; justify-content: space-between; font-size: 11px; padding: 4px 0; border-bottom: 1px solid var(--divider-color); }
.tt-info-row:last-child { border-bottom: none; }
.tt-info-k { color: var(--secondary-text-color); }
.tt-info-v { color: var(--primary-text-color); font-weight: 500; text-align: right; max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.tt-empty { grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--secondary-text-color); font-size: 13px; }
`;

class TigerTagCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass        = null;
    this._config      = {};
    this._selected    = null;
    this._search      = "";
    this._filter      = "Toutes";
    this._editWeight  = null;
    this._initialized = false;
    this._refreshing  = false;
    this._domGrid = this._domOverlay = this._domPanel = this._domFilters = null;
  }

  setConfig(cfg) {
    this._config = { title: cfg.title || null };
  }
  static getStubConfig() { return { type: "custom:tigertag-card" }; }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) { this._initDOM(); this._initialized = true; }
    this._renderGrid();
    if (this._selected) this._syncPanelWeight();
  }

  /* ── Détection Bambu Lab ─────────────────────────────────────────────── */
  _getBambuTrayEntities() {
    if (!this._hass) return [];
    return Object.values(this._hass.states).filter(e => {
      if (!e.entity_id.startsWith("sensor.")) return false;
      const a = e.attributes;
      // Les trays Bambu exposent nozzle_temp_min_val ou tray_type
      return (a.tray_type !== undefined || a.nozzle_temp_min_val !== undefined)
        && !e.entity_id.includes("tigertag");
    });
  }

  _getBambuTrayOptions() {
    const trays = this._getBambuTrayEntities();
    const opts = [{ value: "—", label: "Pas dans un AMS" }];
    trays.forEach(e => {
      const name = e.attributes.friendly_name || e.entity_id;
      opts.push({ value: e.entity_id, label: name });
    });
    return opts;
  }

  /* ── Lieux de stockage depuis le coordinator ─────────────────────────── */
  _getConfigLocations() {
    if (!this._hass) return ["Garage","Salon","Bureau"];
    // Les lieux sont exposés dans coordinator.data["config_locations"]
    // via l'attribut de n'importe quel sensor tigertag
    const sensor = Object.values(this._hass.states).find(e =>
      e.entity_id.startsWith("sensor.") && e.attributes.uid && e.entity_id.includes("tigertag")
    );
    return sensor?.attributes?.config_locations || ["Garage","Salon","Bureau"];
  }

  /* ── Init DOM ────────────────────────────────────────────────────────── */
  _initDOM() {
    const style = document.createElement("style");
    style.textContent = CSS;
    const root = document.createElement("div");
    root.className = "tt";

    // Toolbar
    const tb = document.createElement("div");
    tb.className = "tt-toolbar";
    if (this._config.title) {
      const t = document.createElement("span");
      t.className = "tt-title"; t.textContent = this._config.title;
      tb.appendChild(t);
    }
    const inp = document.createElement("input");
    inp.className = "tt-search"; inp.type = "text";
    inp.placeholder = "Rechercher marque, matériau, couleur, UID…";
    inp.addEventListener("input", e => { this._search = e.target.value; this._renderGrid(); });
    tb.appendChild(inp);

    // Bouton refresh
    const refreshBtn = document.createElement("button");
    refreshBtn.className = "tt-btn-refresh";
    refreshBtn.title = "Rafraîchir l'inventaire";
    refreshBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`;
    refreshBtn.addEventListener("click", () => this._doRefresh(refreshBtn));
    tb.appendChild(refreshBtn);
    root.appendChild(tb);

    // Filtres
    this._domFilters = document.createElement("div");
    this._domFilters.className = "tt-filters";
    root.appendChild(this._domFilters);

    // Grille
    const gw = document.createElement("div");
    gw.className = "tt-grid-wrap";
    this._domGrid = document.createElement("div");
    this._domGrid.className = "tt-grid";
    gw.appendChild(this._domGrid);
    root.appendChild(gw);

    // Overlay
    this._domOverlay = document.createElement("div");
    this._domOverlay.className = "tt-overlay";
    this._domOverlay.addEventListener("click", () => this._closePanel());

    // Panneau
    this._domPanel = document.createElement("div");
    this._domPanel.className = "tt-panel";

    this.shadowRoot.replaceChildren(style, root, this._domOverlay, this._domPanel);
    this._buildFilters();
  }

  _buildFilters() {
    const rooms   = this._getConfigLocations();
    const filters = ["Toutes","Dans un AMS","Non placées","Stock faible",...rooms];
    this._domFilters.innerHTML = "";
    filters.forEach(f => {
      const b = document.createElement("button");
      b.className = "tt-filter" + (f === this._filter ? " active" : "");
      b.textContent = f;
      b.addEventListener("click", () => {
        this._filter = f;
        this._domFilters.querySelectorAll(".tt-filter").forEach(el =>
          el.classList.toggle("active", el.textContent === f));
        this._renderGrid();
      });
      this._domFilters.appendChild(b);
    });
  }

  /* ── Refresh ─────────────────────────────────────────────────────────── */
  async _doRefresh(btn) {
    if (this._refreshing || !this._hass) return;
    this._refreshing = true;
    btn.classList.add("spinning");
    try {
      await this._hass.callService("tigertag", "refresh", {});
    } catch(e) { console.error("[TigerTagCard] refresh:", e); }
    finally {
      setTimeout(() => { this._refreshing = false; btn.classList.remove("spinning"); }, 1500);
    }
  }

  /* ── Données ─────────────────────────────────────────────────────────── */
  _allSpools() {
    if (!this._hass) return [];
    return Object.values(this._hass.states)
      .filter(e => e.entity_id.startsWith("sensor.tigertag_") && e.attributes.uid)
      .map(e => this._normalize(e));
  }

  _normalize(e) {
    const a = e.attributes;
    const tare = a.container_weight_effective ?? a.container_weight_custom ?? a.container_weight ?? 0;
    return {
      entity_id:    e.entity_id,
      uid:          String(a.uid || ""),
      name:         a.color_name || a.product_name || a.friendly_name || e.entity_id,
      brand:        a.brand || "",
      material:     a.material || "",
      series:       a.series || "",
      color_hex:    a.color_hex || "#888888",
      img_url:      (a.img_url && a.img_url !== "--") ? a.img_url : null,
      is_plus:      !!a.is_plus,
      has_twin:     !!a.has_twin,
      twin_uid:     a.twin_uid || null,
      weight:       parseFloat(e.state) || 0,
      capacity:     parseFloat(a.capacity_gr) || 1000,
      tare:         parseFloat(tare) || 0,
      tare_official:parseFloat(a.container_weight) || 0,
      tare_custom:  a.container_weight_custom != null ? parseFloat(a.container_weight_custom) : null,
      ams_entity:   a.ams_location || null,   // entity_id du tray Bambu
      room:         a.room_location || null,
      nozzle_min:   a.nozzle_temp_min || null,
      nozzle_max:   a.nozzle_temp_max || null,
      bed_min:      a.bed_temp_min || null,
      bed_max:      a.bed_temp_max || null,
      dry_temp:     a.dry_temp || null,
      dry_time:     a.dry_time_hours || null,
      link_msds:    a.link_msds || null,
      link_tds:     a.link_tds || null,
      link_rohs:    a.link_rohs || null,
      link_reach:   a.link_reach || null,
      link_food:    a.link_food || null,
      link_youtube: a.link_youtube || null,
      is_refill:    !!a.is_refill,
      is_recycled:  !!a.is_recycled,
      sku:          a.sku || null,
      barcode:      a.barcode || null,
      diameter:     a.diameter || null,
    };
  }

  _deduplicated(spools) {
    const uids = new Set(spools.map(s => s.uid));
    const hidden = new Set();
    spools.forEach(s => {
      if (s.has_twin && s.twin_uid && uids.has(s.twin_uid) && !hidden.has(s.uid))
        hidden.add(s.twin_uid);
    });
    return spools.filter(s => !hidden.has(s.uid));
  }

  _filtered() {
    const all = this._deduplicated(this._allSpools());
    const q   = this._search.toLowerCase();
    const f   = this._filter;
    const thr = 250;
    return all.filter(s => {
      const mq = !q || s.name.toLowerCase().includes(q) || s.brand.toLowerCase().includes(q)
               || s.material.toLowerCase().includes(q)  || s.uid.toLowerCase().includes(q);
      const mf = f === "Toutes"
        || (f === "Dans un AMS"  && s.ams_entity)
        || (f === "Non placées"  && !s.ams_entity && !s.room)
        || (f === "Stock faible" && s.weight < thr && s.weight >= 0)
        || s.room === f;
      return mq && mf;
    });
  }

  /* ── Grille ──────────────────────────────────────────────────────────── */
  _renderGrid() {
    if (!this._domGrid) return;
    this._buildFilters(); // met à jour les lieux si changés
    const spools = this._filtered();
    const thr    = 250;
    this._domGrid.innerHTML = "";
    if (!spools.length) {
      this._domGrid.innerHTML = `<div class="tt-empty">Aucune bobine trouvée</div>`;
      return;
    }
    spools.forEach(s => this._domGrid.appendChild(this._spoolCard(s, thr)));
  }

  _syncPanelWeight() {
    if (!this._selected || this._editWeight !== null) return;
    const s = this._allSpools().find(x => x.entity_id === this._selected);
    if (!s) return;
    const wval  = this._domPanel.querySelector("#tt-wval");
    const wbar  = this._domPanel.querySelector("#tt-wbar");
    const range = this._domPanel.querySelector("#tt-range");
    const winp  = this._domPanel.querySelector("#tt-winput");
    if (!wval) return;
    wval.textContent = Math.round(s.weight) + " g";
    if (wbar) { wbar.style.width = this._pct(s.weight, s.capacity) + "%"; wbar.style.background = this._barColor(s.weight, s.capacity); }
    if (range && range !== document.activeElement) range.value = s.weight;
    if (winp  && winp  !== document.activeElement) winp.value  = Math.round(s.weight);
  }

  /* ── Carte bobine ────────────────────────────────────────────────────── */
  _spoolCard(s, thr) {
    const isSel = s.entity_id === this._selected;
    const isLow = s.weight < thr && s.weight >= 0;
    const pct   = this._pct(s.weight, s.capacity);
    const bc    = this._barColor(s.weight, s.capacity);

    const card = document.createElement("div");
    card.className = "tt-spool" + (isSel ? " selected" : "") + (isLow ? " low-stock" : "");
    card.dataset.eid = s.entity_id;

    const imgWrap = document.createElement("div");
    imgWrap.className = "tt-spool-img-wrap";
    if (s.img_url) {
      const img = document.createElement("img");
      img.className = "tt-spool-img"; img.src = s.img_url; img.loading = "lazy";
      img.onerror = () => { imgWrap.removeChild(img); imgWrap.appendChild(this._colorDiv(s, "tt-spool-color")); };
      imgWrap.appendChild(img);
    } else {
      imgWrap.appendChild(this._colorDiv(s, "tt-spool-color"));
    }
    // Badge twin avec logo chaîne
    if (s.has_twin) {
      const dot = document.createElement("div");
      dot.className = "tt-twin-dot"; dot.title = "Twin Tag — 2 puces RFID";
      dot.innerHTML = LINK_SVG + `<span>2×</span>`;
      imgWrap.appendChild(dot);
    }
    card.appendChild(imgWrap);

    // Emplacement AMS — nom court depuis hass.states si possible
    let amsLabel = null;
    if (s.ams_entity && this._hass && this._hass.states[s.ams_entity]) {
      const trayState = this._hass.states[s.ams_entity];
      amsLabel = trayState.attributes.friendly_name || s.ams_entity;
      // Raccourcir : "P2S AMS 1 Emplacement 1" → "P2S T1"
      amsLabel = amsLabel.replace(/emplacement\s*/i, "T").replace(/\s+/g, " ").trim();
    }

    const body = document.createElement("div");
    body.className = "tt-spool-body";
    // On affiche toujours le badge TigerTag+/TigerTag ET le lieu si défini
    const locBadge = amsLabel
      ? `<span class="tt-tag tt-tag-ams" title="${this._esc(s.ams_entity || '')}">${this._esc(amsLabel)}</span>`
      : s.room
        ? `<span class="tt-tag tt-tag-room">${this._esc(s.room)}</span>`
        : "";
    const typeBadge = `<span class="tt-tag ${s.is_plus ? "tt-tag-plus" : "tt-tag-base"}">${s.is_plus ? "TigerTag+" : "TigerTag"}</span>`;
    const badge = locBadge || typeBadge;  // priorité au lieu, fallback sur type
    // Ligne de badges : type (TigerTag+/TigerTag) + lieu si défini
    const allBadges = locBadge 
      ? typeBadge + locBadge 
      : typeBadge;
    body.innerHTML = `
      <div class="tt-spool-name">${this._esc(s.name)}</div>
      <div class="tt-spool-sub">${this._esc(s.material)}${s.brand ? " · " + this._esc(s.brand) : ""}</div>
      <div class="tt-spool-foot" style="flex-wrap:wrap;gap:3px"><span class="tt-spool-weight">${Math.round(s.weight)} g</span><span style="display:flex;gap:3px;flex-wrap:wrap">${allBadges}</span></div>
      <div class="tt-bar"><div class="tt-bar-fill" style="width:${pct}%;background:${bc}"></div></div>`;
    card.appendChild(body);
    card.addEventListener("click", () => this._openPanel(s));
    return card;
  }

  /* ── Panneau ─────────────────────────────────────────────────────────── */
  _openPanel(s) {
    this._selected   = s.entity_id;
    this._editWeight = null;
    this._domPanel.innerHTML = "";
    this._domPanel.appendChild(this._buildPanel(s));
    requestAnimationFrame(() => {
      this._domOverlay.classList.add("open");
      this._domPanel.classList.add("open");
    });
    this._domGrid.querySelectorAll(".tt-spool").forEach(el =>
      el.classList.toggle("selected", el.dataset.eid === s.entity_id));
  }

  _closePanel() {
    this._selected = null; this._editWeight = null;
    this._domOverlay.classList.remove("open");
    this._domPanel.classList.remove("open");
    this._domGrid.querySelectorAll(".tt-spool").forEach(el => el.classList.remove("selected"));
  }

  _buildPanel(s) {
    const frag = document.createDocumentFragment();
    const w    = s.weight;

    // Header
    const head = document.createElement("div");
    head.className = "tt-panel-head";
    const closeBtn = document.createElement("button");
    closeBtn.className = "tt-panel-close";
    closeBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="2" y1="2" x2="12" y2="12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><line x1="12" y1="2" x2="2" y2="12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
    closeBtn.addEventListener("click", () => this._closePanel());
    const headName = document.createElement("div");
    headName.className = "tt-panel-head-name"; headName.textContent = s.name;
    head.appendChild(closeBtn); head.appendChild(headName);
    frag.appendChild(head);

    // Image
    const imgWrap = document.createElement("div");
    imgWrap.className = "tt-panel-img-wrap";
    if (s.img_url) {
      const img = document.createElement("img");
      img.className = "tt-panel-img"; img.src = s.img_url;
      img.onerror = () => { imgWrap.removeChild(img); imgWrap.appendChild(this._colorDiv(s, "tt-panel-color")); };
      imgWrap.appendChild(img);
    } else {
      imgWrap.appendChild(this._colorDiv(s, "tt-panel-color"));
    }
    const badges = document.createElement("div");
    badges.className = "tt-panel-badges";
    const b1 = document.createElement("span");
    b1.className = "tt-panel-badge";
    b1.style.cssText = s.is_plus ? "background:rgba(255,243,224,.9);color:#bf360c" : "background:rgba(232,245,233,.9);color:#1b5e20";
    b1.textContent = s.is_plus ? "TigerTag+" : "TigerTag";
    badges.appendChild(b1);
    if (s.has_twin) {
      const b2 = document.createElement("span");
      b2.className = "tt-panel-badge";
      b2.style.cssText = "background:rgba(24,95,165,.85);color:#fff;display:flex;align-items:center;gap:3px";
      b2.innerHTML = `<span style="width:10px;height:10px;display:inline-flex">${LINK_SVG}</span> 2 × RFID`;
      badges.appendChild(b2);
    }
    imgWrap.appendChild(badges);
    frag.appendChild(imgWrap);

    // Corps
    const body = document.createElement("div");
    body.className = "tt-panel-body";

    // Intro
    const tagList = [
      s.ams_entity && `<span class="tt-tag tt-tag-ams">${this._esc(this._shortAmsName(s.ams_entity))}</span>`,
      s.room       && `<span class="tt-tag tt-tag-room">${this._esc(s.room)}</span>`,
      s.is_refill  && `<span class="tt-tag tt-tag-refill">Recharge</span>`,
      s.is_recycled&& `<span class="tt-tag tt-tag-eco">Recyclé</span>`,
    ].filter(Boolean).join("");
    const intro = document.createElement("div");
    intro.innerHTML = `
      <div style="font-size:12px;color:var(--secondary-text-color);margin-bottom:${tagList?"6":"0"}px">
        ${this._esc(s.material)}${s.series?" · "+this._esc(s.series):""}${s.brand?" · "+this._esc(s.brand):""}${s.diameter?" · "+this._esc(s.diameter):""}
      </div>
      ${tagList?`<div style="display:flex;gap:4px;flex-wrap:wrap">${tagList}</div>`:""}`;
    body.appendChild(intro);

    // ── Section Poids ──
    const pct = this._pct(w, s.capacity);
    const bc  = this._barColor(w, s.capacity);
    const wSec = document.createElement("div");
    wSec.innerHTML = `<div class="tt-section-label">Poids</div>`;
    const wBox = document.createElement("div");
    wBox.className = "tt-weight-box";
    wBox.innerHTML = `
      <div class="tt-weight-top">
        <span class="tt-weight-val" id="tt-wval">${Math.round(w)} g</span>
        <span class="tt-weight-cap">${s.capacity} g total</span>
      </div>
      <div class="tt-w-bar"><div class="tt-w-bar-fill" id="tt-wbar" style="width:${pct}%;background:${bc}"></div></div>
      <input type="range" class="tt-range" id="tt-range" min="0" max="${s.capacity}" step="1" value="${w}" />
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--secondary-text-color);margin-bottom:8px">
        <span>0 g</span><span>${s.capacity} g</span>
      </div>
      <div class="tt-weight-row2">
        <input type="number" class="tt-w-input" id="tt-winput" min="0" max="${s.capacity}" step="1" value="${Math.round(w)}" />
        <button class="tt-btn-save" id="tt-save">Enregistrer</button>
      </div>
      ${s.has_twin?`<div class="tt-w-note" style="color:var(--tt-blue);display:flex;align-items:center;gap:4px"><span style="width:12px;height:12px;display:inline-flex">${LINK_SVG}</span>Twin Tag — les deux puces seront mises à jour</div>`:""}
      <div class="tt-tare-row">
        <span class="tt-tare-label">Tare (g) :</span>
        <input type="number" class="tt-tare-input" id="tt-tare" min="0" max="2000" step="1"
          value="${s.tare_custom !== null ? s.tare_custom : s.tare_official}"
          placeholder="${s.tare_official || 0}" />
        <button class="tt-btn-tare" id="tt-tare-save">Appliquer</button>
      </div>
      <div class="tt-w-note">Tare officielle TigerTag : ${s.tare_official || 0} g — tu peux l'ajuster (masterspool différent)</div>`;

    // Listeners poids — attachés directement après innerHTML, pas de rAF nécessaire
    // wBox.querySelector fonctionne car les éléments sont déjà dans le sous-arbre wBox
    wSec.appendChild(wBox);
    body.appendChild(wSec);

    const rng_   = wBox.querySelector("#tt-range");
    const winp_  = wBox.querySelector("#tt-winput");
    const saveB_ = wBox.querySelector("#tt-save");
    const tareI_ = wBox.querySelector("#tt-tare");
    const tSave_ = wBox.querySelector("#tt-tare-save");
    const wval_  = wBox.querySelector("#tt-wval");
    const wbar_  = wBox.querySelector("#tt-wbar");

    const syncW = (v) => {
      const n = Math.round(Math.max(0, Math.min(s.capacity, Number(v))));
      this._editWeight = n;
      if (wval_) wval_.textContent = n + " g";
      if (wbar_) { wbar_.style.width = this._pct(n,s.capacity)+"%"; wbar_.style.background = this._barColor(n,s.capacity); }
      if (rng_  && rng_  !== document.activeElement) rng_.value  = n;
      if (winp_ && winp_ !== document.activeElement) winp_.value = n;
    };

    if (rng_)   rng_.addEventListener("input",   e => syncW(e.target.value));
    if (winp_)  winp_.addEventListener("input",  e => syncW(e.target.value));
    if (saveB_) saveB_.addEventListener("click", () => this._saveWeight(s, saveB_));
    if (tSave_) tSave_.addEventListener("click", () => this._saveTare(s, tareI_, tSave_));

    // ── Section Emplacement ──
    const rooms    = this._getConfigLocations();
    const trayOpts = this._getBambuTrayOptions();
    const locSec   = document.createElement("div");
    locSec.innerHTML = `<div class="tt-section-label">Emplacement</div>
      <div class="tt-loc-rows">
        <div class="tt-loc-row">
          <span class="tt-loc-lbl">Pièce</span>
          <select class="tt-loc-sel" id="tt-room">
            <option value="—">Non placée</option>
            ${rooms.map(r=>`<option value="${r}"${s.room===r?" selected":""}>${this._esc(r)}</option>`).join("")}
          </select>
        </div>
        <div class="tt-loc-row">
          <span class="tt-loc-lbl">AMS / Ext.</span>
          <select class="tt-loc-sel" id="tt-ams">
            ${trayOpts.map(o=>`<option value="${o.value}"${s.ams_entity===o.value?" selected":""}>${this._esc(o.label)}</option>`).join("")}
          </select>
        </div>
        ${s.ams_entity?`<button class="tt-btn-ams" id="tt-push">Envoyer la configuration vers l'imprimante ↗</button>`:""}
      </div>`;
    body.appendChild(locSec);

    requestAnimationFrame(() => {
      const rs = locSec.querySelector("#tt-room");
      const as = locSec.querySelector("#tt-ams");
      const pb = locSec.querySelector("#tt-push");
      if (rs) rs.addEventListener("change", e => this._setRoom(s, e.target.value));
      if (as) as.addEventListener("change", e => this._setAms(s, e.target.value, locSec));
      if (pb) pb.addEventListener("click",  () => this._pushToAms(s));
    });

    // ── Températures ──
    if (s.nozzle_min || s.nozzle_max || s.bed_min || s.bed_max || s.dry_temp) {
      const tSec = document.createElement("div");
      tSec.innerHTML = `<div class="tt-section-label">Paramètres d'impression</div>
        <div class="tt-temp-grid">
          ${(s.nozzle_min||s.nozzle_max)?`<div class="tt-temp-chip"><div class="tt-temp-lbl">Buse</div><div class="tt-temp-val">${s.nozzle_min||"?"}–${s.nozzle_max||"?"} °C</div></div>`:""}
          ${(s.bed_min||s.bed_max)?`<div class="tt-temp-chip"><div class="tt-temp-lbl">Plateau</div><div class="tt-temp-val">${s.bed_min||"?"}–${s.bed_max||"?"} °C</div></div>`:""}
          ${s.dry_temp?`<div class="tt-temp-chip"><div class="tt-temp-lbl">Séchage</div><div class="tt-temp-val">${s.dry_temp} °C</div></div>`:""}
          ${s.dry_time?`<div class="tt-temp-chip"><div class="tt-temp-lbl">Durée séchage</div><div class="tt-temp-val">${s.dry_time} h</div></div>`:""}
        </div>`;
      body.appendChild(tSec);
    }

    // ── Liens ──
    const links = [
      s.link_msds&&{url:s.link_msds,label:"MSDS"},
      s.link_tds&&{url:s.link_tds,label:"TDS"},
      s.link_rohs&&{url:s.link_rohs,label:"RoHS"},
      s.link_reach&&{url:s.link_reach,label:"REACH"},
      s.link_food&&{url:s.link_food,label:"Food safe"},
      s.link_youtube&&{url:s.link_youtube,label:"Vidéo"},
    ].filter(Boolean);
    if (links.length) {
      const lSec = document.createElement("div");
      lSec.innerHTML = `<div class="tt-section-label">Documents & liens</div>
        <div class="tt-links">${links.map(l=>`<a class="tt-link-btn" href="${this._esc(l.url)}" target="_blank" rel="noopener">${l.label}</a>`).join("")}</div>`;
      body.appendChild(lSec);
    }

    // ── Détails ──
    const dRows = [["UID",s.uid],s.sku&&["SKU",s.sku],s.barcode&&["Code-barres",s.barcode]].filter(Boolean);
    if (dRows.length) {
      const dSec = document.createElement("div");
      dSec.innerHTML = `<div class="tt-section-label">Détails</div>
        ${dRows.map(([k,v])=>`<div class="tt-info-row"><span class="tt-info-k">${k}</span><span class="tt-info-v">${this._esc(String(v))}</span></div>`).join("")}`;
      body.appendChild(dSec);
    }

    frag.appendChild(body);
    return frag;
  }

  /* ── Actions ─────────────────────────────────────────────────────────── */
  async _saveWeight(s, btn) {
    const w = this._editWeight;
    if (w === null || !this._hass) return;
    if (btn) { btn.disabled = true; btn.textContent = "Sauvegarde…"; }
    try {
      await this._hass.callService("tigertag", "update_spool_weight", {
        uid: s.uid, weight: w, container_weight: s.tare || 0,
      });
      this._editWeight = null;
    } catch(e) { console.error("[TigerTagCard] saveWeight:", e); }
    finally { if (btn) { btn.disabled = false; btn.textContent = "Enregistrer"; } }
  }

  async _saveTare(s, input, btn) {
    const v = parseInt(input.value);
    if (isNaN(v) || !this._hass) return;
    btn.textContent = "…";
    try {
      await this._hass.callService("tigertag", "set_spool_tare", {
        uid: s.uid, tare: v,
      });
      // Mise à jour immédiate de l'objet spool en mémoire
      // pour que _saveWeight utilise la nouvelle tare sans avoir à
      // fermer/rouvrir le panneau
      s.tare         = v;
      s.tare_custom  = v;
    } catch(e) { console.warn("[TigerTagCard] saveTare:", e); }
    finally { btn.textContent = "Appliquer ✓"; setTimeout(() => { btn.textContent = "Appliquer"; }, 1500); }
  }

  async _setRoom(s, v) {
    if (!this._hass) return;
    try {
      await this._hass.callService("tigertag", "set_spool_room", {
        uid: s.uid, room: v === "—" ? null : v,
      });
    } catch(e) { console.error("[TigerTagCard] setRoom:", e); }
  }

  async _setAms(s, entityId, locSec) {
    s.ams_entity = entityId === "—" ? null : entityId;
    // Affiche/masque le bouton push dynamiquement
    const pb = locSec.querySelector("#tt-push");
    if (pb) pb.style.display = s.ams_entity ? "" : "none";
  }

  async _pushToAms(s) {
    if (!s.ams_entity || !this._hass) return;
    try {
      await this._hass.callService("tigertag", "set_bambu_ams_filament", {
        uid: s.uid, tray_entity_id: s.ams_entity,
      });
    } catch(e) { console.error("[TigerTagCard] pushToAms:", e); }
  }

  /* ── Utils ───────────────────────────────────────────────────────────── */
  _shortAmsName(entityId) {
    if (!entityId || !this._hass || !this._hass.states[entityId]) return entityId;
    const name = this._hass.states[entityId].attributes.friendly_name || entityId;
    return name.replace(/emplacement\s*/i,"T").trim();
  }
  _pct(w,c)      { return Math.round(Math.max(0, Math.min(100, w/(c||1000)*100))); }
  _barColor(w,c) {
    const p = this._pct(w,c);
    return p>50?"var(--success-color,#1D9E75)":p>20?"var(--warning-color,#BA7517)":"var(--error-color,#E24B4A)";
  }
  _colorDiv(s,cls) {
    const d = document.createElement("div");
    d.className = cls; d.style.background = s.color_hex+"33";
    d.innerHTML = `<svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity=".25"><circle cx="20" cy="20" r="15" stroke="var(--primary-text-color)" stroke-width="1.5"/><path d="M13 20L20 13L27 20L20 27Z" stroke="var(--primary-text-color)" stroke-width="1.5" fill="none"/></svg>`;
    return d;
  }
  _esc(s) {
    return String(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  }
}

customElements.define("tigertag-card", TigerTagCard);
window.customCards = window.customCards || [];
window.customCards.push({ type:"tigertag-card", name:"TigerTag Card", description:"Gestion inventaire filaments TigerTag", preview:false });
console.info(`%c TigerTag Card %c v${VERSION} `,"background:#1D9E75;color:#fff;font-weight:500;padding:2px 6px;border-radius:3px 0 0 3px","background:#eee;color:#333;padding:2px 6px;border-radius:0 3px 3px 0");
