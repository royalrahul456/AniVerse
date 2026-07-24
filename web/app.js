// Initialize Telegram Web App SDK
const tg = window.Telegram.WebApp;
tg.expand(); // Open in full screen height

// API Server configuration
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8080'
    : 'https://aniverse-bot-cjvr.onrender.com';
// Fallback user ID for previewing in desktop browsers
let userId = 6593485710; // Default fallback to Admin ID
if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userId = tg.initDataUnsafe.user.id;
}

// State variables
let userProfile = null;
let haremList = [];
let filteredHarem = [];

// DOM Elements
const userNameEl = document.getElementById("user-name");
const userTagEl = document.getElementById("user-tag");
const statCoinsEl = document.getElementById("stat-coins");
const statCatchesEl = document.getElementById("stat-catches");
const searchInput = document.getElementById("search-input");
const filterRarity = document.getElementById("filter-rarity");
const sortOrder = document.getElementById("sort-order");
const loadingIndicator = document.getElementById("loading-indicator");
const noResults = document.getElementById("no-results");
const cardsGrid = document.getElementById("cards-grid");

// Initialize application
async function init() {
    try {
        await fetchProfile();
        await fetchHarem();
        setupEventListeners();
    } catch (err) {
        console.error("Initialization failed:", err);
    }
}

// Fetch user profile statistics
async function fetchProfile() {
    try {
        const response = await fetch(`${API_BASE}/api/profile/${userId}`);
        if (!response.ok) throw new Error("Profile fetch failed");
        
        userProfile = await response.json();
        
        // Render profile card
        userNameEl.textContent = userProfile.first_name;
        userTagEl.textContent = userProfile.custom_tag || "Novice Trainer";
        statCoinsEl.textContent = userProfile.coins.toLocaleString();
        statCatchesEl.textContent = userProfile.total_catches.toLocaleString();
    } catch (err) {
        console.error("Error loading profile:", err);
        // Fallback ui values on error
        userNameEl.textContent = tg.initDataUnsafe?.user?.first_name || "Trainer";
    }
}

// Fetch user harem character list
async function fetchHarem() {
    try {
        const response = await fetch(`${API_BASE}/api/harem/${userId}`);
        if (!response.ok) throw new Error("Harem fetch failed");
        
        const data = await response.json();
        haremList = data.harem || [];
        filteredHarem = [...haremList];
        
        // Hide loading indicator
        loadingIndicator.classList.add("hidden");
        
        // Populate Rarity filter options
        populateRarityFilter();
        
        // Render card collection
        renderCards();
    } catch (err) {
        console.error("Error loading harem:", err);
        loadingIndicator.innerHTML = `
            <p style="color: #ff7675;">⚠️ Failed to load collection.</p>
            <p style="font-size: 11px; margin-top: 8px;">Please check if API URL is correct or server is awake.</p>
        `;
    }
}

// Populate rarity select input dynamic choices
function populateRarityFilter() {
    const rarities = new Set(haremList.map(c => c.rarity));
    // Clear dynamic options, keep 'ALL'
    filterRarity.innerHTML = '<option value="ALL">All Rarities</option>';
    
    rarities.forEach(rarity => {
        if (!rarity) return;
        const opt = document.createElement("option");
        opt.value = rarity.toLowerCase();
        opt.textContent = rarity;
        filterRarity.appendChild(opt);
    });
}

// Render dynamic character cards
function renderCards() {
    cardsGrid.innerHTML = "";
    
    if (filteredHarem.length === 0) {
        noResults.classList.remove("hidden");
        return;
    }
    
    noResults.classList.add("hidden");
    
    filteredHarem.forEach(char => {
        const card = document.createElement("div");
        const rarityClass = `rarity-${char.rarity.toLowerCase()}`;
        card.className = `char-card ${rarityClass}`;
        
        // Fallback default avatar image if image_url is missing
        const imgUrl = char.image_url && char.image_url.startsWith("http") 
            ? char.image_url 
            : "https://cdn.pixabay.com/photo/2022/12/01/04/35/anime-7628313_1280.jpg";
            
        card.innerHTML = `
            <div class="char-image-container">
                <img class="char-image" src="${imgUrl}" alt="${char.name}" loading="lazy">
            </div>
            <div class="char-info">
                <span class="char-name">${char.name}</span>
                <span class="char-anime">${char.anime}</span>
                <div class="char-footer">
                    <span class="char-rarity-badge">${char.rarity_emoji} ${char.rarity}</span>
                    ${char.count > 1 ? `<span class="char-count-badge">x${char.count}</span>` : ""}
                </div>
            </div>
        `;
        
        // Haptic feedback feedback on card tap
        card.addEventListener("click", () => {
            if (tg.HapticFeedback) {
                tg.HapticFeedback.impactOccurred("light");
            }
        });
        
        cardsGrid.appendChild(card);
    });
}

// Setup Event Listeners for searching & sorting filters
function setupEventListeners() {
    searchInput.addEventListener("input", filterAndSort);
    filterRarity.addEventListener("change", filterAndSort);
    sortOrder.addEventListener("change", filterAndSort);
}

// Filter and Sort function
function filterAndSort() {
    const searchVal = searchInput.value.toLowerCase().trim();
    const rarityVal = filterRarity.value.toLowerCase();
    const sortVal = sortOrder.value;
    
    // 1. Filter
    filteredHarem = haremList.filter(char => {
        const matchesSearch = char.name.toLowerCase().includes(searchVal) || char.anime.toLowerCase().includes(searchVal);
        const matchesRarity = rarityVal === "all" || char.rarity.toLowerCase() === rarityVal;
        return matchesSearch && matchesRarity;
    });
    
    // 2. Sort
    filteredHarem.sort((a, b) => {
        if (sortVal === "id_asc") return a.id - b.id;
        if (sortVal === "id_desc") return b.id - a.id;
        if (sortVal === "count_desc") return b.count - a.count;
        
        if (sortVal === "name_asc") {
            return a.name.localeCompare(b.name);
        }
        return 0;
    });
    
    renderCards();
}

// Run app
init();
