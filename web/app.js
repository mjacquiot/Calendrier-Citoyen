/**
 * Moteur interactif du Calendrier Dunièrois
 * - Fenêtre glissante stricte J-7 / Aujourd'hui / J+7
 * - Vue Aujourd'hui / Jour sélectionné type Google Calendar (grille horaire 07h-23h, zone toute la journée, ligne Maintenant)
 * - Vues rétrospective (J-7) et prévisionnelle (J+7)
 * - Modale fiche événement complète avec export Google Calendar
 */

let appData = null;
let allEventsList = [];
let todayDateStr = "";
let selectedDateStr = "";
let currentCategory = "all";
let searchQuery = "";
let activePanel = "day"; // 'past' | 'day' | 'future'
let dayViewMode = "grid"; // 'grid' | 'list'
let activeModalEventId = null;
let nowLineTimer = null;

const HOUR_HEIGHT = 64; // px par heure dans la grille Google Calendar
const DEFAULT_TIMED_DURATION_MIN = 90;
const MIN_BLOCK_HEIGHT = 46;

const JOURS_COURTS = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];
const JOURS_LONGS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const MOIS_COURTS_UPPER = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUIN", "JUIL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"];

const CATEGORY_THEMES = {
  "Vie Municipale & Délibérations": {
    dot: "bg-blue-500",
    accent: "bg-blue-600",
    pill: "bg-blue-50 text-blue-700 border-blue-200",
    block: "bg-blue-50/95 border-l-blue-600 border-blue-200/80 text-blue-950 hover:bg-blue-100/80",
    subtext: "text-blue-700"
  },
  "Travaux & Voirie": {
    dot: "bg-amber-500",
    accent: "bg-amber-500",
    pill: "bg-amber-50 text-amber-800 border-amber-200",
    block: "bg-amber-50/95 border-l-amber-500 border-amber-200/80 text-amber-950 hover:bg-amber-100/80",
    subtext: "text-amber-800"
  },
  "Manifestations & Vie Associative": {
    dot: "bg-emerald-500",
    accent: "bg-emerald-600",
    pill: "bg-emerald-50 text-emerald-700 border-emerald-200",
    block: "bg-emerald-50/95 border-l-emerald-600 border-emerald-200/80 text-emerald-950 hover:bg-emerald-100/80",
    subtext: "text-emerald-700"
  },
  "Culture & Patrimoine": {
    dot: "bg-violet-500",
    accent: "bg-violet-600",
    pill: "bg-violet-50 text-violet-700 border-violet-200",
    block: "bg-violet-50/95 border-l-violet-600 border-violet-200/80 text-violet-950 hover:bg-violet-100/80",
    subtext: "text-violet-700"
  },
  "Services & Déchets": {
    dot: "bg-teal-500",
    accent: "bg-teal-600",
    pill: "bg-teal-50 text-teal-700 border-teal-200",
    block: "bg-teal-50/95 border-l-teal-600 border-teal-200/80 text-teal-950 hover:bg-teal-100/80",
    subtext: "text-teal-700"
  },
  "Enfance & Jeunesse": {
    dot: "bg-sky-500",
    accent: "bg-sky-600",
    pill: "bg-sky-50 text-sky-700 border-sky-200",
    block: "bg-sky-50/95 border-l-sky-600 border-sky-200/80 text-sky-950 hover:bg-sky-100/80",
    subtext: "text-sky-700"
  },
  "Alertes & Météo": {
    dot: "bg-rose-500",
    accent: "bg-rose-600",
    pill: "bg-rose-50 text-rose-700 border-rose-200",
    block: "bg-rose-50/95 border-l-rose-600 border-rose-200/80 text-rose-950 hover:bg-rose-100/80",
    subtext: "text-rose-700"
  },
  default: {
    dot: "bg-slate-500",
    accent: "bg-slate-600",
    pill: "bg-slate-100 text-slate-700 border-slate-200",
    block: "bg-slate-50 border-l-slate-500 border-slate-200 text-slate-900 hover:bg-slate-100",
    subtext: "text-slate-600"
  }
};

document.addEventListener("DOMContentLoaded", () => {
  initApp();

  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      if (clearBtn) clearBtn.classList.toggle("hidden", !searchQuery);
      renderAllViews();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeEventModal();
      return;
    }
    const activeTag = document.activeElement ? document.activeElement.tagName : "";
    if (activeTag === "INPUT" || activeTag === "TEXTAREA" || isModalOpen()) return;

    if (activePanel === "day") {
      if (e.key === "ArrowLeft") shiftSelectedDay(-1);
      if (e.key === "ArrowRight") shiftSelectedDay(1);
    }
  });

  const modalElem = document.getElementById("event-modal");
  if (modalElem) {
    modalElem.addEventListener("click", (e) => {
      if (e.target === modalElem) closeEventModal();
    });
  }
});

async function initApp() {
  try {
    const res = await fetch("data.json?v=" + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    appData = await res.json();
    allEventsList = Array.isArray(appData.all_events) ? appData.all_events : [];

    if (appData.metadata && appData.metadata.reference_date) {
      todayDateStr = appData.metadata.reference_date;
    } else {
      todayDateStr = getParisNow().dateStr;
    }
    selectedDateStr = todayDateStr;

    updateHeaderBadge();
    renderAllViews();
    switchPanel("day", true);

    if (nowLineTimer) clearInterval(nowLineTimer);
    nowLineTimer = setInterval(() => {
      if (activePanel === "day" && dayViewMode === "grid") {
        updateNowLinePosition();
      }
    }, 60000);
  } catch (err) {
    console.error("Erreur de chargement de data.json :", err);
    const panelDay = document.getElementById("panel-day");
    if (panelDay) {
      panelDay.innerHTML = `
        <div class="p-8 text-center text-rose-700 bg-rose-50 rounded-2xl border border-rose-200 text-sm">
          Impossible de charger les données du calendrier. Veuillez réactualiser la page.
        </div>
      `;
    }
  }
}

function getParisNow() {
  const now = new Date();
  const dateParts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(now);

  const timeParts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).formatToParts(now);

  const getPart = (parts, type) => (parts.find(p => p.type === type) || {}).value || "00";
  const dateStr = `${getPart(dateParts, "year")}-${getPart(dateParts, "month")}-${getPart(dateParts, "day")}`;
  const hour = parseInt(getPart(timeParts, "hour"), 10);
  const minute = parseInt(getPart(timeParts, "minute"), 10);

  return {
    dateStr,
    hour,
    minute,
    totalMinutes: hour * 60 + minute,
    hhmm: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
  };
}

function updateHeaderBadge() {
  const d = parseISODate(todayDateStr);
  const monthEl = document.getElementById("header-day-month");
  const numEl = document.getElementById("header-day-num");
  if (monthEl) monthEl.textContent = MOIS_COURTS_UPPER[d.getMonth()];
  if (numEl) numEl.textContent = String(d.getDate());

  const syncEl = document.getElementById("footer-last-sync");
  if (syncEl && appData && appData.metadata && appData.metadata.generated_at) {
    const genDate = new Date(appData.metadata.generated_at);
    if (!Number.isNaN(genDate.getTime())) {
      const formatted = genDate.toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit"
      });
      syncEl.textContent = `Actualisé le ${formatted} • Fenêtre J-7 / J+7`;
    }
  }
}

function renderAllViews() {
  render15DayRibbon();
  renderDayPanel();
  renderPastPanel();
  renderFuturePanel();
}

/* ==============================================================
 * NAVIGATION & FILTRES
 * ============================================================== */
function switchPanel(panelName, autoScrollGrid = false) {
  activePanel = panelName;

  const panels = ["past", "day", "future"];
  panels.forEach(p => {
    const sec = document.getElementById(`panel-${p}`);
    const btn = document.getElementById(`tab-btn-${p}`);
    if (sec) sec.classList.toggle("hidden", p !== panelName);
    if (btn) {
      if (p === panelName) {
        btn.className = "flex-1 sm:flex-initial px-3.5 py-1.5 rounded-lg text-xs font-bold bg-white text-blue-600 shadow-xs transition flex items-center justify-center gap-1.5";
      } else {
        btn.className = "flex-1 sm:flex-initial px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 transition flex items-center justify-center gap-1.5";
      }
    }
  });

  if (panelName === "day" && autoScrollGrid && dayViewMode === "grid") {
    requestAnimationFrame(() => scrollDayGridToFocus());
  }
}

function goToToday() {
  selectedDateStr = todayDateStr;
  renderAllViews();
  switchPanel("day", true);
}

function selectDay(isoDate) {
  selectedDateStr = isoDate;
  renderAllViews();
  switchPanel("day", true);
}

function shiftSelectedDay(offsetDays) {
  const minDate = addDaysISO(todayDateStr, -7);
  const maxDate = addDaysISO(todayDateStr, 7);
  const candidate = addDaysISO(selectedDateStr, offsetDays);
  if (candidate < minDate || candidate > maxDate) return;
  selectDay(candidate);
}

function setDayViewMode(mode) {
  dayViewMode = mode;
  const gridBtn = document.getElementById("mode-btn-grid");
  const listBtn = document.getElementById("mode-btn-list");
  const activeCls = "px-2.5 py-1 rounded-md text-xs font-semibold bg-white text-slate-900 shadow-2xs transition flex items-center gap-1";
  const idleCls = "px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 hover:text-slate-900 transition flex items-center gap-1";

  if (gridBtn) gridBtn.className = mode === "grid" ? activeCls : idleCls;
  if (listBtn) listBtn.className = mode === "list" ? activeCls : idleCls;

  renderDayPanel();
  if (mode === "grid") {
    requestAnimationFrame(() => scrollDayGridToFocus());
  }
}

function setCategoryFilter(cat) {
  currentCategory = cat;
  document.querySelectorAll(".cat-pill").forEach(pill => {
    const isMatch = pill.dataset.category === cat;
    if (cat === "all" && isMatch) {
      pill.className = "cat-pill shrink-0 px-3 py-1 rounded-full font-semibold bg-slate-900 text-white transition";
    } else if (isMatch) {
      pill.className = "cat-pill shrink-0 px-3 py-1 rounded-full font-semibold bg-slate-900 text-white flex items-center gap-1.5 transition";
    } else if (pill.dataset.category === "all") {
      pill.className = "cat-pill shrink-0 px-3 py-1 rounded-full font-medium bg-white text-slate-600 border border-slate-200 hover:bg-slate-100 transition";
    } else {
      pill.className = "cat-pill shrink-0 px-3 py-1 rounded-full font-medium bg-white text-slate-600 border border-slate-200 hover:bg-slate-100 flex items-center gap-1.5 transition";
    }
  });
  renderAllViews();
}

function clearSearch() {
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");
  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.classList.add("hidden");
  searchQuery = "";
  renderAllViews();
}

/* ==============================================================
 * RUBAN INTERACTIF 15 JOURS (J-7 -> Aujourd'hui -> J+7)
 * ============================================================== */
function render15DayRibbon() {
  const container = document.getElementById("ribbon-15d-container");
  const summaryCountEl = document.getElementById("window-summary-count");
  if (!container || !todayDateStr) return;

  const dates = getRelativeDateRange(todayDateStr, -7, 7);
  const filteredTotal = allEventsList.filter(matchesFilters).length;
  if (summaryCountEl) {
    summaryCountEl.textContent = `${filteredTotal} événement${filteredTotal > 1 ? "s" : ""} sur 15 jours`;
  }

  container.innerHTML = dates.map(iso => {
    const d = parseISODate(iso);
    const dayShort = JOURS_COURTS[d.getDay()];
    const dayNum = d.getDate();
    const events = getEventsForDate(iso).filter(matchesFilters);
    const count = events.length;
    const isToday = iso === todayDateStr;
    const isSelected = iso === selectedDateStr && activePanel === "day";
    const isSelectedAny = iso === selectedDateStr;

    let boxClass = "bg-white border-slate-200 text-slate-700 hover:border-blue-300 hover:bg-blue-50/40";
    if (isSelectedAny) {
      boxClass = "bg-blue-600 border-blue-600 text-white shadow-sm ring-2 ring-blue-600/20";
    } else if (isToday) {
      boxClass = "bg-blue-50 border-blue-300 text-blue-800 hover:bg-blue-100/70";
    } else if (iso < todayDateStr) {
      boxClass = "bg-slate-50/80 border-slate-200 text-slate-500 hover:bg-slate-100";
    }

    const dots = events.slice(0, 3).map(ev => {
      const theme = getCategoryTheme(ev.category);
      const dotCls = isSelectedAny ? "bg-white/90" : theme.dot;
      return `<span class="w-1.5 h-1.5 rounded-full ${dotCls}"></span>`;
    }).join("");

    const countText = count > 0
      ? `<div class="flex items-center justify-center gap-0.5 mt-1 h-2">${dots}${count > 3 ? `<span class="text-[9px] font-bold leading-none ml-0.5">+</span>` : ""}</div>`
      : `<div class="mt-1 h-2 flex items-center justify-center"><span class="w-1 h-1 rounded-full ${isSelectedAny ? "bg-white/40" : "bg-slate-200"}"></span></div>`;

    return `
      <button
        type="button"
        onclick="selectDay('${iso}')"
        class="rounded-xl border px-1.5 py-2 text-center transition flex flex-col items-center justify-between cursor-pointer ${boxClass}"
        title="${formatLongDate(iso)} — ${count} événement(s)"
      >
        <span class="text-[10px] font-semibold uppercase tracking-tight leading-none ${isSelectedAny ? "text-blue-100" : isToday ? "text-blue-600" : "opacity-75"}">
          ${isToday ? "Auj." : dayShort}
        </span>
        <span class="text-sm font-extrabold leading-tight mt-1 tabular-nums">${dayNum}</span>
        ${countText}
      </button>
    `;
  }).join("");
}

/* ==============================================================
 * VUE JOUR GOOGLE CALENDAR (GRILLE HORAIRE + ZONE TOUTE LA JOURNÉE)
 * ============================================================== */
function renderDayPanel() {
  if (!selectedDateStr) return;

  const titleEl = document.getElementById("day-view-title");
  const badgeEl = document.getElementById("day-view-badge");
  const subtitleEl = document.getElementById("day-view-subtitle");
  const countEl = document.getElementById("day-event-count-badge");

  const calWrapper = document.getElementById("day-calendar-wrapper");
  const listWrapper = document.getElementById("day-list-wrapper");
  const emptyState = document.getElementById("day-empty-state");

  const events = getEventsForDate(selectedDateStr).filter(matchesFilters);
  const timedEvents = [];
  const allDayEvents = [];

  events.forEach(ev => {
    const startMin = getEventStartMinutes(ev);
    if (startMin !== null) {
      timedEvents.push(ev);
    } else {
      allDayEvents.push(ev);
    }
  });

  timedEvents.sort((a, b) => getEventStartMinutes(a) - getEventStartMinutes(b));

  if (titleEl) titleEl.textContent = formatLongDate(selectedDateStr);

  if (badgeEl) {
    const diff = diffDaysISO(todayDateStr, selectedDateStr);
    if (diff === 0) {
      badgeEl.textContent = "Aujourd'hui";
      badgeEl.className = "px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200";
    } else if (diff < 0) {
      badgeEl.textContent = `Il y a ${Math.abs(diff)} j`;
      badgeEl.className = "px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200";
    } else {
      badgeEl.textContent = `Dans ${diff} j`;
      badgeEl.className = "px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200";
    }
  }

  if (subtitleEl) {
    if (events.length === 0) {
      subtitleEl.textContent = "Aucun événement actif pour cette date";
    } else {
      subtitleEl.textContent = `${timedEvents.length} créneau(x) horaire(s) • ${allDayEvents.length} info(s) toute la journée`;
    }
  }

  if (countEl) {
    countEl.textContent = `${events.length} événement${events.length > 1 ? "s" : ""}`;
  }

  if (events.length === 0) {
    if (calWrapper) calWrapper.classList.add("hidden");
    if (listWrapper) listWrapper.classList.add("hidden");
    if (emptyState) emptyState.classList.remove("hidden");
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");

  if (dayViewMode === "list") {
    if (calWrapper) calWrapper.classList.add("hidden");
    if (listWrapper) {
      listWrapper.classList.remove("hidden");
      const ordered = [...timedEvents, ...allDayEvents];
      listWrapper.innerHTML = ordered.map(ev => createEventCard(ev)).join("");
    }
    return;
  }

  // Mode Grille Google Calendar
  if (listWrapper) listWrapper.classList.add("hidden");
  if (calWrapper) calWrapper.classList.remove("hidden");

  renderAllDayZone(allDayEvents);
  renderHourlyGrid(timedEvents, allDayEvents.length > 0);
}

function renderAllDayZone(allDayEvents) {
  const section = document.getElementById("day-allday-section");
  const container = document.getElementById("day-allday-container");
  if (!section || !container) return;

  if (allDayEvents.length === 0) {
    section.classList.add("hidden");
    container.innerHTML = "";
    return;
  }

  section.classList.remove("hidden");
  container.innerHTML = allDayEvents.map(ev => {
    const theme = getCategoryTheme(ev.category);
    const price = extractExplicitPrice(ev);
    return `
      <button
        type="button"
        onclick="openEventModal('${ev.id}')"
        class="text-left px-3 py-2 rounded-xl border border-l-4 ${theme.block} transition shadow-2xs flex items-center gap-2.5 max-w-full sm:max-w-[calc(50%-0.25rem)] lg:max-w-[calc(33.333%-0.35rem)] cursor-pointer"
      >
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="text-[10px] font-bold uppercase tracking-wide ${theme.subtext}">${escapeHtml(ev.badge || ev.category)}</span>
            ${price ? `<span class="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-white/80 text-slate-700 border border-slate-200">${escapeHtml(price)}</span>` : ""}
          </div>
          <p class="text-xs font-bold truncate mt-0.5">${escapeHtml(ev.title)}</p>
          <p class="text-[11px] opacity-75 truncate">${escapeHtml(ev.location || "Dunières")}</p>
        </div>
      </button>
    `;
  }).join("");
}

function renderHourlyGrid(timedEvents, hasAllDayItems) {
  const canvas = document.getElementById("day-timegrid-canvas");
  const noTimedBanner = document.getElementById("day-no-timed-banner");
  if (!canvas) return;

  if (noTimedBanner) {
    noTimedBanner.classList.toggle("hidden", !(timedEvents.length === 0 && hasAllDayItems));
  }

  // Bornes horaires dynamiques : 07h-23h par défaut, étendues si événement plus tôt/plus tard
  let startHour = 7;
  let endHour = 23;
  timedEvents.forEach(ev => {
    const sMin = getEventStartMinutes(ev);
    const eMin = getEventVisualEndMinutes(ev, sMin);
    if (sMin !== null) startHour = Math.min(startHour, Math.floor(sMin / 60));
    if (eMin !== null) endHour = Math.max(endHour, Math.min(24, Math.ceil(eMin / 60)));
  });

  const totalHours = endHour - startHour;
  const totalHeightPx = totalHours * HOUR_HEIGHT;

  // Axe horaire gauche
  let hourLabelsHtml = "";
  let gridLinesHtml = "";
  for (let i = 0; i < totalHours; i++) {
    const h = startHour + i;
    const topPx = i * HOUR_HEIGHT;
    const labelStr = `${String(h).padStart(2, "0")}:00`;
    hourLabelsHtml += `
      <div class="absolute right-2.5 text-[11px] font-medium text-slate-400 tabular-nums ${i === 0 ? "top-1" : "-translate-y-2"}" ${i === 0 ? "" : `style="top: ${topPx}px;"`}>
        ${labelStr}
      </div>
    `;
    gridLinesHtml += `
      <div class="absolute inset-x-0 border-t border-slate-200/85" style="top: ${topPx}px;"></div>
      <div class="absolute inset-x-0 border-t border-dashed border-slate-100" style="top: ${topPx + HOUR_HEIGHT / 2}px;"></div>
    `;
  }

  // Calcul des colonnes en cas de chevauchement horaire
  const layoutItems = computeOverlapColumns(timedEvents);
  const eventsHtml = layoutItems.map(item => {
    const { event, startMin, endMin, col, totalCols } = item;
    const topPx = ((startMin - startHour * 60) / 60) * HOUR_HEIGHT;
    const rawHeight = ((endMin - startMin) / 60) * HOUR_HEIGHT;
    const heightPx = Math.max(MIN_BLOCK_HEIGHT, Math.min(rawHeight, totalHeightPx - topPx - 2));

    const leftPct = (col / totalCols) * 100;
    const widthPct = (1 / totalCols) * 100;
    const theme = getCategoryTheme(event.category);
    const timeLabel = formatTimingRange(event);
    const durationLabel = formatDurationLabel(event);
    const price = extractExplicitPrice(event);
    const showLocation = heightPx >= 64;

    return `
      <button
        type="button"
        onclick="openEventModal('${event.id}')"
        class="cal-event-block absolute rounded-xl border border-l-4 ${theme.block} px-3 py-1.5 text-left overflow-hidden flex flex-col justify-start cursor-pointer shadow-xs z-10"
        style="top: ${topPx + 1}px; height: ${heightPx - 2}px; left: calc(${leftPct}% + 6px); width: calc(${widthPct}% - 12px);"
        title="${escapeHtml(event.title)} (${timeLabel})"
      >
        <div class="flex items-center justify-between gap-2 min-w-0">
          <div class="flex items-center gap-1.5 min-w-0 flex-wrap">
            <span class="text-[11px] font-extrabold tabular-nums ${theme.subtext} shrink-0">${escapeHtml(timeLabel)}</span>
            ${durationLabel ? `<span class="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-white/80 border border-black/5 shrink-0">${escapeHtml(durationLabel)}</span>` : ""}
            ${price ? `<span class="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-white/80 text-slate-700 border border-black/5 shrink-0">${escapeHtml(price)}</span>` : ""}
          </div>
          <span class="hidden md:inline text-[10px] font-semibold opacity-70 truncate shrink-0">${escapeHtml(event.badge || event.category)}</span>
        </div>
        <p class="text-xs sm:text-sm font-bold leading-snug line-clamp-2 mt-0.5">${escapeHtml(event.title)}</p>
        ${showLocation ? `<p class="text-[11px] opacity-75 truncate mt-auto">${escapeHtml(event.location || "Dunières")}</p>` : ""}
      </button>
    `;
  }).join("");

  canvas.dataset.startHour = String(startHour);
  canvas.dataset.endHour = String(endHour);
  canvas.innerHTML = `
    <div class="w-16 sm:w-20 shrink-0 border-r border-slate-200 bg-slate-50/40 relative" style="height: ${totalHeightPx}px;">
      ${hourLabelsHtml}
    </div>
    <div id="day-grid-events-layer" class="flex-1 relative bg-white" style="height: ${totalHeightPx}px;">
      ${gridLinesHtml}
      <div id="day-now-indicator" class="hidden absolute inset-x-0 z-20 pointer-events-none">
        <div class="relative flex items-center">
          <span class="w-2.5 h-2.5 rounded-full bg-rose-500 -ml-1.5 shadow-xs ring-2 ring-white"></span>
          <div class="h-0.5 bg-rose-500 flex-1"></div>
          <span id="day-now-label" class="mr-2 px-1.5 py-0.5 rounded bg-rose-500 text-white text-[10px] font-bold tabular-nums shadow-xs">
            --:--
          </span>
        </div>
      </div>
      ${eventsHtml}
    </div>
  `;

  updateNowLinePosition();
}

function updateNowLinePosition() {
  const canvas = document.getElementById("day-timegrid-canvas");
  const indicator = document.getElementById("day-now-indicator");
  const label = document.getElementById("day-now-label");
  if (!canvas || !indicator) return;

  const parisNow = getParisNow();
  const showNow = selectedDateStr === parisNow.dateStr || selectedDateStr === todayDateStr;
  const startHour = parseInt(canvas.dataset.startHour || "7", 10);
  const endHour = parseInt(canvas.dataset.endHour || "23", 10);

  if (!showNow || parisNow.totalMinutes < startHour * 60 || parisNow.totalMinutes > endHour * 60) {
    indicator.classList.add("hidden");
    return;
  }

  const topPx = ((parisNow.totalMinutes - startHour * 60) / 60) * HOUR_HEIGHT;
  indicator.style.top = `${topPx}px`;
  indicator.classList.remove("hidden");
  if (label) label.textContent = parisNow.hhmm;
}

function scrollDayGridToFocus() {
  const scrollBox = document.getElementById("day-grid-scroll");
  const canvas = document.getElementById("day-timegrid-canvas");
  if (!scrollBox || !canvas) return;

  const startHour = parseInt(canvas.dataset.startHour || "7", 10);
  const events = getEventsForDate(selectedDateStr).filter(matchesFilters);
  const timedMinutes = events.map(getEventStartMinutes).filter(m => m !== null).sort((a, b) => a - b);

  let targetMinutes = 8 * 60;
  if (timedMinutes.length > 0) {
    targetMinutes = Math.max(startHour * 60, timedMinutes[0] - 90);
  } else if (selectedDateStr === todayDateStr) {
    const parisNow = getParisNow();
    targetMinutes = Math.max(startHour * 60, parisNow.totalMinutes - 120);
  }

  const targetPx = Math.max(0, ((targetMinutes - startHour * 60) / 60) * HOUR_HEIGHT);
  scrollBox.scrollTo({ top: targetPx, behavior: "smooth" });
}

function computeOverlapColumns(timedEvents) {
  const items = timedEvents
    .map(ev => {
      const startMin = getEventStartMinutes(ev);
      if (startMin === null) return null;
      const endMin = getEventVisualEndMinutes(ev, startMin);
      return { event: ev, startMin, endMin };
    })
    .filter(Boolean)
    .sort((a, b) => a.startMin - b.startMin || b.endMin - a.endMin);

  if (items.length === 0) return [];

  // Regrouper les événements qui se chevauchent en clusters connexes
  const clusters = [];
  let currentCluster = [items[0]];
  let clusterEnd = items[0].endMin;

  for (let i = 1; i < items.length; i++) {
    if (items[i].startMin < clusterEnd) {
      currentCluster.push(items[i]);
      clusterEnd = Math.max(clusterEnd, items[i].endMin);
    } else {
      clusters.push(currentCluster);
      currentCluster = [items[i]];
      clusterEnd = items[i].endMin;
    }
  }
  clusters.push(currentCluster);

  const result = [];
  clusters.forEach(cluster => {
    const colEnds = [];
    cluster.forEach(item => {
      let placedCol = colEnds.findIndex(endT => endT <= item.startMin);
      if (placedCol === -1) {
        placedCol = colEnds.length;
        colEnds.push(item.endMin);
      } else {
        colEnds[placedCol] = item.endMin;
      }
      item.col = placedCol;
    });
    const totalCols = colEnds.length;
    cluster.forEach(item => {
      item.totalCols = totalCols;
      result.push(item);
    });
  });

  return result;
}

/* ==============================================================
 * VUES 7 JOURS PASSÉS (J-7) & 7 JOURS À VENIR (J+7)
 * ============================================================== */
function renderPastPanel() {
  const strip = document.getElementById("past-strip-container");
  const timeline = document.getElementById("past-timeline-container");
  if (!strip || !timeline || !todayDateStr) return;

  const pastDates = getRelativeDateRange(todayDateStr, -7, -1);
  strip.innerHTML = pastDates.map(iso => render7DayStripChip(iso)).join("");

  // Afficher du plus récent (J-1) au plus ancien (J-7)
  const orderedDates = [...pastDates].reverse();
  renderDayTimelineList(timeline, orderedDates, "Aucun événement répertorié sur les 7 derniers jours.");
}

function renderFuturePanel() {
  const strip = document.getElementById("future-strip-container");
  const timeline = document.getElementById("future-timeline-container");
  if (!strip || !timeline || !todayDateStr) return;

  const futureDates = getRelativeDateRange(todayDateStr, 1, 7);
  strip.innerHTML = futureDates.map(iso => render7DayStripChip(iso)).join("");

  renderDayTimelineList(timeline, futureDates, "Aucun événement programmé sur les 7 prochains jours.");
}

function render7DayStripChip(iso) {
  const d = parseISODate(iso);
  const count = getEventsForDate(iso).filter(matchesFilters).length;
  const hasEvents = count > 0;

  return `
    <button
      type="button"
      onclick="selectDay('${iso}')"
      class="rounded-xl border p-2 text-center transition flex flex-col items-center justify-center cursor-pointer ${
        hasEvents
          ? "bg-blue-50/70 border-blue-200 text-blue-900 hover:bg-blue-100/80"
          : "bg-slate-50 border-slate-200 text-slate-400 hover:bg-slate-100"
      }"
      title="Ouvrir ${formatLongDate(iso)} dans l'agenda horaire"
    >
      <span class="text-[10px] font-semibold uppercase">${JOURS_COURTS[d.getDay()]}</span>
      <span class="text-base font-extrabold leading-tight my-0.5 tabular-nums">${d.getDate()}</span>
      <span class="text-[10px] font-bold ${hasEvents ? "text-blue-600" : "text-slate-400"}">
        ${hasEvents ? `${count} év.` : "—"}
      </span>
    </button>
  `;
}

function renderDayTimelineList(container, dates, emptyText) {
  const activeDates = dates.filter(iso => getEventsForDate(iso).filter(matchesFilters).length > 0);
  if (activeDates.length === 0) {
    container.innerHTML = `
      <div class="bg-white rounded-2xl border border-slate-200 p-8 text-center text-sm text-slate-500">
        ${escapeHtml(emptyText)}
      </div>
    `;
    return;
  }

  container.innerHTML = activeDates.map(iso => {
    const dayEvents = getEventsForDate(iso).filter(matchesFilters);
    dayEvents.sort((a, b) => {
      const mA = getEventStartMinutes(a);
      const mB = getEventStartMinutes(b);
      return (mA === null ? 9999 : mA) - (mB === null ? 9999 : mB);
    });

    return `
      <div class="space-y-2.5">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-sm font-extrabold text-slate-800 capitalize">${escapeHtml(formatLongDate(iso))}</h3>
          <button
            type="button"
            onclick="selectDay('${iso}')"
            class="text-xs font-semibold text-blue-600 hover:text-blue-800 transition cursor-pointer"
          >
            Voir la journée en grille →
          </button>
        </div>
        <div class="space-y-2.5">
          ${dayEvents.map(ev => createEventCard(ev)).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function createEventCard(event) {
  const theme = getCategoryTheme(event.category);
  const timeLabel = formatTimingRange(event);
  const durationLabel = formatDurationLabel(event);
  const price = extractExplicitPrice(event);

  const thumbHtml = event.image_url ? `
    <div class="hidden sm:block w-24 h-24 rounded-xl overflow-hidden bg-slate-100 border border-slate-200 shrink-0 self-center">
      <img src="${escapeHtml(event.image_url)}" alt="" loading="lazy" class="w-full h-full object-cover" onerror="this.parentElement.remove()">
    </div>
  ` : "";

  return `
    <article
      onclick="openEventModal('${event.id}')"
      class="bg-white rounded-2xl border border-slate-200 hover:border-blue-300 hover:shadow-md transition p-4 flex items-stretch gap-4 cursor-pointer group relative overflow-hidden"
    >
      <div class="w-1 rounded-full ${theme.accent} shrink-0"></div>

      <!-- Colonne Horaire -->
      <div class="w-24 sm:w-28 shrink-0 flex flex-col justify-center border-r border-slate-100 pr-3">
        <span class="text-sm font-extrabold text-slate-900 tabular-nums leading-tight">${escapeHtml(timeLabel)}</span>
        ${durationLabel ? `<span class="text-[11px] font-semibold text-blue-700 mt-1">${escapeHtml(durationLabel)}</span>` : ""}
      </div>

      <!-- Corps -->
      <div class="flex-1 min-w-0 flex flex-col justify-between space-y-1.5">
        <div class="flex flex-wrap items-center gap-1.5">
          <span class="px-2 py-0.5 rounded-full text-[11px] font-semibold border ${theme.pill}">
            ${escapeHtml(event.category)}
          </span>
          ${price ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">${escapeHtml(price)}</span>` : ""}
          ${event.has_attachment ? `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">${event.attachment_type === "calameo" ? "Agenda Calaméo" : "Document PDF"}</span>` : ""}
          <span class="ml-auto text-[11px] text-slate-400 hidden md:inline truncate">${escapeHtml(event.source_name || "")}</span>
        </div>

        <h4 class="text-sm sm:text-base font-bold text-slate-900 group-hover:text-blue-600 transition leading-snug">
          ${escapeHtml(event.title)}
        </h4>

        <p class="text-xs sm:text-sm text-slate-600 line-clamp-2 leading-relaxed">
          ${escapeHtml(event.summary || "")}
        </p>

        <div class="flex items-center justify-between text-xs text-slate-500 pt-1">
          <span class="truncate">${escapeHtml(event.location || "Dunières")}</span>
          <span class="font-semibold text-blue-600 group-hover:underline shrink-0 ml-2">Détails →</span>
        </div>
      </div>

      ${thumbHtml}
    </article>
  `;
}

/* ==============================================================
 * MODALE FICHE ÉVÉNEMENT DÉTAILLÉE
 * ============================================================== */
function openEventModal(eventId) {
  const event = allEventsList.find(e => e.id === eventId);
  if (!event) return;

  activeModalEventId = eventId;
  const modal = document.getElementById("event-modal");
  const card = document.getElementById("event-modal-card");
  const accentBar = document.getElementById("modal-accent-bar");
  const catBadge = document.getElementById("modal-cat-badge");
  const timeBadge = document.getElementById("modal-time-badge");
  const priceBadge = document.getElementById("modal-price-badge");
  const titleEl = document.getElementById("modal-title");
  const bodyEl = document.getElementById("modal-body");
  const footerEl = document.getElementById("modal-footer");

  if (!modal || !bodyEl) return;

  const theme = getCategoryTheme(event.category);
  const timeLabel = formatTimingRange(event);
  const durationLabel = formatDurationLabel(event);
  const price = extractExplicitPrice(event);
  const dateDisplay = formatEventDatePeriod(event.dates);
  const fullText = event.full_content || event.summary || "";

  if (accentBar) accentBar.className = `h-1.5 w-full shrink-0 ${theme.accent}`;
  if (catBadge) {
    catBadge.textContent = event.category;
    catBadge.className = `px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${theme.pill}`;
  }
  if (timeBadge) {
    timeBadge.textContent = durationLabel ? `${timeLabel} (${durationLabel})` : timeLabel;
  }
  if (priceBadge) {
    if (price) {
      priceBadge.textContent = price;
      priceBadge.classList.remove("hidden");
    } else {
      priceBadge.classList.add("hidden");
    }
  }
  if (titleEl) titleEl.textContent = event.title;

  const imageHtml = event.image_url ? `
    <div class="rounded-xl overflow-hidden bg-slate-100 border border-slate-200 p-2 flex items-center justify-center">
      <img src="${escapeHtml(event.image_url)}" alt="${escapeHtml(event.title)}" class="max-w-full max-h-80 object-contain rounded-lg" onerror="this.parentElement.remove()">
    </div>
  ` : "";

  let attachmentHtml = "";
  if (event.has_attachment && event.attachment_data) {
    const attUrl = event.attachment_data.original_url || event.source_url;
    const isCalameo = event.attachment_type === "calameo";
    attachmentHtml = `
      <div class="p-4 rounded-xl bg-amber-50 border border-amber-200 space-y-2">
        <p class="text-xs font-bold uppercase tracking-wide text-amber-900">
          ${isCalameo ? "Publication Calaméo associée" : "Document officiel PDF"}
        </p>
        ${event.attachment_data.enriched_text ? `<p class="text-xs text-amber-950/85 leading-relaxed">${escapeHtml(event.attachment_data.enriched_text.slice(0, 260))}</p>` : ""}
        <a href="${escapeHtml(attUrl)}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white transition">
          <span>${isCalameo ? "Feuilleter sur Calaméo" : "Ouvrir le PDF"}</span>
          <span>↗</span>
        </a>
      </div>
    `;
  }

  bodyEl.innerHTML = `
    ${imageHtml}

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
      <div>
        <span class="text-slate-400 font-medium block">Date</span>
        <span class="font-bold text-slate-800 capitalize">${escapeHtml(dateDisplay)}</span>
      </div>
      <div>
        <span class="text-slate-400 font-medium block">Horaire</span>
        <span class="font-bold text-slate-800">${escapeHtml(durationLabel ? `${timeLabel} (${durationLabel})` : timeLabel)}</span>
      </div>
      <div>
        <span class="text-slate-400 font-medium block">Lieu</span>
        <span class="font-bold text-slate-800">${escapeHtml(event.location || "Dunières")}</span>
      </div>
      <div>
        <span class="text-slate-400 font-medium block">Source</span>
        <span class="font-bold text-slate-800">${escapeHtml(event.source_name || "")}</span>
      </div>
    </div>

    <div class="space-y-2">
      <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Informations complètes</h4>
      <div class="text-sm text-slate-700 leading-relaxed space-y-2.5">
        ${formatRichText(fullText)}
      </div>
    </div>

    ${attachmentHtml}
  `;

  const gcalUrl = buildGoogleCalendarUrl(event);
  if (footerEl) {
    footerEl.innerHTML = `
      <div class="flex flex-wrap items-center gap-2">
        <a
          href="${escapeHtml(event.source_url)}"
          target="_blank"
          rel="noopener noreferrer"
          class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition inline-flex items-center gap-1.5"
        >
          <span>Voir la source officielle</span>
          <span>↗</span>
        </a>
        <a
          href="${escapeHtml(gcalUrl)}"
          target="_blank"
          rel="noopener noreferrer"
          class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition inline-flex items-center gap-1.5"
        >
          <span>+ Ajouter à Google Calendar</span>
        </a>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick="shareEventById('${event.id}')"
          class="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-200/70 hover:bg-slate-200 text-slate-700 transition cursor-pointer"
        >
          Partager
        </button>
        <button
          type="button"
          onclick="closeEventModal()"
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white transition cursor-pointer"
        >
          Fermer
        </button>
      </div>
    `;
  }

  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.remove("opacity-0");
    if (card) card.classList.remove("scale-95");
  }, 10);
  document.body.style.overflow = "hidden";
}

function closeEventModal() {
  const modal = document.getElementById("event-modal");
  const card = document.getElementById("event-modal-card");
  if (!modal || modal.classList.contains("hidden")) return;

  modal.classList.add("opacity-0");
  if (card) card.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
    activeModalEventId = null;
  }, 180);
}

function isModalOpen() {
  const modal = document.getElementById("event-modal");
  return Boolean(modal && !modal.classList.contains("hidden"));
}

/* ==============================================================
 * UTILITAIRES TEMPORELS, TARIFS & FORMATAGE
 * ============================================================== */
function getEventStartMinutes(event) {
  const st = event && event.timing ? event.timing.start_time : null;
  return parseHHMM(st);
}

function getEventVisualEndMinutes(event, startMin) {
  if (startMin === null) return null;
  const et = event && event.timing ? event.timing.end_time : null;
  const parsedEnd = parseHHMM(et);
  if (parsedEnd !== null && parsedEnd > startMin) return parsedEnd;

  const dur = event && event.timing ? event.timing.duration_minutes : null;
  if (typeof dur === "number" && dur > 0) return Math.min(24 * 60, startMin + dur);

  return Math.min(24 * 60, startMin + DEFAULT_TIMED_DURATION_MIN);
}

function parseHHMM(str) {
  if (!str) return null;
  const m = str.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  const h = parseInt(m[1], 10);
  const min = parseInt(m[2], 10);
  if (h < 0 || h > 23 || min < 0 || min > 59) return null;
  return h * 60 + min;
}

function formatTimingRange(event) {
  const t = event && event.timing ? event.timing : {};
  if (!t.start_time) return "Toute la journée";
  if (t.end_time) return `${t.start_time} – ${t.end_time}`;
  return `À ${t.start_time}`;
}

function formatDurationLabel(event) {
  const mins = event && event.timing ? event.timing.duration_minutes : null;
  if (!mins || mins <= 0) return "";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h}h`;
  return `${h}h${String(m).padStart(2, "0")}`;
}

function extractExplicitPrice(event) {
  const text = `${event.title || ""} ${event.summary || ""} ${event.full_content || ""}`.toLowerCase();
  const matchTarif = text.match(/(?:tarif|prix|adulte|formule|place|billet)\s*[:àa]?\s*(\d+(?:[.,]\d{1,2})?\s*€)/i);
  if (matchTarif) return matchTarif[1].replace(/\s+/g, " ");

  const matchEuro = text.match(/\b(\d+(?:[.,]\d{1,2})?\s*(?:€|euros?))\b/i);
  if (matchEuro && !/lot\s*=/.test(text) && !/b[ée]n[ée]fices/.test(text)) {
    return matchEuro[1].replace(/euros?/i, "€").replace(/\s+/g, " ");
  }

  if (/\b(?:entrée libre|entree libre|accès libre)\b/i.test(text) || /\bgratuit(?:e|s)?\b/i.test(text) && !/accompagnement gratuit/.test(text)) {
    return "Gratuit";
  }
  return null;
}

function getCategoryTheme(category) {
  return CATEGORY_THEMES[category] || CATEGORY_THEMES.default;
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
  if (!matchCat) return false;
  if (!searchQuery) return true;

  const haystack = [
    event.title,
    event.summary,
    event.full_content,
    event.location,
    event.badge,
    event.category
  ].filter(Boolean).join(" ").toLowerCase();

  return haystack.includes(searchQuery);
}

function getRelativeDateRange(refIso, startOffset, endOffset) {
  const list = [];
  for (let i = startOffset; i <= endOffset; i++) {
    list.push(addDaysISO(refIso, i));
  }
  return list;
}

function addDaysISO(isoDate, delta) {
  const d = parseISODate(isoDate);
  d.setDate(d.getDate() + delta);
  return formatISODate(d);
}

function diffDaysISO(fromIso, toIso) {
  const d1 = parseISODate(fromIso);
  const d2 = parseISODate(toIso);
  return Math.round((d2 - d1) / (1000 * 60 * 60 * 24));
}

function parseISODate(isoStr) {
  if (!isoStr) return new Date();
  const parts = isoStr.split("T")[0].split("-");
  if (parts.length === 3) {
    return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  }
  return new Date(isoStr);
}

function formatISODate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatLongDate(isoStr) {
  const d = parseISODate(isoStr);
  return `${JOURS_LONGS[d.getDay()]} ${d.getDate()} ${MOIS_LONGS[d.getMonth()]} ${d.getFullYear()}`;
}

function formatEventDatePeriod(dates) {
  if (!dates || !dates.start) return "Date à préciser";
  if (dates.is_period && dates.end) {
    return `Du ${formatLongDate(dates.start)} au ${formatLongDate(dates.end)}`;
  }
  return formatLongDate(dates.start);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatRichText(text) {
  const escaped = escapeHtml(text);
  const paragraphs = escaped.split(/\n+/).map(p => p.trim()).filter(Boolean);
  return paragraphs.map(p => {
    const linked = p.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline break-all">$1</a>'
    );
    return `<p>${linked}</p>`;
  }).join("");
}

function buildGoogleCalendarUrl(event) {
  const params = new URLSearchParams();
  params.set("action", "TEMPLATE");
  params.set("text", event.title || "Événement Dunières");

  const startIso = (event.dates && event.dates.start ? event.dates.start : todayDateStr).replace(/-/g, "");
  const startMin = getEventStartMinutes(event);

  if (startMin !== null) {
    const endMin = getEventVisualEndMinutes(event, startMin);
    const sh = String(Math.floor(startMin / 60)).padStart(2, "0");
    const sm = String(startMin % 60).padStart(2, "0");
    const eh = String(Math.floor(endMin / 60)).padStart(2, "0");
    const em = String(endMin % 60).padStart(2, "0");
    params.set("dates", `${startIso}T${sh}${sm}00/${startIso}T${eh}${em}00`);
    params.set("ctz", "Europe/Paris");
  } else {
    const endBase = event.dates && event.dates.end ? event.dates.end : event.dates.start;
    const endPlusOne = addDaysISO(endBase || todayDateStr, 1).replace(/-/g, "");
    params.set("dates", `${startIso}/${endPlusOne}`);
  }

  if (event.location) params.set("location", event.location);
  const desc = `${event.summary || ""}\n\nSource : ${event.source_url || ""}`.trim();
  params.set("details", desc);

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function shareEventById(eventId) {
  const event = allEventsList.find(e => e.id === eventId);
  if (!event) return;
  if (navigator.share) {
    navigator.share({ title: event.title, url: event.source_url }).catch(() => {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(`${event.title} : ${event.source_url}`);
    alert("Lien copié dans votre presse-papier !");
  }
}
