/**
 * Moteur interactif du Dépliant Triptyque – Portail Citoyen de Dunières.
 * Gère la navigation triptyque (Passé -14j, Aujourd'hui, Avenir +14j),
 * les volets latéraux pliés 3D, les calendriers 2x7 et le popup plein écran.
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

// Initialisation au chargement de la page
document.addEventListener("DOMContentLoaded", () => {
  initApp();

  // Écouteur de recherche en direct
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

  // Clic en dehors de la carte popup pour fermer
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

    // Date de référence (défaut ou metadata)
    if (appData.metadata && appData.metadata.reference_date) {
      todayDateStr = appData.metadata.reference_date;
    } else {
      todayDateStr = formatISODate(new Date());
    }

    updateHeaderMetadata();
    renderAllSections();

    // Démarrage sur le volet Aujourd'hui
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

/**
 * Mise à jour de l'en-tête (date d'actualisation)
 */
function updateHeaderMetadata() {
  if (!appData || !appData.metadata) return;

  if (appData.metadata.generated_at) {
    const d = new Date(appData.metadata.generated_at);
    const dateFormatted = d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    const timeFormatted = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const badge = document.getElementById("header-update-time");
    if (badge) badge.textContent = `• Actualisé le ${dateFormatted} à ${timeFormatted}`;
  }

  // Titre Aujourd'hui
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

/**
 * Rendu complet de toutes les sections
 */
function renderAllSections() {
  renderTodayPanel();
  renderPastCalendarGrid();
  renderFutureCalendarGrid();
  renderGlobalDirectory();
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

  // Masquer / afficher les volets
  if (panelPast) panelPast.classList.toggle("hidden", panelName !== "past");
  if (panelToday) panelToday.classList.toggle("hidden", panelName !== "today");
  if (panelFuture) panelFuture.classList.toggle("hidden", panelName !== "future");

  // Styles des onglets du triptyque
  const activeTabStyle = "px-4 sm:px-6 py-2 rounded-xl text-xs font-black bg-blue-600 text-white shadow-md";
  const inactiveTabStyle = "px-3 sm:px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900";

  if (tabPast) tabPast.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "past" ? activeTabStyle : inactiveTabStyle}`;
  if (tabToday) tabToday.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "today" ? activeTabStyle : inactiveTabStyle}`;
  if (tabFuture) tabFuture.className = `triptych-tab flex-1 sm:flex-initial transition flex items-center justify-center gap-2 ${panelName === "future" ? activeTabStyle : inactiveTabStyle}`;

  // Mise à jour des volets pliés latéraux 3D (flaps)
  updateSideFlaps();

  // Remonter en douceur en haut du contenu
  window.scrollTo({ top: 110, behavior: "smooth" });
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
    // Volet central ouvert : les deux côtés montrent les pages pliées
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
    // Volet Passé ouvert : la gauche est au bout, la droite permet de revenir à Aujourd'hui
    flapLeft.style.opacity = "0.2";
    flapLeft.style.pointerEvents = "none";

    flapRight.style.opacity = "1";
    flapRight.style.pointerEvents = "auto";
    if (iconRight) iconRight.textContent = "📍";
    if (labelRight) labelRight.textContent = "Revenir à Aujourd'hui ▶";
    if (subRight) subRight.textContent = "(En direct)";

  } else if (activePanel === "future") {
    // Volet Avenir ouvert : la gauche permet de revenir à Aujourd'hui, la droite est au bout
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
  if (activePanel === "today") {
    switchPanel("past");
  } else if (activePanel === "future") {
    switchPanel("today");
  }
}

function onRightFlapClick() {
  if (activePanel === "today") {
    switchPanel("future");
  } else if (activePanel === "past") {
    switchPanel("today");
  }
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
 * 1. VOLET AUJOURD'HUI (Direct & Événements en cours)
 * ==============================================================
 */
function renderTodayPanel() {
  const container = document.getElementById("today-cards-grid");
  const countBadge = document.getElementById("today-event-count-badge");
  const emptyAlert = document.getElementById("today-empty-alert");
  if (!container) return;

  const todayEvents = getEventsForDate(todayDateStr).filter(matchesFilters);

  if (countBadge) countBadge.textContent = `${todayEvents.length} événement(s) en cours`;

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
  const catBadgeClass = getCategoryBadgeClass(event.category);

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
      <img src="${event.image_url}" alt="${event.title}" class="w-full h-full object-cover transition-transform duration-300 hover:scale-105" loading="lazy">
      <div class="absolute top-2.5 right-2.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-black/70 backdrop-blur text-white">
        ${event.badge || "En vigueur"}
      </div>
    </div>
  ` : "";

  return `
    <article class="bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 overflow-hidden flex flex-col justify-between hover:bg-white/15 transition shadow-lg">
      <div>
        ${imageHtml}
        <div class="p-5">
          <div class="flex items-center justify-between gap-2 mb-2">
            <span class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md ${catBadgeClass}">
              ${event.category}
            </span>
            <span class="text-xs font-bold text-emerald-300 flex items-center gap-1">
              ${timeInfo}
            </span>
          </div>

          <h3 class="text-base sm:text-lg font-bold text-white leading-snug mb-2 cursor-pointer hover:text-blue-300 transition" onclick="openDayPopup('${todayDateStr}')">
            ${event.title}
          </h3>

          <p class="text-xs sm:text-sm text-blue-100/90 leading-relaxed line-clamp-3 mb-3">
            ${event.summary}
          </p>

          <div class="flex items-center gap-1 text-xs text-blue-200">
            <span>📍</span>
            <span class="truncate font-medium">${event.location || "Dunières"}</span>
          </div>
        </div>
      </div>

      <div class="p-4 bg-black/25 border-t border-white/10 flex items-center justify-between gap-2 mt-auto">
        <div>${attachmentBadge}</div>
        <button onclick="openDayPopup('${todayDateStr}')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white text-blue-950 hover:bg-blue-50 transition shadow-sm flex items-center gap-1">
          <span>Ouvrir la fiche du jour</span>
          <span>➔</span>
        </button>
      </div>
    </article>
  `;
}

/**
 * ==============================================================
 * 2. VOLET PASSÉ : CALENDRIER 2 LIGNES X 7 COLONNES (-14 jours)
 * ==============================================================
 */
function renderPastCalendarGrid() {
  const container = document.getElementById("past-grid-container");
  const headersContainer = document.getElementById("past-col-headers");
  if (!container || !todayDateStr) return;

  const pastDates = getPast14Days(todayDateStr);

  // En-têtes de colonnes dynamiques basés sur les 7 premiers jours
  if (headersContainer && pastDates.length >= 7) {
    const first7 = pastDates.slice(0, 7);
    headersContainer.innerHTML = first7.map(iso => {
      const d = parseISODate(iso);
      return `<div>${JOURS_SEMAINE_COURTS[d.getDay()]}</div>`;
    }).join("");
  }

  container.innerHTML = pastDates.map((isoDate, index) => renderCalendarCell(isoDate, index, "past")).join("");
}

/**
 * ==============================================================
 * 3. VOLET AVENIR : CALENDRIER 2 LIGNES X 7 COLONNES (+14 jours)
 * ==============================================================
 */
function renderFutureCalendarGrid() {
  const container = document.getElementById("future-grid-container");
  const headersContainer = document.getElementById("future-col-headers");
  if (!container || !todayDateStr) return;

  const futureDates = getFuture14Days(todayDateStr);

  // En-têtes de colonnes dynamiques basés sur les 7 premiers jours
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
 * Rendu d'une cellule journalière pour le calendrier 2x7
 */
function renderCalendarCell(isoDate, index, mode) {
  const d = parseISODate(isoDate);
  const jourSemCourt = JOURS_SEMAINE_COURTS[d.getDay()];
  const numJour = d.getDate();
  const moisCourt = MOIS_COURTS[d.getMonth()];

  const events = getEventsForDate(isoDate).filter(matchesFilters);
  const count = events.length;

  let cellBg = "bg-white border-slate-200 hover:border-blue-400";
  let badgeColor = "bg-slate-100 text-slate-500";

  if (count > 0) {
    cellBg = "bg-blue-50/60 border-blue-200 hover:border-blue-500 shadow-sm";
    badgeColor = "bg-blue-600 text-white font-bold";
  }

  // Contenu des événements visibles en 1 coup d'œil
  let eventsListHtml = "";
  if (count === 0) {
    eventsListHtml = `
      <div class="flex-1 flex items-center justify-center py-2 text-slate-300 text-[11px] italic">
        Rien de répertorié
      </div>
    `;
  } else {
    eventsListHtml = `
      <div class="space-y-1.5 flex-1 overflow-hidden mt-1">
        ${events.slice(0, 2).map(e => {
          const time = extractEventTime(e, true);
          return `
            <div class="p-1 rounded-md bg-white border border-slate-200/90 shadow-2xs hover:bg-blue-50/80 transition">
              <div class="flex items-center gap-1">
                <span class="text-[9px] font-black px-1 py-0.2 rounded bg-blue-100 text-blue-800 shrink-0">
                  ${time}
                </span>
                <span class="text-[10px] font-bold text-slate-800 truncate block leading-tight">
                  ${e.title}
                </span>
              </div>
            </div>
          `;
        }).join("")}

        ${count > 2 ? `
          <div class="text-[9px] font-extrabold text-blue-600 text-center bg-blue-100/70 py-0.5 rounded">
            + ${count - 2} autre(s)...
          </div>
        ` : ""}
      </div>
    `;
  }

  return `
    <div 
      onclick="openDayPopup('${isoDate}')" 
      class="day-cell p-2.5 rounded-2xl border flex flex-col justify-between cursor-pointer select-none ${cellBg}"
      title="Cliquer pour voir la fiche détaillée du ${jourSemCourt} ${numJour} ${moisCourt}"
    >
      <!-- En-tête du jour -->
      <div class="flex items-center justify-between pb-1.5 border-b border-slate-100">
        <div>
          <span class="text-[10px] font-black uppercase text-slate-400 block tracking-wider leading-none">
            ${jourSemCourt}
          </span>
          <span class="text-base sm:text-lg font-black text-slate-900 block leading-tight mt-0.5">
            ${numJour} <span class="text-[10px] font-medium text-slate-400">${moisCourt}</span>
          </span>
        </div>
        <span class="text-[10px] px-1.5 py-0.5 rounded-full ${badgeColor}">
          ${count}
        </span>
      </div>

      <!-- Corps du jour : Titre et Heure en un coup d'œil -->
      ${eventsListHtml}

      <!-- Pied de carte : Indication clic -->
      <div class="pt-1.5 mt-auto border-t border-slate-100/80 flex items-center justify-between text-[10px] text-slate-400">
        <span class="font-medium text-slate-400">Détail</span>
        <span>🔍</span>
      </div>
    </div>
  `;
}

/**
 * ==============================================================
 * 4. POPUP DYNAMIQUE DU JOUR (Prend la place sur l'écran)
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

  // Statut temporel
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

  const events = getEventsForDate(isoDate).filter(matchesFilters);
  if (countBadge) countBadge.textContent = `${events.length} événement(s) répertorié(s)`;

  if (subtitle) {
    subtitle.textContent = events.length > 0 
      ? `Retrouvez ci-dessous le descriptif complet, les horaires et les documents pour cette journée.` 
      : `Aucun arrêté ni événement officiel n'a été publié pour cette date.`;
  }

  // Rendu des fiches détaillées de la journée
  if (events.length === 0) {
    body.innerHTML = `
      <div class="py-12 text-center space-y-3 bg-white rounded-2xl border border-slate-200 p-6">
        <span class="text-4xl block">☀️</span>
        <h4 class="text-base font-bold text-slate-800">Aucun événement n'est programmé le ${dateFormatted}</h4>
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

  // Animation d'ouverture
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

/**
 * Fiche détaillée d'un événement affichée dans le popup dynamique
 */
function createDetailedDayEventCard(event) {
  const timeInfo = extractEventTime(event, false, true);
  const catBadgeClass = getCategoryBadgeClass(event.category);
  const dateStr = formatEventDate(event.dates, true);

  // Bloc Document Résolu (Calaméo ou Arrêté PDF)
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
            Le texte intégral de l'arrêté ou de la délibération municipale a été extrait et analysé.
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

  // Image d'en-tête
  const imageHtml = event.image_url ? `
    <div class="h-48 sm:h-56 w-full rounded-2xl overflow-hidden bg-slate-900 mb-4 shadow">
      <img src="${event.image_url}" alt="${event.title}" class="w-full h-full object-cover">
    </div>
  ` : "";

  return `
    <article class="bg-white rounded-3xl p-5 sm:p-6 border border-slate-200 shadow-sm space-y-4">
      
      <!-- Badges et Source -->
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="px-2.5 py-1 rounded-lg text-xs font-black uppercase ${catBadgeClass}">
            ${event.category}
          </span>
          <span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-700">
            ${event.badge || "Information"}
          </span>
        </div>
        <span class="text-xs font-semibold text-slate-500 flex items-center gap-1">
          <span>Source :</span>
          <span class="font-bold text-slate-700">${event.source_name}</span>
        </span>
      </div>

      ${imageHtml}

      <!-- Titre principal -->
      <h4 class="text-lg sm:text-xl font-black text-slate-900 leading-snug">
        ${event.title}
      </h4>

      <!-- Métadonnées : Horaires, Dates, Lieu -->
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

      <!-- Descriptif complet -->
      <div class="space-y-1.5">
        <h5 class="text-xs font-black uppercase tracking-wider text-slate-400">Descriptif complet</h5>
        <p class="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
          ${event.summary}
        </p>
      </div>

      <!-- Bloc pièce jointe résolue si présente -->
      ${attachmentHtml}

      <!-- Boutons d'action -->
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
          onclick="shareSpecificEvent('${event.title.replace(/'/g, "\\'")}', '${event.source_url}')" 
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
 * 5. SECTION RÉPERTOIRE & RECHERCHE GLOBALE (Index)
 * ==============================================================
 */
function renderGlobalDirectory() {
  const container = document.getElementById("global-events-grid");
  const countLabel = document.getElementById("all-publications-count");
  if (!container) return;

  const filtered = allEventsList.filter(matchesFilters);
  if (countLabel) countLabel.textContent = `${filtered.length} parution(s)`;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-10 text-center text-slate-500 bg-white rounded-2xl border border-slate-200 text-xs">
        Aucun résultat ne correspond à votre filtre.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(e => createDirectoryCard(e)).join("");
}

function createDirectoryCard(event) {
  const timeInfo = extractEventTime(event);
  const catClass = getCategoryBadgeClass(event.category);
  const dateStr = formatEventDate(event.dates);

  return `
    <article class="bg-white rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition flex flex-col justify-between overflow-hidden">
      <div class="p-4 sm:p-5">
        <div class="flex items-center justify-between gap-2 mb-2">
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-md ${catClass}">
            ${event.category}
          </span>
          <span class="text-xs font-semibold text-slate-500">
            ${timeInfo}
          </span>
        </div>

        <h4 
          class="text-sm sm:text-base font-bold text-slate-900 leading-snug mb-2 cursor-pointer hover:text-blue-600 transition" 
          onclick="openDayPopup('${event.dates.start.split('T')[0]}')"
        >
          ${event.title}
        </h4>

        <p class="text-xs text-slate-600 leading-relaxed line-clamp-3 mb-3">
          ${event.summary}
        </p>

        <div class="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100">
          <span class="truncate">📍 ${event.location || "Dunières"}</span>
          <span class="shrink-0">📅 ${dateStr}</span>
        </div>
      </div>

      <div class="px-4 py-2 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-2">
        <span class="text-[11px] text-slate-500 truncate">
          ${event.source_name}
        </span>
        <button 
          onclick="openDayPopup('${event.dates.start.split('T')[0]}')" 
          class="px-2.5 py-1 rounded-lg text-xs font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 transition"
        >
          Voir le jour ➔
        </button>
      </div>
    </article>
  `;
}

/**
 * ==============================================================
 * 6. FONCTIONS UTILITAIRES DE GESTION DES DATES & TEMPS
 * ==============================================================
 */

/**
 * Calcule les 14 jours passés strictement avant refDateStr (de J-14 à J-1)
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

/**
 * Calcule les 14 jours futurs strictement après refDateStr (de J+1 à J+14)
 */
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

/**
 * Renvoie tous les événements actifs à une date donnée
 */
function getEventsForDate(isoDate) {
  if (!allEventsList || !isoDate) return [];

  return allEventsList.filter(e => {
    if (!e.dates || !e.dates.start) return false;
    const start = e.dates.start.split("T")[0];
    const end = e.dates.end ? e.dates.end.split("T")[0] : start;
    return isoDate >= start && isoDate <= end;
  });
}

/**
 * Extraction des horaires dans le texte
 */
function extractEventTime(event, compact = false, fullVerbose = false) {
  const text = `${event.title} ${event.summary}`;
  
  const matchRange = text.match(/(?:de|dès|entre)\s*(\d{1,2}[h:]\d{0,2})\s*(?:à|a|et)\s*(\d{1,2}[h:]\d{0,2})/i);
  if (matchRange) {
    if (compact) return matchRange[1];
    return `🕒 ${matchRange[1]} - ${matchRange[2]}`;
  }

  const matchSingle = text.match(/(?:à|a|vers|dès)\s*(\d{1,2}[h:]\d{0,2})/i);
  if (matchSingle) {
    if (compact) return matchSingle[1];
    return `🕒 À ${matchSingle[1]}`;
  }

  const matchDirect = text.match(/\b(\d{1,2}h\d{2}|\d{1,2}h)\b/i);
  if (matchDirect) {
    if (compact) return matchDirect[1];
    return `🕒 ${matchDirect[1]}`;
  }

  if (fullVerbose) return "Toute la journée ou selon affichage municipal";
  return compact ? "Journée" : "📅 En journée";
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

function getCategoryBadgeClass(category) {
  switch (category) {
    case "Alertes & Météo":
      return "bg-rose-100 text-rose-800 border border-rose-200";
    case "Travaux & Voirie":
      return "bg-amber-100 text-amber-800 border border-amber-200";
    case "Vie Municipale & Délibérations":
      return "bg-sky-100 text-sky-800 border border-sky-200";
    case "Manifestations & Vie Associative":
      return "bg-emerald-100 text-emerald-800 border border-emerald-200";
    case "Culture & Patrimoine":
      return "bg-purple-100 text-purple-800 border border-purple-200";
    case "Services & Déchets":
      return "bg-teal-100 text-teal-800 border border-teal-200";
    default:
      return "bg-slate-100 text-slate-700 border border-slate-200";
  }
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
