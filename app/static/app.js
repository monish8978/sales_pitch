// Initialize Lucide Icons
lucide.createIcons();

// DOM References
const emailInput = document.getElementById('prospect-email');
const phoneInput = document.getElementById('prospect-phone');
const generatePitchBtn = document.getElementById('generate-pitch-btn');
const quickFillBtn = document.getElementById('quick-fill-btn');

// Sidebar View States
const sidebarEmpty = document.getElementById('sidebar-empty');
const sidebarLoader = document.getElementById('sidebar-loader');
const sidebarContent = document.getElementById('sidebar-content');

// Loader status elements
const loaderApolloStatus = document.getElementById('loader-apollo-status');
const loaderLlmStatus = document.getElementById('loader-llm-status');

// Output DOM elements
const contactFirstName = document.getElementById('contact-first-name');
const contactLastName = document.getElementById('contact-last-name');
const contactCompany = document.getElementById('contact-company');
const prospectAvatar = document.getElementById('prospect-avatar');
const prospectName = document.getElementById('prospect-name');
const prospectTitle = document.getElementById('prospect-title');
const prospectCompany = document.getElementById('prospect-company');
const prospectIndustry = document.getElementById('prospect-industry');
const prospectLocation = document.getElementById('prospect-location');
const prospectEmployees = document.getElementById('prospect-employees');
const prospectLinkedin = document.getElementById('prospect-linkedin');

// Telemetry Timing DOM elements
const telemetryApolloTime = document.getElementById('telemetry-apollo-time');
const telemetryApolloSource = document.getElementById('telemetry-apollo-source');
const telemetryLlmTime = document.getElementById('telemetry-llm-time');
const telemetryLlmSource = document.getElementById('telemetry-llm-source');
const telemetryTotalTime = document.getElementById('telemetry-total-time');

// Analysis Output DOM elements
const analysisSummary = document.getElementById('analysis-summary');
const analysisInsights = document.getElementById('analysis-insights');
const analysisPitch = document.getElementById('analysis-pitch');

// Action Buttons
const copyPitchBtn = document.getElementById('copy-pitch-btn');
const speakPitchBtn = document.getElementById('speak-pitch-btn');
const ttsIcon = document.getElementById('tts-icon');
const copyIcon = document.getElementById('copy-icon');

// Settings Modal elements
const toggleSettingsBtn = document.getElementById('toggle-settings-btn');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const settingsModal = document.getElementById('settings-modal');
const saveSettingsBtn = document.getElementById('save-settings-btn');

const briefCompany = document.getElementById('brief-company');
const briefServices = document.getElementById('brief-services');
const briefValueProps = document.getElementById('brief-value-props');

// State Management
let currentUtterance = null;
let isSpeaking = false;

// 1. Local Storage Management for Configurations
function loadConfig() {
    const config = JSON.parse(localStorage.getItem('sales_copilot_config') || '{}');

    if (config.company) briefCompany.value = config.company;
    if (config.services) briefServices.value = config.services;
    if (config.valueProps) briefValueProps.value = config.valueProps;
}

function saveConfig() {
    const config = {
        company: briefCompany.value.trim(),
        services: briefServices.value.trim(),
        valueProps: briefValueProps.value.trim()
    };
    
    localStorage.setItem('sales_copilot_config', JSON.stringify(config));
    
    // Animate save button feedback
    const originalText = saveSettingsBtn.textContent;
    saveSettingsBtn.textContent = 'Config Saved!';
    saveSettingsBtn.classList.remove('bg-indigo-600', 'hover:bg-indigo-500');
    saveSettingsBtn.classList.add('bg-emerald-600', 'hover:bg-emerald-500');
    
    setTimeout(() => {
        saveSettingsBtn.textContent = originalText;
        saveSettingsBtn.classList.remove('bg-emerald-600', 'hover:bg-emerald-500');
        saveSettingsBtn.classList.add('bg-indigo-600', 'hover:bg-indigo-500');
        settingsModal.classList.add('hidden');
    }, 1000);
}

// 2. Settings Modal Events
toggleSettingsBtn.addEventListener('click', () => {
    settingsModal.classList.remove('hidden');
});

closeSettingsBtn.addEventListener('click', () => {
    settingsModal.classList.add('hidden');
});

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
        settingsModal.classList.add('hidden');
    }
});

saveSettingsBtn.addEventListener('click', saveConfig);

// 3. Demo lead pre-fill function
function setDemoLead(email, phone) {
    emailInput.value = email;
    phoneInput.value = phone;
    
    // Add glowing effect to inputs to indicate populate
    emailInput.classList.add('ring-2', 'ring-indigo-500/50');
    phoneInput.classList.add('ring-2', 'ring-indigo-500/50');
    
    setTimeout(() => {
        emailInput.classList.remove('ring-2', 'ring-indigo-500/50');
        phoneInput.classList.remove('ring-2', 'ring-indigo-500/50');
    }, 1500);

    // Auto-trigger generation
    handleGenerate();
}

// Attach setDemoLead to window object so it's accessible by inline onclick attributes
window.setDemoLead = setDemoLead;

// Load demo Leads quickfill cycle
const demoLeads = [
    { email: "arijit@c-zentrix.com", phone: "+919845244545" },
    { email: "sundar@google.com", phone: "+16502530000" },
    { email: "sarah.smith@techflow.io", phone: "+14159846281" }
];
let demoIndex = 0;

quickFillBtn.addEventListener('click', () => {
    const lead = demoLeads[demoIndex];
    setDemoLead(lead.email, lead.phone);
    demoIndex = (demoIndex + 1) % demoLeads.length;
});

// 4. MAIN GENERATION PIPELINE
async function handleGenerate() {
    const email = emailInput.value.trim();
    const phone = phoneInput.value.trim();

    if (!email && !phone) {
        alert('Please provide at least an Email address or Phone number to lookup the prospect.');
        return;
    }

    // Stop speaking if currently active
    stopTTS();

    // 1. Shift View States
    sidebarEmpty.classList.add('hidden');
    sidebarContent.classList.add('hidden');
    sidebarLoader.classList.remove('hidden');

    // Reset loader text
    loaderApolloStatus.textContent = 'Queueing Job...';
    loaderApolloStatus.className = 'text-amber-400 font-medium';
    loaderLlmStatus.textContent = 'Pending';
    loaderLlmStatus.className = 'text-slate-600';

    // Retrieve active keys from LocalStorage Config
    const config = JSON.parse(localStorage.getItem('sales_copilot_config') || '{}');
    const apolloKey = '';
    const groqKey = '';

    try {
        const payload = {
            email: email,
            phone: phone,
            apollo_api_key: apolloKey,
            groq_api_key: groqKey
        };

        const response = await fetch('/api/generate-pitch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            let errorMsg = `Server returned code ${response.status}`;
            try {
                const errJson = await response.json();
                if (errJson.detail) errorMsg = errJson.detail;
            } catch (e) {}
            throw new Error(errorMsg);
        }

        const data = await response.json();
        
        // Show Apollo done, LLM start
        loaderApolloStatus.textContent = 'Success';
        loaderApolloStatus.className = 'text-emerald-500 font-semibold';
        loaderLlmStatus.textContent = 'Synthesizing Pitch...';
        loaderLlmStatus.className = 'text-amber-400 font-medium';

        // Brief delay for transition smooth experience
        await new Promise(resolve => setTimeout(resolve, 600));

        loaderLlmStatus.textContent = 'Done';
        loaderLlmStatus.className = 'text-emerald-500 font-semibold';

        await new Promise(resolve => setTimeout(resolve, 400));

        // Render response data
        renderOutput(data);

    } catch (error) {
        console.error('Error generating pitch:', error);
        alert(`Failed to generate pitch. ${error.message || ''}`);
        
        // Fallback to empty state
        sidebarLoader.classList.add('hidden');
        sidebarEmpty.classList.remove('hidden');
    }
}

// Attach main listener
generatePitchBtn.addEventListener('click', handleGenerate);

// 5. RENDER SYSTEM
function renderOutput(data) {
    const prospect = data.prospect;
    const analysis = data.analysis;
    const timing = data.timing;

    // Update CRM Mock Fields
    const nameParts = prospect.name.split(' ');
    contactFirstName.value = nameParts[0] || '';
    contactLastName.value = nameParts.slice(1).join(' ') || '';
    contactCompany.value = prospect.company?.name || '';

    // Render Avatar / Initials
    if (prospect.photo_url) {
        prospectAvatar.innerHTML = `<img src="${prospect.photo_url}" alt="photo" class="w-full h-full object-cover rounded-xl">`;
    } else {
        const initials = prospect.name
            .split(' ')
            .map(n => n[0])
            .join('')
            .substring(0, 2)
            .toUpperCase();
        prospectAvatar.textContent = initials;
    }

    // Profile Metadata
    prospectName.textContent = prospect.name;
    prospectTitle.textContent = prospect.title;
    
    prospectCompany.innerHTML = `<i data-lucide="building" class="w-3 h-3 mr-1"></i>${prospect.company.name}`;
    prospectIndustry.innerHTML = `<i data-lucide="tag" class="w-3 h-3 mr-1"></i>${prospect.company.industry}`;
    prospectEmployees.innerHTML = `<i data-lucide="users" class="w-3 h-3 mr-1"></i>${prospect.company.employee_count} Employees`;
    
    if (prospect.location) {
        prospectLocation.innerHTML = `<i data-lucide="map-pin" class="w-3 h-3 mr-1"></i>${prospect.location}`;
        prospectLocation.classList.remove('hidden');
    } else {
        prospectLocation.classList.add('hidden');
    }

    // LinkedIn Link
    if (prospect.linkedin_url) {
        prospectLinkedin.href = prospect.linkedin_url;
        prospectLinkedin.classList.remove('hidden');
    } else {
        prospectLinkedin.classList.add('hidden');
    }

    // Latency Dashboard
    telemetryApolloTime.textContent = timing.apollo_time;
    telemetryApolloSource.textContent = timing.apollo_source;
    
    // Source styles logic
    if (timing.apollo_source === 'live') {
        telemetryApolloSource.className = 'text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/10 text-emerald-400 block truncate';
    } else {
        telemetryApolloSource.className = 'text-[9px] px-1.5 py-0.5 rounded bg-indigo-950/40 border border-indigo-500/10 text-indigo-400 block truncate';
    }

    telemetryLlmTime.textContent = timing.llm_time;
    telemetryLlmSource.textContent = timing.llm_source;
    
    if (timing.llm_source === 'live') {
        telemetryLlmSource.className = 'text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/10 text-emerald-400 block truncate';
    } else {
        telemetryLlmSource.className = 'text-[9px] px-1.5 py-0.5 rounded bg-indigo-950/40 border border-indigo-500/10 text-indigo-400 block truncate';
    }

    telemetryTotalTime.textContent = timing.total_time;

    // AI Contents
    analysisSummary.textContent = analysis.summary;

    // Insights rendering
    analysisInsights.innerHTML = '';
    analysis.insights.forEach((insight, index) => {
        const li = document.createElement('li');
        li.className = 'flex items-start space-x-2.5';
        li.innerHTML = `
            <span class="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-950/60 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-[10px] font-bold mt-0.5">${index + 1}</span>
            <span class="text-slate-300 leading-normal">${insight}</span>
        `;
        analysisInsights.appendChild(li);
    });

    // Pitch Script
    analysisPitch.textContent = analysis.pitch;

    // Refresh icons (since we injected HTML dynamically)
    lucide.createIcons();

    // Transition loaders out
    sidebarLoader.classList.add('hidden');
    sidebarContent.classList.remove('hidden');
}

// 6. UTILITY - Copy to Clipboard
copyPitchBtn.addEventListener('click', () => {
    const pitchText = analysisPitch.textContent.trim();
    navigator.clipboard.writeText(pitchText).then(() => {
        // Switch copy icon to success checkmark
        copyIcon.setAttribute('data-lucide', 'check');
        copyIcon.classList.remove('text-slate-400');
        copyIcon.classList.add('text-emerald-400');
        lucide.createIcons();

        setTimeout(() => {
            copyIcon.setAttribute('data-lucide', 'copy');
            copyIcon.classList.remove('text-emerald-400');
            copyIcon.classList.add('text-slate-400');
            lucide.createIcons();
        }, 2000);
    });
});

// 7. UTILITY - Text-to-Speech (TTS) Agent Coach
function stopTTS() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    ttsIcon.setAttribute('data-lucide', 'volume-2');
    speakPitchBtn.classList.remove('bg-indigo-600', 'text-white');
    speakPitchBtn.classList.add('bg-slate-900', 'text-slate-400');
    lucide.createIcons();
    isSpeaking = false;
}

function startTTS(text) {
    if (!window.speechSynthesis) {
        alert('Text-to-speech is not supported by your browser.');
        return;
    }

    window.speechSynthesis.cancel(); // Stop any pending speech

    currentUtterance = new SpeechSynthesisUtterance(text);
    
    // Choose standard english voice if available
    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => v.lang.startsWith('en-'));
    if (englishVoice) {
        currentUtterance.voice = englishVoice;
    }
    
    currentUtterance.rate = 1.05; // Slightly faster standard conversational speed
    currentUtterance.pitch = 1.0;

    currentUtterance.onend = () => {
        stopTTS();
    };

    currentUtterance.onerror = () => {
        stopTTS();
    };

    // Toggle button UI to active
    ttsIcon.setAttribute('data-lucide', 'square');
    speakPitchBtn.classList.remove('bg-slate-900', 'text-slate-400');
    speakPitchBtn.classList.add('bg-indigo-600', 'text-white');
    lucide.createIcons();

    window.speechSynthesis.speak(currentUtterance);
    isSpeaking = true;
}

speakPitchBtn.addEventListener('click', () => {
    if (isSpeaking) {
        stopTTS();
    } else {
        const text = analysisPitch.textContent.trim();
        startTTS(text);
    }
});

// Cancel speech if user navigates away or closes tab
window.addEventListener('beforeunload', stopTTS);

// On Startup
window.addEventListener('load', () => {
    loadConfig();
    // Pre-populate system with initial list trigger icons
    lucide.createIcons();
});
