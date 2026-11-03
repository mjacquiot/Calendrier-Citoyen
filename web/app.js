/**
 * Moteur interactif du Dépliant Triptyque – Le calendrier Dunièrois de Maxime JACQUIOT
 * Gère la navigation triptyque, les calendriers 2x7 avec lisibilité horaire et titres nets,
 * l'ordre chronologique des événements du jour, l'identification visuelle (heures, prix, types)
 * et le popup dynamique plein écran.
 */

let appData = null;
let allEventsList = [];
let todayDateStr = "";
let currentCategory = "all";
let searchQuery = "";
let activePanel = "today"; // 'past' | 'today' | 'future'
let activePopupDate = "";

const JOURS_SEMAINE_COURTS = ["Dim.", "Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam."];
const JOURS_SEMAINE_LONGS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
const MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const MOIS_COURTS = ["Jan.", "Fév.", "Mar.", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sep.", "Oct.", "Nov.", "Déc."];

document.addEventListener("DOMContentLoaded", () => {
  initApp();

  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderAllSections();
    });
  }

  // Navigation clavier : Flèches gauche/droite pour le triptyque, Échap pour fermer le popup
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDayPopup();
    } else if (e.key === "ArrowLeft" && !isPopupOpen()) {
      navigateRelative(-1);
    } else if (e.key === "ArrowRight" && !isPopupOpen()) {
      navigateRelative(1);
    }
  });

  const modalElem = document.getElementById("day-popup-modal");
  if (modalElem) {
    modalElem.addEventListener("click", (e) => {
      if (e.target === modalElem) closeDayPopup();
    });
  }
});

/**
 * Initialisation des données depuis data.json
 */
async function initApp() {
  try {
    const res = await fetch("data.json?v=" + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    appData = await res.json();
    allEventsList = appData.all_events || [];

    if (appData.metadata && appData.metadata.reference_date) {
      todayDateStr = appData.metadata.reference_date;
    } else {
      todayDateStr = formatISODate(new Date());
    }

    updateHeaderMetadata();
    renderAllSections();
    switchPanel("today");

  } catch (err) {
    console.error("Erreur de chargement de data.json :", err);
    const container = document.getElementById("panel-today");
    if (container) {
      container.innerHTML = `
        <div class="p-8 text-center text-rose-600 bg-rose-50 rounded-2xl border border-rose-200 text-sm">
          ⚠️ Impossible de charger les données du calendrier. Veuillez réactualiser la page.
        </div>
      `;
    }
  }
}

function updateHeaderMetadata() {
  const banner = document.getElementById("today-full-title");
  if (banner && todayDateStr) {
    const d = parseISODate(todayDateStr);
    const jourSem = JOURS_SEMAINE_LONGS[d.getDay()];
    const numJour = d.getDate();
    const mois = MOIS_LONGS[d.getMonth()];
    const annee = d.getFullYear();
    banner.textContent = `Aujourd'hui à Dunières : ${jourSem} ${numJour} ${mois} ${annee}`;
  }
}

function renderAllSections() {
  renderTodayPanel();
  renderPastCalendarGrid();
  renderFutureCalendarGrid();
}

/**
 * ==============================================================
 * NAVIGATION TRIPTYQUE (Passé ◀ Aujourd'hui ▶ Avenir)
 * ==============================================================
 */
function switchPanel(panelName) {
  activePanel = panelName;

  const panelPast = document.getElementById("panel-past");
  const panelToday = document.getElementById("panel-today");
  const panelFuture = document.getElementById("panel-future");

  const tabPast = document.getElementById("tab-btn-past");
  const tabToday = document.getElementById("tab-btn-today");
  const tabFuture = document.getElementById("tab-btn-future");

  if (panelPast) panelPast.classList.toggle("hidden", panelName !== "past");
  if (panelToday) panelToday.classList.toggle("hidden", panelName !== "today");
  if (panelFuture) panelFuture.classList.toggle("hidden", panelName !== "future");

  const activeTabStyle = "px-4 sm:px-6 py-1.5 rounded-lg text-xs font-black bg-blue-600 text-white shadow-sm";
  const inactiveTabStyle = "px-3 sm:px-4 py-1.5 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900";

  if (tabPast) tabPast.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "past" ? activeTabStyle : inactiveTabStyle}`;
  if (tabToday) tabToday.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "today" ? activeTabStyle : inactiveTabStyle}`;
  if (tabFuture) tabFuture.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "future" ? activeTabStyle : inactiveTabStyle}`;

  updateSideFlaps();
  window.scrollTo({ top: 100, behavior: "smooth" });
}

function updateSideFlaps() {
  const flapLeft = document.getElementById("side-flap-left");
  const flapRight = document.getElementById("side-flap-right");
  const iconLeft = document.getElementById("side-flap-left-icon");
  const labelLeft = document.getElementById("side-flap-left-label");
  const subLeft = document.getElementById("side-flap-left-sub");
  const iconRight = document.getElementById("side-flap-right-icon");
  const labelRight = document.getElementById("side-flap-right-label");
  const subRight = document.getElementById("side-flap-right-sub");

  if (!flapLeft || !flapRight) return;

  if (activePanel === "today") {
    flapLeft.style.opacity = "1";
    flapLeft.style.pointerEvents = "auto";
    if (iconLeft) iconLeft.textContent = "⏮️";
    if (labelLeft) labelLeft.textContent = "◀ Ce qu'il s'est passé";
    if (subLeft) subLeft.textContent = "(-14 jours)";

    flapRight.style.opacity = "1";
    flapRight.style.pointerEvents = "auto";
    if (iconRight) iconRight.textContent = "⏭️";
    if (labelRight) labelRight.textContent = "Ce qui va se passer ▶";
    if (subRight) subRight.textContent = "(+14 jours)";

  } else if (activePanel === "past") {
    flapLeft.style.opacity = "0.2";
    flapLeft.style.pointerEvents = "none";

    flapRight.style.opacity = "1";
    flapRight.style.pointerEvents = "auto";
    if (iconRight) iconRight.textContent = "📍";
    if (labelRight) labelRight.textContent = "Revenir à Aujourd'hui ▶";
    if (subRight) subRight.textContent = "(En direct)";

  } else if (activePanel === "future") {
    flapLeft.style.opacity = "1";
    flapLeft.style.pointerEvents = "auto";
    if (iconLeft) iconLeft.textContent = "📍";
    if (labelLeft) labelLeft.textContent = "◀ Revenir à Aujourd'hui";
    if (subLeft) subLeft.textContent = "(En direct)";

    flapRight.style.opacity = "0.2";
    flapRight.style.pointerEvents = "none";
  }
}

function onLeftFlapClick() {
  if (activePanel === "today") switchPanel("past");
  else if (activePanel === "future") switchPanel("today");
}

function onRightFlapClick() {
  if (activePanel === "today") switchPanel("future");
  else if (activePanel === "past") switchPanel("today");
}

function navigateRelative(dir) {
  const panels = ["past", "today", "future"];
  const curIdx = panels.indexOf(activePanel);
  let nextIdx = curIdx + dir;
  if (nextIdx < 0) nextIdx = 0;
  if (nextIdx >= panels.length) nextIdx = panels.length - 1;
  switchPanel(panels[nextIdx]);
}

/**
 * ==============================================================
 * 1. VOLET AUJOURD'HUI (Chronologique, Heures, Prix & Types nets)
 * ==============================================================
 */
function renderTodayPanel() {
  const container = document.getElementById("today-cards-grid");
  const countBadge = document.getElementById("today-event-count-badge");
  const emptyAlert = document.getElementById("today-empty-alert");
  if (!container) return;

  let todayEvents = getEventsForDate(todayDateStr).filter(matchesFilters);

  // Tri par ordre chronologique
  todayEvents.sort((a, b) => extractHourOrder(a) - extractHourOrder(b));

  if (countBadge) countBadge.textContent = `${todayEvents.length} événement(s) actif(s)`;

  if (todayEvents.length === 0) {
    container.innerHTML = "";
    if (emptyAlert) emptyAlert.classList.remove("hidden");
    return;
  }

  if (emptyAlert) emptyAlert.classList.add("hidden");
  container.innerHTML = todayEvents.map(event => createHeroTodayCard(event)).join("");
}

function createHeroTodayCard(event) {
  const timeInfo = extractEventTime(event);
  const isTimeExplicit = isExplicitTime(timeInfo);
  const typeObj = extractEventType(event);
  const priceInfo = extractPrice(event);

  let attachmentBadge = "";
  if (event.has_attachment && event.attachment_data) {
    if (event.attachment_type === "calameo") {
      attachmentBadge = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-amber-300 bg-amber-400/20 px-2 py-0.5 rounded border border-amber-300/30">
          📖 Agenda Calaméo
        </span>
      `;
    } else if (event.attachment_type === "pdf") {
      attachmentBadge = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-rose-300 bg-rose-400/20 px-2 py-0.5 rounded border border-rose-300/30">
          📄 Arrêté PDF
        </span>
      `;
    }
  }

  const imageHtml = event.image_url ? `
    <div class="h-44 w-full overflow-hidden bg-slate-800 relative">
      <img src="${event.image_url}" alt="${cleanTitle(event.title)}" class="w-full h-full object-cover transition-transform duration-300 hover:scale-105" loading="lazy">
      <div class="absolute top-2.5 right-2.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-black/70 backdrop-blur text-white">
        ${event.badge || "En vigueur"}
      </div>
    </div>
  ` : "";

  return `
    <article class="bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 overflow-hidden flex flex-col justify-between hover:bg-white/15 transition shadow-lg">
      <div>
        ${imageHtml}
        <div class="p-5 space-y-3">
          
          <!-- Bandeau Identifiable : Horaire + Type + Tarif -->
          <div class="flex flex-wrap items-center gap-2">
            <!-- Horaire bien visible -->
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-black shadow-xs ${isTimeExplicit ? 'bg-emerald-500 text-slate-950 font-black' : 'bg-blue-600/60 text-white'}">
              🕒 ${timeInfo}
            </span>

            <!-- Type / Ce que c'est -->
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs font-black bg-white/20 text-white uppercase tracking-wider">
              <span>${typeObj.icon}</span>
              <span>${typeObj.label}</span>
            </span>

            <!-- Prix / Tarif -->
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs font-extrabold ${priceInfo.isFree ? 'bg-amber-400 text-slate-950' : 'bg-white/10 text-slate-200'}">
              🎟️ ${priceInfo.text}
            </span>
          </div>

          <!-- Titre principal net -->
          <h3 class="text-base sm:text-lg font-black text-white leading-snug cursor-pointer hover:text-blue-300 transition" onclick="openDayPopup('${todayDateStr}')">
            ${cleanTitle(event.title)}
          </h3>

          <!-- Résumé -->
          <p class="text-xs sm:text-sm text-blue-100/90 leading-relaxed line-clamp-3">
            ${event.summary}
          </p>

          <!-- Lieu -->
          <div class="flex items-center gap-1 text-xs text-blue-200 font-medium">
            <span>📍</span>
            <span class="truncate">${event.location || "Dunières"}</span>
          </div>
        </div>
      </div>

      <div class="p-4 bg-black/25 border-t border-white/10 flex items-center justify-between gap-2 mt-auto">
        <div>${attachmentBadge}</div>
        <button onclick="openDayPopup('${todayDateStr}')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white text-blue-950 hover:bg-blue-50 transition shadow-sm flex items-center gap-1">
          <span>Fiche complète</span>
          <span>➔</span>
        </button>
      </div>
    </article>
  `;
}

/**
 * ==============================================================
 * 2. VOLETS PASSÉ & AVENIR : CALENDRIERS 2x7 VISIBLES & NETS
 * ==============================================================
 */
function renderPastCalendarGrid() {
  const container = document.getElementById("past-grid-container");
  const headersContainer = document.getElementById("past-col-headers");
  if (!container || !todayDateStr) return;

  const pastDates = getPast14Days(todayDateStr);

  if (headersContainer && pastDates.length >= 7) {
    const first7 = pastDates.slice(0, 7);
    headersContainer.innerHTML = first7.map(iso => {
      const d = parseISODate(iso);
      return `<div>${JOURS_SEMAINE_COURTS[d.getDay()]}</div>`;
    }).join("");
  }

  container.innerHTML = pastDates.map((isoDate, index) => renderCalendarCell(isoDate, index, "past")).join("");
}

function renderFutureCalendarGrid() {
  const container = document.getElementById("future-grid-container");
  const headersContainer = document.getElementById("future-col-headers");
  if (!container || !todayDateStr) return;

  const futureDates = getFuture14Days(todayDateStr);

  if (headersContainer && futureDates.length >= 7) {
    const first7 = futureDates.slice(0, 7);
    headersContainer.innerHTML = first7.map(iso => {
      const d = parseISODate(iso);
      return `<div>${JOURS_SEMAINE_COURTS[d.getDay()]}</div>`;
    }).join("");
  }

  container.innerHTML = futureDates.map((isoDate, index) => renderCalendarCell(isoDate, index, "future")).join("");
}

/**
 * Rendu d'une cellule journalière 2x7 : Heure et Événement parfaitement lisibles
 */
function renderCalendarCell(isoDate, index, mode) {
  const d = parseISODate(isoDate);
  const jourSemCourt = JOURS_SEMAINE_COURTS[d.getDay()];
  const numJour = d.getDate();
  const moisCourt = MOIS_COURTS[d.getMonth()];

  const events = getEventsForDate(isoDate).filter(matchesFilters);
  const count = events.length;
  const hasEvents = count > 0;

  let cellBg = "bg-white border-slate-200 hover:border-slate-400";
  let badgeColor = "bg-slate-100 text-slate-400";

  if (hasEvents) {
    cellBg = "bg-white border-blue-400 ring-2 ring-blue-500/10 shadow-sm hover:border-blue-600";
    badgeColor = "bg-blue-600 text-white font-black shadow-2xs";
  }

  // Contenu des événements : Heure + Titre lisibles en un coup d'œil
  let eventsListHtml = "";
  if (!hasEvents) {
    eventsListHtml = `
      <div class="flex-1 flex items-center justify-center py-4 text-slate-300 font-mono text-sm select-none">
        —
      </div>
    `;
  } else {
    eventsListHtml = `
      <div class="space-y-1.5 flex-1 flex flex-col justify-start my-1.5">
        ${events.slice(0, 2).map(e => {
          const time = extractEventTime(e);
          const isExplicit = isExplicitTime(time);
          const typeObj = extractEventType(e);
          const title = cleanTitle(e.title);

          return `
            <div class="p-1.5 rounded-xl bg-slate-50 border border-slate-200/90 hover:bg-blue-50/70 hover:border-blue-300 transition">
              <!-- Ligne 1 : Heure nette & Type -->
              <div class="flex items-center justify-between gap-1 mb-1">
                <span class="inline-flex items-center gap-1 text-[10px] font-black px-1.5 py-0.5 rounded-md shadow-2xs ${isExplicit ? 'bg-emerald-600 text-white' : 'bg-blue-600 text-white'}">
                  🕒 ${time}
                </span>
                <span class="text-xs" title="${typeObj.label}">${typeObj.icon}</span>
              </div>
              
              <!-- Ligne 2 : Titre enveloppé sans coupure brute -->
              <div class="text-[11px] font-bold text-slate-900 leading-snug line-clamp-2">
                ${title}
              </div>
            </div>
          `;
        }).join("")}

        ${count > 2 ? `
          <div class="text-[10px] font-black text-blue-600 text-center bg-blue-50 py-0.5 rounded-md border border-blue-100">
            + ${count - 2} autre(s)
          </div>
        ` : ""}
      </div>
    `;
  }

  return `
    <div 
      onclick="openDayPopup('${isoDate}')" 
      class="day-cell p-2.5 rounded-2xl border flex flex-col justify-between cursor-pointer select-none transition ${cellBg}"
      title="Cliquer pour afficher la fiche détaillée du ${jourSemCourt} ${numJour} ${moisCourt}"
    >
      <!-- En-tête date net -->
      <div class="flex items-center justify-between pb-1.5 border-b ${hasEvents ? 'border-blue-100' : 'border-slate-100'}">
        <div class="flex items-baseline gap-1.5">
          <span class="text-[11px] font-black uppercase tracking-wider ${hasEvents ? 'text-blue-700' : 'text-slate-400'}">
            ${jourSemCourt}
          </span>
          <span class="text-base sm:text-lg font-black ${hasEvents ? 'text-slate-900' : 'text-slate-600'}">
            ${numJour}
          </span>
          <span class="text-[10px] font-semibold text-slate-400">
            ${moisCourt}
          </span>
        </div>
        ${hasEvents ? `<span class="text-[10px] px-1.5 py-0.2 rounded-full ${badgeColor}">${count}</span>` : ''}
      </div>

      <!-- Corps : Heure & Titre -->
      ${eventsListHtml}

      <!-- Pied : Indication discrète si événement -->
      ${hasEvents ? `
        <div class="pt-1 border-t border-blue-100/60 flex items-center justify-end text-[10px] font-bold text-blue-600 gap-1">
          <span>Détail</span>
          <span>➔</span>
        </div>
      ` : ''}
    </div>
  `;
}

/**
 * ==============================================================
 * 3. POPUP DYNAMIQUE DU JOUR (Prend toute la place de l'écran)
 * ==============================================================
 */
function openDayPopup(isoDate) {
  activePopupDate = isoDate;
  const modal = document.getElementById("day-popup-modal");
  const card = document.getElementById("day-popup-card");
  const title = document.getElementById("day-popup-date-title");
  const badge = document.getElementById("day-popup-badge");
  const countBadge = document.getElementById("day-popup-count-badge");
  const subtitle = document.getElementById("day-popup-subtitle");
  const body = document.getElementById("day-popup-body");

  if (!modal || !body) return;

  const d = parseISODate(isoDate);
  const jourSem = JOURS_SEMAINE_LONGS[d.getDay()];
  const numJour = d.getDate();
  const mois = MOIS_LONGS[d.getMonth()];
  const annee = d.getFullYear();
  const dateFormatted = `${jourSem} ${numJour} ${mois} ${annee}`;

  if (title) title.textContent = dateFormatted;

  if (badge) {
    if (isoDate === todayDateStr) {
      badge.textContent = "📍 AUJOURD'HUI (Direct)";
      badge.className = "px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider bg-emerald-500/30 text-emerald-200 border border-emerald-400/40";
    } else if (isoDate < todayDateStr) {
      badge.textContent = "⏮️ Rétrospective passée";
      badge.className = "px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider bg-slate-500/30 text-slate-200 border border-slate-400/30";
    } else {
      badge.textContent = "⏭️ Calendrier prévisionnel";
      badge.className = "px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider bg-blue-500/30 text-blue-200 border border-blue-400/40";
    }
  }

  let events = getEventsForDate(isoDate).filter(matchesFilters);
  events.sort((a, b) => extractHourOrder(a) - extractHourOrder(b));

  if (countBadge) countBadge.textContent = `${events.length} événement(s)`;

  if (subtitle) {
    subtitle.textContent = events.length > 0 
      ? `Retrouvez ci-dessous le détail horaire, les tarifs et les documents de cette journée.` 
      : `Aucun événement ni arrêté n'a été publié pour cette date.`;
  }

  if (events.length === 0) {
    body.innerHTML = `
      <div class="py-12 text-center space-y-3 bg-white rounded-2xl border border-slate-200 p-6">
        <span class="text-4xl block">☀️</span>
        <h4 class="text-base font-bold text-slate-800">Aucun événement répertorié le ${dateFormatted}</h4>
        <p class="text-xs text-slate-500 max-w-sm mx-auto">
          Aucune manifestation associative, alerte ou travaux n'ont été signalés pour ce jour à Dunières et ses environs.
        </p>
        <div class="pt-3">
          <button onclick="navigatePopupDay(1)" class="px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 text-white hover:bg-blue-500 transition">
            Consulter le jour suivant ➔
          </button>
        </div>
      </div>
    `;
  } else {
    body.innerHTML = events.map(event => createDetailedDayEventCard(event)).join("");
  }

  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.remove("opacity-0");
    card.classList.remove("scale-95");
  }, 10);
  document.body.style.overflow = "hidden";
}

function closeDayPopup() {
  const modal = document.getElementById("day-popup-modal");
  const card = document.getElementById("day-popup-card");
  if (!modal) return;

  modal.classList.add("opacity-0");
  card.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
    activePopupDate = "";
  }, 200);
}

function isPopupOpen() {
  const modal = document.getElementById("day-popup-modal");
  return modal && !modal.classList.contains("hidden");
}

function navigatePopupDay(dir) {
  if (!activePopupDate) return;
  const d = parseISODate(activePopupDate);
  d.setDate(d.getDate() + dir);
  const nextIso = formatISODate(d);
  openDayPopup(nextIso);
}

function createDetailedDayEventCard(event) {
  const timeInfo = extractEventTime(event);
  const isTimeExplicit = isExplicitTime(timeInfo);
  const typeObj = extractEventType(event);
  const priceInfo = extractPrice(event);
  const dateStr = formatEventDate(event.dates, true);
  const title = cleanTitle(event.title);

  let attachmentHtml = "";
  if (event.has_attachment && event.attachment_data) {
    if (event.attachment_type === "calameo") {
      attachmentHtml = `
        <div class="p-4 rounded-2xl bg-amber-50 border border-amber-200/80 space-y-2.5">
          <div class="flex items-center gap-2">
            <span class="text-xl">📖</span>
            <span class="text-xs font-black text-amber-950 uppercase tracking-wide">
              Document officiel Calaméo résolu
            </span>
          </div>
          <p class="text-xs text-amber-900 leading-relaxed">
            ${event.attachment_data.enriched_text ? event.attachment_data.enriched_text.slice(0, 180) + '...' : "Cet événement dispose d'une publication Calaméo complète."}
          </p>
          <a 
            href="${event.attachment_data.original_url || event.source_url}" 
            target="_blank" 
            rel="noopener" 
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-sm transition"
          >
            <span>Feuilleter l'agenda complet sur Calaméo</span>
            <span>↗</span>
          </a>
        </div>
      `;
    } else if (event.attachment_type === "pdf") {
      attachmentHtml = `
        <div class="p-4 rounded-2xl bg-rose-50 border border-rose-200/80 space-y-2.5">
          <div class="flex items-center gap-2">
            <span class="text-xl">📄</span>
            <span class="text-xs font-black text-rose-950 uppercase tracking-wide">
              Arrêté Municipal ou Document Réglementaire PDF
            </span>
          </div>
          <p class="text-xs text-rose-900 leading-relaxed">
            Le texte officiel de l'arrêté ou de la délibération municipale a été analysé.
          </p>
          <a 
            href="${event.attachment_data.original_url || event.source_url}" 
            target="_blank" 
            rel="noopener" 
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white shadow-sm transition"
          >
            <span>Consulter l'arrêté officiel (PDF)</span>
            <span>↗</span>
          </a>
        </div>
      `;
    }
  }

  const imageHtml = event.image_url ? `
    <div class="h-48 sm:h-56 w-full rounded-2xl overflow-hidden bg-slate-900 mb-4 shadow">
      <img src="${event.image_url}" alt="${title}" class="w-full h-full object-cover">
    </div>
  ` : "";

  return `
    <article class="bg-white rounded-3xl p-5 sm:p-6 border border-slate-200 shadow-xs space-y-4">
      
      <!-- Ligne d'identification : Heure, Type & Tarif -->
      <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
        <div class="flex flex-wrap items-center gap-2">
          <span class="px-3 py-1 rounded-xl text-xs font-black ${isTimeExplicit ? 'bg-emerald-600 text-white shadow-xs' : 'bg-blue-600 text-white'}">
            🕒 ${timeInfo}
          </span>
          <span class="px-2.5 py-1 rounded-xl text-xs font-black bg-slate-100 text-slate-800 uppercase tracking-wide flex items-center gap-1">
            <span>${typeObj.icon}</span>
            <span>${typeObj.label}</span>
          </span>
          <span class="px-2.5 py-1 rounded-xl text-xs font-bold ${priceInfo.isFree ? 'bg-amber-100 text-amber-900 border border-amber-200' : 'bg-slate-100 text-slate-700'}">
            🎟️ ${priceInfo.text}
          </span>
        </div>
        <span class="text-xs font-semibold text-slate-400">
          Source : <span class="text-slate-700 font-bold">${event.source_name}</span>
        </span>
      </div>

      ${imageHtml}

      <h4 class="text-lg sm:text-xl font-black text-slate-900 leading-snug">
        ${title}
      </h4>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-100 text-xs">
        <div class="flex items-center gap-2.5">
          <span class="text-lg">🕒</span>
          <div>
            <span class="text-slate-400 block font-medium">Horaire précis</span>
            <span class="font-bold text-slate-800">${timeInfo}</span>
          </div>
        </div>
        <div class="flex items-center gap-2.5">
          <span class="text-lg">📍</span>
          <div>
            <span class="text-slate-400 block font-medium">Lieu</span>
            <span class="font-bold text-slate-800">${event.location || "Dunières"}</span>
          </div>
        </div>
        <div class="flex items-center gap-2.5 sm:col-span-2">
          <span class="text-lg">📅</span>
          <div>
            <span class="text-slate-400 block font-medium">Période concernée</span>
            <span class="font-bold text-slate-800">${dateStr}</span>
          </div>
        </div>
      </div>

      <div class="space-y-1.5">
        <h5 class="text-xs font-black uppercase tracking-wider text-slate-400">Descriptif complet</h5>
        <p class="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
          ${event.summary}
        </p>
      </div>

      ${attachmentHtml}

      <div class="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
        <a 
          href="${event.source_url}" 
          target="_blank" 
          rel="noopener" 
          class="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 transition"
        >
          <span>🔗 Voir la publication officielle originale</span>
          <span>↗</span>
        </a>

        <button 
          onclick="shareSpecificEvent('${title.replace(/'/g, "\\'")}', '${event.source_url}')" 
          class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1"
        >
          <span>📤 Partager</span>
        </button>
      </div>

    </article>
  `;
}

/**
 * ==============================================================
 * 4. FONCTIONS UTILITAIRES DE GESTION DES DATES & TEMPS
 * ==============================================================
 */
function getPast14Days(refDateStr) {
  const ref = parseISODate(refDateStr);
  const days = [];
  for (let offset = -14; offset <= -1; offset++) {
    const d = new Date(ref);
    d.setDate(ref.getDate() + offset);
    days.push(formatISODate(d));
  }
  return days;
}

function getFuture14Days(refDateStr) {
  const ref = parseISODate(refDateStr);
  const days = [];
  for (let offset = 1; offset <= 14; offset++) {
    const d = new Date(ref);
    d.setDate(ref.getDate() + offset);
    days.push(formatISODate(d));
  }
  return days;
}

function getEventsForDate(isoDate) {
  if (!allEventsList || !isoDate) return [];

  return allEventsList.filter(e => {
    if (!e.dates || !e.dates.start) return false;
    const start = e.dates.start.split("T")[0];
    const end = e.dates.end ? e.dates.end.split("T")[0] : start;
    return isoDate >= start && isoDate <= end;
  });
}

function cleanTimeStr(s) {
  return s.replace(/\s*heures?\s*/gi, 'h').replace(/\s+/g, '').trim();
}

/**
 * Extraction des horaires avec robustesse maximale
 */
function extractEventTime(event) {
  const text = (event.title + ' ' + (event.summary || ''));

  // 1. Plage avec deux points : 18:30 - 19:30
  const matchColonRange = text.match(/(\d{1,2}:\d{2})\s*[-–àa]\s*(\d{1,2}:\d{2})/i);
  if (matchColonRange) return `${matchColonRange[1]} - ${matchColonRange[2]}`;

  // 2. Plage "de X à Y" (avec "heures" ou "h")
  const matchRange = text.match(/(?:de|dès|entre)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))\s*(?:à|a|et|-|–)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))/i);
  if (matchRange) return `${cleanTimeStr(matchRange[1])} - ${cleanTimeStr(matchRange[2])}`;

  // 3. Colonne simple : 18:30
  const matchColon = text.match(/\b(\d{1,2}:\d{2})\b/);
  if (matchColon) return matchColon[1];

  // 4. À midi
  if (/\b(?:à|a|vers)\s*midi\b/i.test(text)) return '12h00';

  // 5. À partir de / dès / à Xh: à 7h30, à 14h, dès 20h
  const matchSingle = text.match(/(?:à|a|vers|dès|partir de)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))/i);
  if (matchSingle) return cleanTimeStr(matchSingle[1]);

  // 6. Direct Xh ou XhXX même collé à des lettres : 18h30Spectacle
  const matchDirect = text.match(/(\d{1,2}h\d{2}|\d{1,2}h(?!\w))/i);
  if (matchDirect) return cleanTimeStr(matchDirect[1]);

  return 'En journée';
}

function isExplicitTime(timeStr) {
  return timeStr && timeStr !== 'En journée' && /\d/.test(timeStr);
}

/**
 * Calcule un ordre horaire décimal pour le tri chronologique
 */
function extractHourOrder(e) {
  const time = extractEventTime(e);
  if (!isExplicitTime(time)) return 99; // Placé en fin de journée

  const matchFirst = time.match(/(\d{1,2})[h:](\d{0,2})/i);
  if (matchFirst) {
    const h = parseInt(matchFirst[1]);
    const m = matchFirst[2] ? parseInt(matchFirst[2]) : 0;
    return h + m / 60;
  }
  return 99;
}

/**
 * Extraction du type et de la nature de l'événement ("Ce que ça va être")
 */
function extractEventType(e) {
  const text = (e.title + ' ' + (e.summary || '') + ' ' + (e.category || '')).toLowerCase();

  if (text.includes('spectacle') || text.includes('théâtre') || text.includes('conte') || text.includes('cinéma')) {
    return { icon: '🎭', label: 'Spectacle & Culture' };
  }
  if (text.includes('randonnée') || text.includes('rando') || text.includes('pétanque') || text.includes('cross') || text.includes('sport') || text.includes('course')) {
    return { icon: '🥾', label: 'Sport & Randonnée' };
  }
  if (text.includes('repas') || text.includes('cuisine') || text.includes('chef') || text.includes('dégustation') || text.includes('champignons')) {
    return { icon: '🍽️', label: 'Gastronomie & Repas' };
  }
  if (text.includes('travaux') || text.includes('arrêté') || text.includes('voirie') || text.includes('opah') || text.includes('chantier') || text.includes('sècheresse')) {
    return { icon: '🚧', label: 'Travaux & Arrêté' };
  }
  if (text.includes('permanence') || text.includes('mairie') || text.includes('déchets') || text.includes('mda') || text.includes('service public') || text.includes('conseil municipal')) {
    return { icon: '🤝', label: 'Permanence & Service' };
  }
  if (text.includes('halloween') || text.includes('fête') || text.includes('animation') || text.includes('loto') || text.includes('marché')) {
    return { icon: '🎉', label: 'Fête & Animation' };
  }
  if (text.includes('bibliothèque') || text.includes('médiathèque') || text.includes('livre') || text.includes('exposition')) {
    return { icon: '📚', label: 'Médiathèque & Lecture' };
  }
  return { icon: '🏛️', label: 'Information locale' };
}

/**
 * Extraction des informations de prix / tarifs
 */
function extractPrice(e) {
  const text = (e.title + ' ' + (e.summary || '')).toLowerCase();

  if (text.includes('gratuit') || text.includes('entrée libre') || text.includes('entree libre') || text.includes('accès libre') || text.includes('sans rendez-vous')) {
    return { text: 'Gratuit / Entrée libre', isFree: true };
  }
  const matchPrice = text.match(/(?:tarif|prix|inscription|entrée)\s*[:de\s]*(\d+[\s]*(?:€|euros?))/i);
  if (matchPrice) return { text: matchPrice[1], isFree: false };

  const matchEuro = text.match(/\b(\d+[\s]*(?:€|euros?))\b/i);
  if (matchEuro) return { text: matchEuro[1], isFree: false };

  return { text: 'Entrée libre', isFree: false };
}

/**
 * Nettoyage des titres pour une meilleure lisibilité
 */
function cleanTitle(title) {
  if (!title) return "";
  let clean = title
    .replace(/deDunièresle/gi, "de Dunières le ")
    .replace(/deDunières/gi, "de Dunières ")
    .replace(/\s+/g, " ")
    .trim();

  // Nettoyage des formats type "6 nov. 2026 18:30 - 19:30" quand répétés dans le titre
  if (/^\d{1,2}\s+[a-zéû.]+\s+\d{4}\s+\d{1,2}[:h]\d{2}/i.test(clean)) {
    clean = clean.replace(/^\d{1,2}\s+[a-zéû.]+\s+\d{4}\s+\d{1,2}[:h]\d{2}(?:\s*-\s*\d{1,2}[:h]\d{2})?\s*/i, "");
    if (!clean) clean = title;
  }
  return clean;
}

function matchesFilters(event) {
  const matchCat = currentCategory === "all" || event.category === currentCategory;
  const matchSearch = !searchQuery || 
    event.title.toLowerCase().includes(searchQuery) ||
    (event.summary && event.summary.toLowerCase().includes(searchQuery)) ||
    (event.location && event.location.toLowerCase().includes(searchQuery)) ||
    (event.badge && event.badge.toLowerCase().includes(searchQuery));

  return matchCat && matchSearch;
}

function setCategoryFilter(cat) {
  currentCategory = cat;
  document.querySelectorAll(".cat-pill").forEach(pill => {
    if (pill.dataset.category === cat) {
      pill.className = "cat-pill shrink-0 px-3 py-1.5 rounded-lg font-bold bg-slate-900 text-white shadow-sm";
    } else {
      pill.className = "cat-pill shrink-0 px-3 py-1.5 rounded-lg font-medium bg-white text-slate-700 border border-slate-200 hover:bg-slate-100";
    }
  });

  renderAllSections();
}

function formatEventDate(dates, full = false) {
  if (!dates || !dates.start) return "Date à préciser";
  const dStart = parseISODate(dates.start);
  const options = full ? { weekday: "long", day: "numeric", month: "long" } : { day: "numeric", month: "short" };

  if (dates.is_period && dates.end) {
    const dEnd = parseISODate(dates.end);
    return `Du ${dStart.toLocaleDateString("fr-FR", options)} au ${dEnd.toLocaleDateString("fr-FR", options)}`;
  }
  return dStart.toLocaleDateString("fr-FR", options);
}

function parseISODate(isoStr) {
  if (!isoStr) return new Date();
  const parts = isoStr.split("T")[0].split("-");
  if (parts.length === 3) {
    return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  }
  return new Date(isoStr);
}

function formatISODate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shareSpecificEvent(title, url) {
  if (navigator.share) {
    navigator.share({ title: title, url: url }).catch(() => {});
  } else {
    navigator.clipboard.writeText(`${title} : ${url}`);
    alert("Lien copié dans votre presse-papier !");
  }
}
