/**
 * Moteur interactif du Dépliant Triptyque – Le calendrier Dunièrois de Maxime JACQUIOT
 * Architecture Agenda Professionnel : Cases larges pleine largeur par créneau horaire,
 * calcul automatique des durées (ex: ⏱️ 3h, ⏱️ 5h), tri chronologique du matin au soir,
 * et mini-rubans 14 jours (2 rangées de 7 pastilles) avec flux d'événements sans coupure.
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
 * NAVIGATION DANS LE TRIPTYQUE (Passé ◀ Aujourd'hui ▶ Avenir)
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

  const activeTabStyle = "px-4 sm:px-6 py-2 rounded-lg text-xs font-black bg-blue-600 text-white shadow-sm";
  const inactiveTabStyle = "px-3 sm:px-5 py-2 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900";

  if (tabPast) tabPast.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-1.5 ${panelName === "past" ? activeTabStyle : inactiveTabStyle}`;
  if (tabToday) tabToday.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-1.5 ${panelName === "today" ? activeTabStyle : inactiveTabStyle}`;
  if (tabFuture) tabFuture.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-1.5 ${panelName === "future" ? activeTabStyle : inactiveTabStyle}`;

  window.scrollTo({ top: 90, behavior: "smooth" });
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
 * 1. VOLET AUJOURD'HUI : TIMELINE AGENDA PRO (Lignes Larges)
 * ==============================================================
 */
function renderTodayPanel() {
  const container = document.getElementById("today-timeline-container");
  const countBadge = document.getElementById("today-event-count-badge");
  const emptyAlert = document.getElementById("today-empty-alert");
  if (!container) return;

  let todayEvents = getEventsForDate(todayDateStr).filter(matchesFilters);

  // Tri strictement chronologique du matin au soir
  todayEvents.sort((a, b) => {
    const tA = extractTiming(a).startDec;
    const tB = extractTiming(b).startDec;
    return tA - tB;
  });

  if (countBadge) countBadge.textContent = `${todayEvents.length} événement(s) en cours`;

  if (todayEvents.length === 0) {
    container.innerHTML = "";
    if (emptyAlert) emptyAlert.classList.remove("hidden");
    return;
  }

  if (emptyAlert) emptyAlert.classList.add("hidden");
  container.innerHTML = todayEvents.map(event => createAgendaProRow(event, todayDateStr)).join("");
}

/**
 * Création d'une ligne large format Agenda Professionnel
 */
function createAgendaProRow(event, isoDate) {
  const timing = extractTiming(event);
  const typeObj = extractEventType(event);
  const priceInfo = extractPrice(event);
  const title = cleanTitle(event.title);
  const catColor = getCategoryBorderColor(event.category);

  let attachmentBadge = "";
  if (event.has_attachment && event.attachment_data) {
    if (event.attachment_type === "calameo") {
      attachmentBadge = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-200">
          📖 Agenda Calaméo
        </span>
      `;
    } else if (event.attachment_type === "pdf") {
      attachmentBadge = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-rose-800 bg-rose-100 px-2 py-0.5 rounded border border-rose-200">
          📄 Arrêté PDF
        </span>
      `;
    }
  }

  return `
    <article 
      onclick="openDayPopup('${isoDate}')" 
      class="bg-white rounded-2xl border border-slate-200/90 shadow-2xs hover:shadow-md hover:border-blue-400 transition-all duration-200 overflow-hidden flex flex-col sm:flex-row items-stretch group cursor-pointer"
      title="Cliquer pour afficher la fiche complète de l'événement"
    >
      <!-- Rail Temporel Gauche (Durée & Horaires) -->
      <div class="sm:w-44 shrink-0 bg-slate-50/90 border-b sm:border-b-0 sm:border-r border-slate-100 p-3.5 sm:p-4 flex sm:flex-col justify-between items-start relative select-none">
        <div class="absolute left-0 top-0 bottom-0 w-1.5 ${catColor}"></div>
        
        <div class="pl-2">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-base sm:text-lg font-black text-slate-900 tracking-tight leading-none">${timing.start}</span>
            ${timing.end ? `<span class="text-xs text-slate-400 font-bold">➔</span><span class="text-base sm:text-lg font-black text-slate-700 leading-none">${timing.end}</span>` : ''}
          </div>

          ${timing.duration ? `
            <div class="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100/90 text-blue-900 text-[11px] font-extrabold shadow-3xs">
              <span>⏱️ Durée :</span>
              <span>${timing.duration}</span>
            </div>
          ` : ''}

          ${!timing.isExplicit ? `
            <span class="inline-flex items-center gap-1 text-[11px] font-bold text-slate-500 mt-1">
              📅 Toute la journée
            </span>
          ` : ''}
        </div>
        
        <div class="hidden sm:block pl-2 mt-auto pt-2">
          <span class="text-[11px] text-slate-400 group-hover:text-blue-600 transition flex items-center gap-1 font-bold">
            <span>Fiche</span>
            <span>➔</span>
          </span>
        </div>
      </div>

      <!-- Corps de l'Événement (Pleine Largeur sans coupure) -->
      <div class="flex-1 min-w-0 p-4 sm:p-5 flex flex-col justify-between space-y-2.5">
        
        <!-- Badges : Type + Tarif + Documents -->
        <div class="flex flex-wrap items-center gap-2">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-black bg-slate-100 text-slate-800 border border-slate-200 uppercase tracking-wide">
            <span>${typeObj.icon}</span>
            <span>${typeObj.label}</span>
          </span>

          <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-bold ${priceInfo.isFree ? 'bg-amber-100 text-amber-900 border border-amber-200' : 'bg-slate-100 text-slate-700'}">
            🎟️ ${priceInfo.text}
          </span>

          ${attachmentBadge}

          <span class="ml-auto text-[11px] text-slate-400 font-medium hidden md:inline truncate">
            ${event.source_name}
          </span>
        </div>

        <!-- Titre Pleine Largeur -->
        <h4 class="text-base sm:text-lg font-black text-slate-900 group-hover:text-blue-600 transition leading-snug">
          ${title}
        </h4>

        <!-- Résumé clair -->
        <p class="text-xs sm:text-sm text-slate-600 leading-relaxed line-clamp-2">
          ${event.summary}
        </p>

        <!-- Lieu et Appel à l'action -->
        <div class="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-100/70">
          <span class="font-medium flex items-center gap-1 truncate">
            <span>📍</span>
            <span>${event.location || "Dunières"}</span>
          </span>
          <span class="text-blue-600 font-bold group-hover:underline shrink-0">
            Détails complets ➔
          </span>
        </div>

      </div>
    </article>
  `;
}

/**
 * ==============================================================
 * 2. VOLETS PASSÉ & AVENIR : MINI-RUBAN 14j + TIMELINE AGENDA
 * ==============================================================
 */
function renderPastCalendarGrid() {
  const stripContainer = document.getElementById("past-strip-container");
  const timelineContainer = document.getElementById("past-timeline-container");
  if (!stripContainer || !timelineContainer || !todayDateStr) return;

  const pastDates = getPast14Days(todayDateStr);

  // 1. Mini-Ruban Visuel des 14 jours (2 rangées de 7 pastilles)
  stripContainer.innerHTML = pastDates.map(iso => renderMiniDayChip(iso, "past")).join("");

  // 2. Flux Chronologique des jours actifs (Lignes Larges)
  const activeDays = pastDates.filter(iso => getEventsForDate(iso).filter(matchesFilters).length > 0);

  if (activeDays.length === 0) {
    timelineContainer.innerHTML = `
      <div class="paper-panel rounded-2xl p-8 text-center text-slate-500 text-sm">
        ☀️ Aucun événement passé répertorié sur les 14 derniers jours.
      </div>
    `;
    return;
  }

  timelineContainer.innerHTML = activeDays.map(isoDate => {
    const d = parseISODate(isoDate);
    const dateFormatted = `${JOURS_SEMAINE_LONGS[d.getDay()]} ${d.getDate()} ${MOIS_LONGS[d.getMonth()]}`;
    const dayEvents = getEventsForDate(isoDate).filter(matchesFilters);
    dayEvents.sort((a, b) => extractTiming(a).startDec - extractTiming(b).startDec);

    return `
      <div id="day-section-${isoDate}" class="space-y-2.5 pt-2">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-sm font-extrabold text-slate-800 flex items-center gap-2">
            <span>📅</span>
            <span>${dateFormatted}</span>
          </h3>
          <span class="text-xs font-bold text-slate-500 bg-slate-200/80 px-2 py-0.5 rounded-full">
            ${dayEvents.length} événement(s)
          </span>
        </div>

        <div class="space-y-3">
          ${dayEvents.map(e => createAgendaProRow(e, isoDate)).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function renderFutureCalendarGrid() {
  const stripContainer = document.getElementById("future-strip-container");
  const timelineContainer = document.getElementById("future-timeline-container");
  if (!stripContainer || !timelineContainer || !todayDateStr) return;

  const futureDates = getFuture14Days(todayDateStr);

  // 1. Mini-Ruban Visuel des 14 jours (2 rangées de 7 pastilles)
  stripContainer.innerHTML = futureDates.map(iso => renderMiniDayChip(iso, "future")).join("");

  // 2. Flux Chronologique des jours actifs (Lignes Larges)
  const activeDays = futureDates.filter(iso => getEventsForDate(iso).filter(matchesFilters).length > 0);

  if (activeDays.length === 0) {
    timelineContainer.innerHTML = `
      <div class="paper-panel rounded-2xl p-8 text-center text-slate-500 text-sm">
        ☀️ Aucun événement prévisionnel programmé sur les 14 prochains jours.
      </div>
    `;
    return;
  }

  timelineContainer.innerHTML = activeDays.map(isoDate => {
    const d = parseISODate(isoDate);
    const dateFormatted = `${JOURS_SEMAINE_LONGS[d.getDay()]} ${d.getDate()} ${MOIS_LONGS[d.getMonth()]}`;
    const dayEvents = getEventsForDate(isoDate).filter(matchesFilters);
    dayEvents.sort((a, b) => extractTiming(a).startDec - extractTiming(b).startDec);

    return `
      <div id="day-section-${isoDate}" class="space-y-2.5 pt-2">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-sm font-extrabold text-slate-800 flex items-center gap-2">
            <span>📅</span>
            <span>${dateFormatted}</span>
          </h3>
          <span class="text-xs font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
            ${dayEvents.length} événement(s)
          </span>
        </div>

        <div class="space-y-3">
          ${dayEvents.map(e => createAgendaProRow(e, isoDate)).join("")}
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Pastille compacte pour le mini-ruban 14 jours
 */
function renderMiniDayChip(isoDate, mode) {
  const d = parseISODate(isoDate);
  const jourSemCourt = JOURS_SEMAINE_COURTS[d.getDay()];
  const numJour = d.getDate();
  const moisCourt = MOIS_COURTS[d.getMonth()];

  const events = getEventsForDate(isoDate).filter(matchesFilters);
  const count = events.length;
  const hasEvents = count > 0;

  let chipStyle = "bg-slate-50 text-slate-400 border-slate-200 opacity-60";
  if (hasEvents) {
    chipStyle = "bg-blue-600 text-white font-black border-blue-600 shadow-xs cursor-pointer hover:bg-blue-700 opacity-100";
  }

  return `
    <div 
      onclick="scrollToDaySection('${isoDate}')" 
      class="mini-day-chip p-2 rounded-xl border text-center select-none flex flex-col justify-between ${chipStyle}"
      title="${hasEvents ? `${count} événement(s) le ${jourSemCourt} ${numJour} ${moisCourt} - Cliquer pour voir` : `Jour calme (${jourSemCourt} ${numJour} ${moisCourt})`}"
    >
      <span class="text-[10px] font-extrabold uppercase block leading-none opacity-80">${jourSemCourt}</span>
      <span class="text-sm sm:text-base font-black block my-0.5 leading-none">${numJour}</span>
      <span class="text-[9px] block leading-none font-bold">${hasEvents ? `(${count})` : '—'}</span>
    </div>
  `;
}

function scrollToDaySection(isoDate) {
  const el = document.getElementById(`day-section-${isoDate}`);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    // Si pas d'événement dans le flux, ouvrir le popup du jour
    openDayPopup(isoDate);
  }
}

/**
 * ==============================================================
 * 3. POPUP DYNAMIQUE DU JOUR (Plein Écran)
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
  events.sort((a, b) => extractTiming(a).startDec - extractTiming(b).startDec);

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
  const timing = extractTiming(event);
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
      
      <!-- Ligne d'identification : Heure, Durée, Type & Tarif -->
      <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
        <div class="flex flex-wrap items-center gap-2">
          <span class="px-3 py-1 rounded-xl text-xs font-black bg-blue-600 text-white shadow-xs">
            🕒 ${timing.start} ${timing.end ? `➔ ${timing.end}` : ''}
          </span>
          ${timing.duration ? `
            <span class="px-2.5 py-1 rounded-xl text-xs font-black bg-blue-100 text-blue-900">
              ⏱️ ${timing.duration}
            </span>
          ` : ''}
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
            <span class="text-slate-400 block font-medium">Horaire & Durée</span>
            <span class="font-bold text-slate-800">${timing.start} ${timing.end ? `➔ ${timing.end}` : ''} ${timing.duration ? `(${timing.duration})` : ''}</span>
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
 * 4. EXTRACTION AVANCÉE DU TEMPS, DURÉES ET TARIFS
 * ==============================================================
 */
function cleanTimeStr(s) {
  return s.replace(/\s*heures?\s*/gi, 'h').replace(/\s+/g, '').trim();
}

function parseHourToDec(hStr) {
  if (!hStr) return null;
  const match = hStr.match(/(\d{1,2})[h:](\d{0,2})/i);
  if (!match) return null;
  const h = parseInt(match[1]);
  const m = match[2] ? parseInt(match[2]) : 0;
  return h + m / 60;
}

function computeDurationStr(decStart, decEnd) {
  if (!decStart || !decEnd || decEnd <= decStart) return null;
  const diff = decEnd - decStart;
  const h = Math.floor(diff);
  const m = Math.round((diff - h) * 60);
  if (m === 0) return `${h}h`;
  if (h === 0) return `${m} min`;
  return `${h}h${String(m).padStart(2, '0')}`;
}

/**
 * Extraction complète du créneau et calcul de durée
 */
function extractTiming(event) {
  const text = (event.title + ' ' + (event.summary || ''));

  // 1. Format plage "18:30 - 19:30"
  const matchColonRange = text.match(/(\d{1,2}:\d{2})\s*[-–àa]\s*(\d{1,2}:\d{2})/i);
  if (matchColonRange) {
    const sClean = matchColonRange[1].replace(':', 'h');
    const eClean = matchColonRange[2].replace(':', 'h');
    const sDec = parseHourToDec(sClean);
    const eDec = parseHourToDec(eClean);
    return {
      start: sClean,
      end: eClean,
      duration: computeDurationStr(sDec, eDec),
      startDec: sDec,
      isExplicit: true
    };
  }

  // 2. Format plage "de 14 heures à 19 heures" ou "de 9h à 12h"
  const matchRange = text.match(/(?:de|dès|entre)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))\s*(?:à|a|et|-|–)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))/i);
  if (matchRange) {
    const sClean = cleanTimeStr(matchRange[1]);
    const eClean = cleanTimeStr(matchRange[2]);
    const sDec = parseHourToDec(sClean);
    const eDec = parseHourToDec(eClean);
    return {
      start: sClean,
      end: eClean,
      duration: computeDurationStr(sDec, eDec),
      startDec: sDec,
      isExplicit: true
    };
  }

  // 3. Colon simple "18:30"
  const matchColon = text.match(/\b(\d{1,2}:\d{2})\b/);
  if (matchColon) {
    const sClean = matchColon[1].replace(':', 'h');
    const sDec = parseHourToDec(sClean);
    return { start: sClean, end: null, duration: null, startDec: sDec, isExplicit: true };
  }

  // 4. À midi
  if (/\b(?:à|a|vers)\s*midi\b/i.test(text)) {
    return { start: '12h00', end: null, duration: null, startDec: 12, isExplicit: true };
  }

  // 5. À partir de / dès / à Xh: à 7h30, à 14h, dès 20h
  const matchSingle = text.match(/(?:à|a|vers|dès|partir de)\s*(\d{1,2}(?:\s*(?:heures?|h)\s*\d{0,2}|[h:]\d{0,2}))/i);
  if (matchSingle) {
    const sClean = cleanTimeStr(matchSingle[1]);
    const sDec = parseHourToDec(sClean);
    return { start: sClean, end: null, duration: null, startDec: sDec, isExplicit: true };
  }

  // 6. Direct Xh ou XhXX même collé à des lettres : 18h30Spectacle
  const matchDirect = text.match(/(\d{1,2}h\d{2}|\d{1,2}h(?!\w))/i);
  if (matchDirect) {
    const sClean = cleanTimeStr(matchDirect[1]);
    const sDec = parseHourToDec(sClean);
    return { start: sClean, end: null, duration: null, startDec: sDec, isExplicit: true };
  }

  return { start: 'En journée', end: null, duration: null, startDec: 99, isExplicit: false };
}

/**
 * Extraction de la nature de l'activité
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

function cleanTitle(title) {
  if (!title) return "";
  let clean = title
    .replace(/deDunièresle/gi, "de Dunières le ")
    .replace(/deDunières/gi, "de Dunières ")
    .replace(/\s+/g, " ")
    .trim();

  if (/^\d{1,2}\s+[a-zéû.]+\s+\d{4}\s+\d{1,2}[:h]\d{2}/i.test(clean)) {
    clean = clean.replace(/^\d{1,2}\s+[a-zéû.]+\s+\d{4}\s+\d{1,2}[:h]\d{2}(?:\s*-\s*\d{1,2}[:h]\d{2})?\s*/i, "");
    if (!clean) clean = title;
  }
  return clean;
}

function getCategoryBorderColor(category) {
  switch (category) {
    case "Alertes & Météo":
      return "bg-rose-500";
    case "Travaux & Voirie":
      return "bg-amber-500";
    case "Vie Municipale & Délibérations":
      return "bg-blue-600";
    case "Manifestations & Vie Associative":
      return "bg-emerald-500";
    case "Culture & Patrimoine":
      return "bg-purple-600";
    case "Services & Déchets":
      return "bg-teal-500";
    default:
      return "bg-slate-400";
  }
}

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
