/**
 * Application JavaScript pour le Portail Citoyen & Calendrier de Dunières.
 * Consomme web/data.json et gère le fenêtrage en 3 volets, filtres et recherche.
 */

let appData = null;
let currentTab = "today";
let currentCategory = "all";
let searchQuery = "";

// Initialisation au chargement de la page
document.addEventListener("DOMContentLoaded", () => {
  loadData();

  // Écouteur pour la barre de recherche
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderEvents();
    });
  }
});

/**
 * Charge les données depuis le fichier statique data.json
 */
async function loadData() {
  try {
    const res = await fetch("data.json?v=" + new Date().getTime());
    if (!res.ok) {
      throw new Error(`Erreur HTTP: ${res.status}`);
    }
    appData = await res.json();
    updateUIHeader();
    renderEvents();
  } catch (err) {
    console.error("Impossible de charger data.json:", err);
    showError("Le calendrier est en cours de mise à jour. Veuillez recharger la page dans quelques instants.");
  }
}

/**
 * Met à jour les compteurs et métadonnées du bandeau
 */
function updateUIHeader() {
  if (!appData || !appData.metadata) return;

  const counts = appData.metadata.counts || {};
  document.getElementById("count-retrospective").textContent = counts.retrospective || 0;
  document.getElementById("count-today").textContent = counts.today || 0;
  document.getElementById("count-upcoming").textContent = counts.upcoming || 0;

  if (appData.metadata.generated_at) {
    const d = new Date(appData.metadata.generated_at);
    const dateStr = d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
    const timeStr = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const badge = document.getElementById("update-badge");
    if (badge) {
      badge.textContent = `• Mis à jour le ${dateStr} à ${timeStr}`;
    }
  }
}

/**
 * Change de volet temporel (retrospective, today, upcoming)
 */
function switchTab(tabName) {
  currentTab = tabName;

  // Mise à jour visuelle des boutons d'onglets
  const tabs = ["retrospective", "today", "upcoming"];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    if (t === tabName) {
      btn.className = "tab-btn flex-1 min-w-[160px] sm:min-w-[200px] px-4 py-2.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 bg-blue-600 text-white shadow-md shadow-blue-500/20";
    } else {
      btn.className = "tab-btn flex-1 min-w-[160px] sm:min-w-[200px] px-4 py-2.5 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 bg-slate-100 text-slate-600 hover:bg-slate-200";
    }
  });

  // Mise à jour de la description du volet
  const titleElem = document.getElementById("volet-title");
  const descElem = document.getElementById("volet-desc");
  if (tabName === "retrospective") {
    titleElem.textContent = "⏪ Rétrospective des 15 Derniers Jours";
    descElem.textContent = "Retour sur les récents événements, arrêtés municipaux et actualités du territoire.";
  } else if (tabName === "today") {
    titleElem.textContent = "📍 Informations & Événements d'Aujourd'hui";
    descElem.textContent = "Manifestations actives, permanences et travaux en cours à Dunières et aux alentours.";
  } else {
    titleElem.textContent = "⏩ Agenda Prévisionnel (+15 Jours)";
    descElem.textContent = "Prochaines festivités, réunions publiques, séances du conseil et rendez-vous associatifs.";
  }

  renderEvents();
}

/**
 * Définit le filtre par catégorie
 */
function setCategoryFilter(category) {
  currentCategory = category;

  // Mise à jour des styles des boutons pilules
  document.querySelectorAll(".cat-pill").forEach(pill => {
    if (pill.dataset.category === category) {
      pill.className = "cat-pill px-3 py-1.5 rounded-lg font-semibold bg-slate-800 text-white shadow-sm";
    } else {
      pill.className = "cat-pill px-3 py-1.5 rounded-lg font-medium bg-white text-slate-600 border border-slate-200 hover:bg-slate-100";
    }
  });

  renderEvents();
}

/**
 * Filtre et injecte les cartes d'événements
 */
function renderEvents() {
  const container = document.getElementById("events-grid");
  const emptyState = document.getElementById("empty-state");
  const countBadge = document.getElementById("events-visible-count");

  if (!appData || !appData.buckets) {
    container.innerHTML = "";
    emptyState.classList.remove("hidden");
    countBadge.textContent = "0 affiché(s)";
    return;
  }

  // Récupération de la liste brute pour le volet actif
  const list = appData.buckets[currentTab] || [];

  // Application des filtres : Catégorie + Recherche
  const filtered = list.filter(item => {
    const matchCat = currentCategory === "all" || item.category === currentCategory;
    const matchSearch = !searchQuery || 
      item.title.toLowerCase().includes(searchQuery) ||
      (item.summary && item.summary.toLowerCase().includes(searchQuery)) ||
      (item.location && item.location.toLowerCase().includes(searchQuery)) ||
      (item.badge && item.badge.toLowerCase().includes(searchQuery));
    return matchCat && matchSearch;
  });

  countBadge.textContent = `${filtered.length} affiché(s)`;

  if (filtered.length === 0) {
    container.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");
  container.innerHTML = filtered.map(createEventCard).join("");
}

/**
 * Génère le code HTML d'une carte d'événement
 */
function createEventCard(event) {
  const catClass = getCategoryBadgeClass(event.category);
  const formattedDate = formatEventDate(event.dates);

  // Bouton document externe (Calaméo ou PDF)
  let attachmentBtn = "";
  if (event.has_attachment && event.attachment_data) {
    if (event.attachment_type === "calameo") {
      const calameoUrl = event.attachment_data.original_url || event.source_url;
      attachmentBtn = `
        <a href="${calameoUrl}" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition border border-indigo-200">
          <span>📖</span>
          <span>Lire l'agenda Calaméo</span>
        </a>
      `;
    } else if (event.attachment_type === "pdf") {
      const pdfUrl = event.attachment_data.original_url || event.source_url;
      attachmentBtn = `
        <a href="${pdfUrl}" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 transition border border-rose-200">
          <span>📄</span>
          <span>Consulter l'arrêté PDF</span>
        </a>
      `;
    }
  }

  // Image d'illustration ou couverture Calaméo
  const imageHtml = event.image_url ? `
    <div class="h-44 w-full overflow-hidden rounded-t-2xl bg-slate-100 relative">
      <img src="${event.image_url}" alt="${event.title}" class="w-full h-full object-cover transition-transform duration-300 hover:scale-105" loading="lazy">
      <span class="absolute top-3 right-3 text-xs font-semibold px-2.5 py-1 rounded-full shadow-sm bg-white/90 backdrop-blur text-slate-700">
        ${event.badge || "Info"}
      </span>
    </div>
  ` : "";

  return `
    <article class="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col justify-between overflow-hidden">
      <div>
        ${imageHtml}
        <div class="p-5">
          <!-- En-tête de la carte : Catégorie & Date -->
          <div class="flex items-center justify-between gap-2 mb-2.5">
            <span class="text-xs font-bold px-2.5 py-1 rounded-lg ${catClass}">
              ${event.category}
            </span>
            <span class="text-xs text-slate-500 font-medium">
              📅 ${formattedDate}
            </span>
          </div>

          <!-- Titre -->
          <h3 class="text-base sm:text-lg font-bold text-slate-900 leading-snug mb-2 hover:text-blue-600 transition">
            <a href="${event.source_url}" target="_blank" rel="noopener">
              ${event.title}
            </a>
          </h3>

          <!-- Résumé structuré -->
          <p class="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
            ${event.summary}
          </p>

          <!-- Lieu -->
          <div class="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
            <span>📍</span>
            <span class="font-medium">${event.location || "Dunières"}</span>
          </div>
        </div>
      </div>

      <!-- Pied de carte : Actions et Source -->
      <div class="px-5 pb-5 pt-2 border-t border-slate-100 flex items-center justify-between gap-2 mt-auto">
        <div class="flex flex-wrap gap-2">
          ${attachmentBtn}
          <a href="${event.source_url}" target="_blank" rel="noopener" class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-blue-600 hover:bg-slate-50 transition">
            <span>🔗 Source :</span>
            <span class="truncate max-w-[110px]">${event.source_name}</span>
          </a>
        </div>
      </div>
    </article>
  `;
}

/**
 * Stylisation des badges par catégorie
 */
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

/**
 * Formatage des dates en français
 */
function formatEventDate(dates) {
  if (!dates || !dates.start) return "Date à préciser";

  const parseISODate = (str) => {
    const parts = str.split("-");
    if (parts.length === 3) {
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }
    return new Date(str);
  };

  const dStart = parseISODate(dates.start);
  const options = { day: "numeric", month: "short" };

  if (dates.is_period && dates.end) {
    const dEnd = parseISODate(dates.end);
    return `Du ${dStart.toLocaleDateString("fr-FR", options)} au ${dEnd.toLocaleDateString("fr-FR", options)}`;
  }

  return dStart.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
}

function showError(msg) {
  const container = document.getElementById("events-grid");
  if (container) {
    container.innerHTML = `
      <div class="col-span-full p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-center text-sm">
        ${msg}
      </div>
    `;
  }
}
