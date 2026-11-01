/**
 * Moteur interactif du Portail Citoyen & Calendrier de Dunières.
 * Gère le calendrier visuel 31 jours (-15j/+15j), la section Aujourd'hui détaillée,
 * et la modale de consultation approfondie des événements.
 */

let appData = null;
let allEventsList = [];
let todayDateStr = "";
let selectedDateStr = "";
let currentCategory = "all";
let searchQuery = "";
let activeModalEvent = null;

const JOURS_SEMAINE = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];
const MOIS_FR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"];
const MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

// Initialisation au chargement
document.addEventListener("DOMContentLoaded", () => {
  initApp();

  // Écouteur recherche
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderTodaySection();
      renderSelectedDayEvents();
      renderAllEventsGrid();
    });
  }

  // Écouteur touche Échap pour fermer la modale
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Clic en dehors de la carte modale pour fermer
  const modalElem = document.getElementById("event-modal");
  if (modalElem) {
    modalElem.addEventListener("click", (e) => {
      if (e.target === modalElem) closeModal();
    });
  }
});

/**
 * Initialisation principale
 */
async function initApp() {
  try {
    const res = await fetch("data.json?v=" + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    appData = await res.json();
    allEventsList = appData.all_events || [];

    // Détermination de la date du jour de référence
    if (appData.metadata && appData.metadata.reference_date) {
      todayDateStr = appData.metadata.reference_date;
    } else {
      todayDateStr = new Date().toISOString().split("T")[0];
    }
    selectedDateStr = todayDateStr;

    // Mise à jour de l'en-tête
    updateHeaderMetadata();

    // Rendu des différentes sections
    renderTodaySection();
    renderCalendarStrip();
    renderSelectedDayEvents();
    renderAllEventsGrid();

  } catch (err) {
    console.error("Erreur de chargement data.json :", err);
    document.getElementById("today-hero-section").innerHTML = `
      <div class="text-center py-6 text-white text-sm">
        ⚠️ Le calendrier citoyen est en cours d'actualisation. Veuillez recharger la page.
      </div>
    `;
  }
}

/**
 * Met à jour les métadonnées dans l'en-tête
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

  // Bannière date aujourd'hui
  const banner = document.getElementById("today-date-banner");
  if (banner && todayDateStr) {
    const d = parseISODate(todayDateStr);
    const jourSem = d.toLocaleDateString("fr-FR", { weekday: "long" });
    const jourNum = d.getDate();
    const mois = MOIS_LONGS[d.getMonth()];
    const annee = d.getFullYear();
    banner.textContent = `Aujourd'hui à Dunières : ${capitalize(jourSem)} ${jourNum} ${mois} ${annee}`;
  }
}

/**
 * 1. SECTION AUJOURD'HUI TRÈS DÉTAILLÉE
 */
function renderTodaySection() {
  const container = document.getElementById("today-events-container");
  const countBadge = document.getElementById("today-badge-count");
  const emptyMsg = document.getElementById("today-empty-msg");
  if (!container) return;

  const todayEvents = getEventsForDate(todayDateStr).filter(matchesFilters);

  if (countBadge) countBadge.textContent = `${todayEvents.length} événement(s) actif(s)`;

  if (todayEvents.length === 0) {
    container.innerHTML = "";
    if (emptyMsg) emptyMsg.classList.remove("hidden");
    return;
  }

  if (emptyMsg) emptyMsg.classList.add("hidden");
  container.innerHTML = todayEvents.map(event => createHeroTodayCard(event)).join("");
}

/**
 * Carte détaillée pour la section Aujourd'hui (Hero)
 */
function createHeroTodayCard(event) {
  const timeInfo = extractEventTime(event);
  const catBadgeClass = getCategoryBadgeClass(event.category);

  let attachmentAction = "";
  if (event.has_attachment && event.attachment_data) {
    if (event.attachment_type === "calameo") {
      attachmentAction = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-amber-300">
          📖 Agenda Calaméo lié
        </span>
      `;
    } else if (event.attachment_type === "pdf") {
      attachmentAction = `
        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-rose-300">
          📄 Arrêté PDF officiel
        </span>
      `;
    }
  }

  const imageHtml = event.image_url ? `
    <div class="h-40 w-full overflow-hidden bg-slate-800 relative">
      <img src="${event.image_url}" alt="${event.title}" class="w-full h-full object-cover transition-transform duration-300 hover:scale-105" loading="lazy">
      <div class="absolute top-2 right-2 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-black/60 backdrop-blur text-white">
        ${event.badge || "En cours"}
      </div>
    </div>
  ` : "";

  return `
    <article class="bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 overflow-hidden flex flex-col justify-between hover:bg-white/15 transition shadow-sm">
      <div>
        ${imageHtml}
        <div class="p-5">
          <!-- Badges & Horaires -->
          <div class="flex items-center justify-between gap-2 mb-2">
            <span class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md ${catBadgeClass}">
              ${event.category}
            </span>
            <span class="text-xs font-bold text-emerald-300 flex items-center gap-1">
              ${timeInfo}
            </span>
          </div>

          <!-- Titre -->
          <h3 class="text-base sm:text-lg font-bold text-white leading-snug mb-2 cursor-pointer hover:text-blue-300 transition" onclick="openModal('${event.id}')">
            ${event.title}
          </h3>

          <!-- Résumé -->
          <p class="text-xs sm:text-sm text-blue-100/90 leading-relaxed line-clamp-3 mb-3">
            ${event.summary}
          </p>

          <!-- Lieu -->
          <div class="flex items-center gap-1 text-xs text-blue-200">
            <span>📍</span>
            <span class="truncate font-medium">${event.location || "Dunières"}</span>
          </div>
        </div>
      </div>

      <!-- Pied de carte Aujourd'hui -->
      <div class="p-4 bg-black/20 border-t border-white/10 flex items-center justify-between gap-2 mt-auto">
        <div>${attachmentAction}</div>
        <button onclick="openModal('${event.id}')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white text-blue-900 hover:bg-blue-50 transition shadow-sm flex items-center gap-1">
          <span>Détail complet</span>
          <span>➔</span>
        </button>
      </div>
    </article>
  `;
}

/**
 * 2. LE VRAI CALENDRIER VISUEL (Frise des 31 jours : -15j à +15j)
 */
function renderCalendarStrip() {
  const strip = document.getElementById("calendar-days-strip");
  if (!strip || !todayDateStr) return;

  const today = parseISODate(todayDateStr);
  const days = [];

  // Génération de 31 jours : de J-15 à J+15
  for (let offset = -15; offset <= 15; offset++) {
    const cur = new Date(today);
    cur.setDate(today.getDate() + offset);
    const iso = cur.toISOString().split("T")[0];
    const eventsOnDay = getEventsForDate(iso);

    days.push({
      date: cur,
      iso: iso,
      offset: offset,
      isToday: offset === 0,
      isSelected: iso === selectedDateStr,
      eventsCount: eventsOnDay.length,
      sampleTime: eventsOnDay.length > 0 ? extractEventTime(eventsOnDay[0], true) : null
    });
  }

  strip.innerHTML = days.map(d => {
    const jourSem = JOURS_SEMAINE[d.date.getDay()];
    const numJour = d.date.getDate();
    const mois = MOIS_FR[d.date.getMonth()];

    // Styles selon le statut
    let cardStyle = "bg-white text-slate-700 border-slate-200 hover:border-blue-400 hover:bg-blue-50/40";
    let badgeStyle = "bg-slate-100 text-slate-500";

    if (d.isSelected) {
      cardStyle = "bg-blue-600 text-white border-blue-600 shadow-md scale-105 z-10";
      badgeStyle = "bg-white/20 text-white font-bold";
    } else if (d.isToday) {
      cardStyle = "bg-blue-50 text-blue-900 border-blue-400 ring-2 ring-blue-500/30";
      badgeStyle = "bg-blue-600 text-white font-bold";
    }

    // Indicateur d'événements
    let indicatorHtml = `<span class="text-[10px] text-slate-400 mt-1 block">Libre</span>`;
    if (d.eventsCount > 0) {
      const dotColor = d.isSelected ? "bg-white" : "bg-emerald-500";
      const timeLabel = d.sampleTime ? d.sampleTime : `${d.eventsCount} prévu(s)`;
      indicatorHtml = `
        <div class="flex items-center gap-1 justify-center mt-1">
          <span class="w-2 h-2 rounded-full ${dotColor}"></span>
          <span class="text-[10px] font-bold ${d.isSelected ? 'text-white' : 'text-emerald-700'}">${timeLabel}</span>
        </div>
      `;
    }

    return `
      <div 
        onclick="selectCalendarDay('${d.iso}')"
        id="day-chip-${d.iso}"
        class="shrink-0 w-20 sm:w-24 p-2.5 rounded-2xl border text-center cursor-pointer transition-all duration-200 snap-start flex flex-col justify-between ${cardStyle}"
      >
        <div>
          <span class="text-[11px] font-semibold block uppercase tracking-wide opacity-80">
            ${jourSem}
          </span>
          <span class="text-xl sm:text-2xl font-black block my-0.5">
            ${numJour}
          </span>
          <span class="text-[10px] font-medium block opacity-75">
            ${mois}
          </span>
        </div>

        <div>
          ${d.isToday ? `<span class="inline-block text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded-md ${badgeStyle} mt-1">Aujourd'hui</span>` : indicatorHtml}
        </div>
      </div>
    `;
  }).join("");

  // Défilement automatique centré sur Aujourd'hui
  setTimeout(() => {
    const todayEl = document.getElementById(`day-chip-${todayDateStr}`);
    if (todayEl) {
      todayEl.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
    }
  }, 100);
}

/**
 * Sélection d'un jour spécifique sur la frise
 */
function selectCalendarDay(isoDate) {
  selectedDateStr = isoDate;
  renderCalendarStrip();
  renderSelectedDayEvents();
}

/**
 * Rendu des événements du jour sélectionné
 */
function renderSelectedDayEvents() {
  const container = document.getElementById("selected-day-events");
  const title = document.getElementById("selected-day-title");
  const subtitle = document.getElementById("selected-day-subtitle");
  const countBadge = document.getElementById("selected-day-count-badge");
  const emptyState = document.getElementById("selected-day-empty");
  if (!container) return;

  const d = parseISODate(selectedDateStr);
  const dateFormatted = `${capitalize(d.toLocaleDateString("fr-FR", { weekday: "long" }))} ${d.getDate()} ${MOIS_LONGS[d.getMonth()]} ${d.getFullYear()}`;

  if (title) title.textContent = `Programme du ${dateFormatted}`;

  const events = getEventsForDate(selectedDateStr).filter(matchesFilters);
  if (countBadge) countBadge.textContent = `${events.length} événement(s)`;

  if (subtitle) {
    if (selectedDateStr === todayDateStr) {
      subtitle.textContent = "Événements et arrêtés en vigueur aujourd'hui à Dunières";
    } else if (selectedDateStr < todayDateStr) {
      subtitle.textContent = "Rétrospective des événements et décisions passés";
    } else {
      subtitle.textContent = "Manifestations, réunions et activités à venir";
    }
  }

  if (events.length === 0) {
    container.innerHTML = "";
    if (emptyState) {
      emptyState.classList.remove("hidden");
      emptyState.textContent = `Aucun événement n'est programmé le ${dateFormatted}.`;
    }
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");
  container.innerHTML = events.map(e => createStandardEventCard(e)).join("");
}

function renderAllEventsGrid() {
  const container = document.getElementById("all-events-grid");
  const countLabel = document.getElementById("all-events-count");
  if (!container) return;

  const filtered = allEventsList.filter(matchesFilters);
  if (countLabel) countLabel.textContent = `${filtered.length} publication(s)`;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500 bg-white rounded-2xl border border-slate-200 text-sm">
        Aucun résultat ne correspond à votre recherche ou catégorie sélectionnée.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(e => createStandardEventCard(e)).join("");
}

/**
 * Carte d'événement standard avec bouton "Détail complet"
 */
function createStandardEventCard(event) {
  const timeInfo = extractEventTime(event);
  const catClass = getCategoryBadgeClass(event.category);
  const dateStr = formatEventDate(event.dates);

  return `
    <article class="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col justify-between overflow-hidden">
      <div class="p-4 sm:p-5">
        <div class="flex items-center justify-between gap-2 mb-2.5">
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-lg ${catClass}">
            ${event.category}
          </span>
          <span class="text-xs text-slate-500 font-semibold">
            ${timeInfo}
          </span>
        </div>

        <h4 class="text-base font-bold text-slate-900 leading-snug mb-2 cursor-pointer hover:text-blue-600 transition" onclick="openModal('${event.id}')">
          ${event.title}
        </h4>

        <p class="text-xs text-slate-600 leading-relaxed line-clamp-3 mb-3">
          ${event.summary}
        </p>

        <div class="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
          <span class="truncate">📍 ${event.location || "Dunières"}</span>
          <span class="shrink-0 text-slate-400">📅 ${dateStr}</span>
        </div>
      </div>

      <div class="px-4 py-2.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-2">
        <span class="text-[11px] text-slate-500 truncate">
          ${event.source_name}
        </span>
        <button onclick="openModal('${event.id}')" class="px-3 py-1 rounded-lg text-xs font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 transition">
          Consulter ➔
        </button>
      </div>
    </article>
  `;
}

/**
 * 4. MODALE D'AFFICHAGE DU DÉTAIL COMPLET DE L'ÉVÉNEMENT
 */
function openModal(eventId) {
  const event = allEventsList.find(e => e.id === eventId);
  if (!event) return;

  activeModalEvent = event;
  const modal = document.getElementById("event-modal");
  const card = document.getElementById("modal-card");

  // Remplissage des champs de la modale
  document.getElementById("modal-title").textContent = event.title;
  document.getElementById("modal-description").textContent = event.summary;
  document.getElementById("modal-category-badge").textContent = event.category;
  document.getElementById("modal-category-badge").className = `px-2.5 py-1 rounded-lg text-xs font-bold ${getCategoryBadgeClass(event.category)}`;
  document.getElementById("modal-badge-label").textContent = event.badge || "Information";
  document.getElementById("modal-date").textContent = formatEventDate(event.dates, true);
  document.getElementById("modal-time").textContent = extractEventTime(event, false, true);
  document.getElementById("modal-location").textContent = event.location || "Dunières / Haut Pays du Velay";
  
  // Source originale
  const sourceLink = document.getElementById("modal-source-link");
  const sourceName = document.getElementById("modal-source-name");
  sourceLink.href = event.source_url;
  sourceName.textContent = event.source_name;

  // Image d'en-tête
  const imgContainer = document.getElementById("modal-image-container");
  const img = document.getElementById("modal-image");
  if (event.image_url) {
    img.src = event.image_url;
    img.alt = event.title;
    imgContainer.classList.remove("hidden");
  } else {
    imgContainer.classList.add("hidden");
  }

  // Bloc Document Résolu (Calaméo ou PDF)
  const attachBlock = document.getElementById("modal-attachment-block");
  const attachLink = document.getElementById("modal-attachment-link");
  const attachDesc = document.getElementById("modal-attachment-desc");

  if (event.has_attachment && event.attachment_data) {
    attachBlock.classList.remove("hidden");
    if (event.attachment_type === "calameo") {
      attachDesc.textContent = `Ce document correspond à la publication complète "${event.attachment_data.title || 'Agenda Calaméo'}" (liste des villages, programme et contacts).`;
      attachLink.href = event.attachment_data.original_url || event.source_url;
      attachLink.innerHTML = "<span>📖 Ouvrir l'agenda Calaméo officiel</span> <span>↗</span>";
    } else if (event.attachment_type === "pdf") {
      attachDesc.textContent = "Un arrêté municipal ou document réglementaire PDF est associé à cette parution.";
      attachLink.href = event.attachment_data.original_url || event.source_url;
      attachLink.innerHTML = "<span>📄 Télécharger l'arrêté officiel PDF</span> <span>↗</span>";
    }
  } else {
    attachBlock.classList.add("hidden");
  }

  // Animation d'ouverture
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.remove("opacity-0");
    card.classList.remove("scale-95");
  }, 10);
  document.body.style.overflow = "hidden";
}

function closeModal() {
  const modal = document.getElementById("event-modal");
  const card = document.getElementById("modal-card");
  if (!modal) return;

  modal.classList.add("opacity-0");
  card.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
    activeModalEvent = null;
  }, 200);
}

function shareModalEvent() {
  if (!activeModalEvent) return;
  const shareData = {
    title: activeModalEvent.title,
    text: `${activeModalEvent.title} - Portail Citoyen de Dunières`,
    url: activeModalEvent.source_url
  };
  if (navigator.share) {
    navigator.share(shareData).catch(() => {});
  } else {
    navigator.clipboard.writeText(`${activeModalEvent.title} : ${activeModalEvent.source_url}`);
    alert("Lien de l'événement copié dans le presse-papier !");
  }
}

/**
 * 5. FONCTIONS UTILITAIRES DE GESTION DES DATES ET HEURES
 */

/**
 * Renvoie tous les événements actifs à une date précise (YYYY-MM-DD)
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
 * Extrait les mentions d'heures (ex: "14h30", "de 9h à 18h", "20h")
 */
function extractEventTime(event, compact = false, fullVerbose = false) {
  const text = `${event.title} ${event.summary}`;
  
  // Regex pour horaires en français
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
      pill.className = "cat-pill shrink-0 px-3 py-1.5 rounded-lg font-medium bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100";
    }
  });

  renderTodaySection();
  renderSelectedDayEvents();
  renderAllEventsGrid();
}

function scrollToToday() {
  selectedDateStr = todayDateStr;
  renderCalendarStrip();
  renderSelectedDayEvents();
  const hero = document.getElementById("today-hero-section");
  if (hero) hero.scrollIntoView({ behavior: "smooth" });
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

function capitalize(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}
