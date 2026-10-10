    let allJobs = [];
    let currentPage = 1;
    const pageSize = 10;
    let filteredTotal = 0;
    let showBookmarksOnly = false;
    let selectedPlatform = '';
    let selectedMode = '';
    let selectedSort = 'newest';

    function toggleMobileNav() {
      const m = document.getElementById('mobileNavMenu');
      if (m) m.classList.toggle('hidden');
    }

    function togglePlatformMenu() {
      const menu = document.getElementById('sourceFilterMenu');
      menu.classList.toggle('hidden');
    }

    function toggleModeMenu() {
      document.getElementById('modeFilterMenu').classList.toggle('hidden');
    }

    function toggleSortMenu() {
      document.getElementById('sortFilterMenu').classList.toggle('hidden');
    }

    function selectPlatform(val, label) {
      selectedPlatform = val;
      document.getElementById('sourceFilterLabel').innerText = label;
      document.getElementById('sourceFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    function selectMode(val, label) {
      selectedMode = val;
      document.getElementById('modeFilterLabel').innerText = label;
      document.getElementById('modeFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    function selectSort(val, label) {
      selectedSort = val;
      document.getElementById('sortFilterLabel').innerText = label;
      document.getElementById('sortFilterMenu').classList.add('hidden');
      currentPage = 1;
      renderJobs();
    }

    document.addEventListener('click', function(e) {
      const wrapper = document.getElementById('customDropdownWrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        document.getElementById('sourceFilterMenu').classList.add('hidden');
      }
      const modeW = document.getElementById('modeDropdownWrapper');
      if (modeW && !modeW.contains(e.target)) {
        document.getElementById('modeFilterMenu').classList.add('hidden');
      }
      const sortW = document.getElementById('sortDropdownWrapper');
      if (sortW && !sortW.contains(e.target)) {
        document.getElementById('sortFilterMenu').classList.add('hidden');
      }
    });

    function getSavedIds() {
      try { return JSON.parse(localStorage.getItem('saved_jobs') || '[]'); } catch { return []; }
    }

    function toggleSaveJob(id) {
      let saved = getSavedIds();
      if (saved.includes(id)) { saved = saved.filter(x => x !== id); }
      else { saved.push(id); }
      localStorage.setItem('saved_jobs', JSON.stringify(saved));
      updateBookmarkUI();
      renderJobs();
    }

    function updateBookmarkUI() {
      const count = getSavedIds().length;
      const badge = document.getElementById('bookmarkCount');
      if (badge) badge.innerText = count;
    }

    function toggleBookmarksOnly() {
      showBookmarksOnly = !showBookmarksOnly;
      currentPage = 1;
      const btn = document.getElementById('bookmarkToggle');
      const indicator = document.getElementById('bookmarkIndicator');
      const badge = document.getElementById('bookmarkCount');
      if (showBookmarksOnly) {
        btn.className = 'bg-limepill text-black font-bold border border-limepill rounded-full pl-3.5 pr-4 py-2 text-xs tracking-wide focus:outline-none flex items-center gap-1.5 transition w-full md:w-auto';
        badge.className = 'ml-auto md:ml-0 text-[10px] text-black/60 font-mono font-bold';
        if (indicator) indicator.className = 'w-2 h-2 rounded-full bg-black';
      } else {
        btn.className = 'bg-neutral-900 text-neutral-200 hover:text-white border border-neutral-800 rounded-full pl-3.5 pr-4 py-2 text-xs font-bold tracking-wide focus:outline-none flex items-center gap-1.5 transition w-full md:w-auto';
        badge.className = 'ml-auto md:ml-0 text-[10px] text-limepill font-mono font-bold';
        if (indicator) indicator.className = 'w-2 h-2 rounded-full border border-neutral-500';
      }
      renderJobs();
    }
    
    function formatUpdatedDate(isoString) {
      if (!isoString) return '-';
      try {
        const d = new Date(isoString);
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        const dayName = days[d.getDay()];
        const date = d.getDate();
        const monthName = months[d.getMonth()];
        const year = d.getFullYear();
        const hours = String(d.getHours()).padStart(2, '0');
        const mins = String(d.getMinutes()).padStart(2, '0');
        return `${dayName}, ${date} ${monthName} ${year} • ${hours}:${mins} WIB`;
      } catch {
        return isoString;
      }
    }

    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('statTotal').innerText = data.totalJobs || '0';
        document.getElementById('statUpdated').innerText = formatUpdatedDate(data.lastUpdated);
        document.getElementById('statScraped').innerText = data.lastScrapedAt ? formatUpdatedDate(data.lastScrapedAt) : 'Running normally';
        const retEl = document.getElementById('statRetention');
        if (retEl && data.retentionDays) {
          const mb = data.dbBytes ? ` · ${(data.dbBytes / 1024 / 1024).toFixed(1)} MB` : '';
          retEl.innerText = `Auto-prune ${data.retentionDays}d${mb}`;
        }
        
        if (data.locations && data.locations.length) {
          const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
          const primaryLoc = cap(data.locations[0]);
          const modeEntry = data.locations.find(l => ['remote', 'hybrid', 'wfh'].includes(l.toLowerCase()));
          document.getElementById('heroSubtitle').innerText = `${primaryLoc} & ${cap(modeEntry || 'remote')}`;
          document.getElementById('heroStreamBadge').innerText = `${primaryLoc} Opportunities`;
          document.getElementById('envLocations').innerHTML = data.locations.map(l => 
            `<span class="bg-white border border-black/10 px-3 py-1 rounded-full capitalize font-extrabold tracking-tight text-neutral-600 shadow-sm" style="font-size:${chipFontSize(l)}">${l}</span>`
          ).join('');
        }
        if (data.keywords && data.keywords.length) {
          const toTitleCase = (s) => (s || '').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
          const words = data.keywords.map(toTitleCase);
          initTypewriter(words);
          document.getElementById('envKeywords').innerHTML = data.keywords.slice(0, 10).map(k => 
            `<span class="bg-limepill text-black border border-black/10 px-3 py-1 rounded-full font-extrabold tracking-tight shadow-sm whitespace-nowrap" style="font-size:${chipFontSize(k)}">${k}</span>`
          ).join('') + (data.keywords.length > 10 ? `<span class="text-neutral-500 text-[11px] font-bold self-center">+${data.keywords.length - 10} more</span>` : '');
        }

        const platforms = data.platforms || (data.sourceCounts ? Object.keys(data.sourceCounts) : []);
        if (data.sourceCounts) {
          const gridEl = document.getElementById('statSources');
          const rows = 2;
          const cols = Math.max(2, Math.ceil(platforms.length / rows));
          gridEl.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
          document.getElementById('statSources').innerHTML = Object.entries(data.sourceCounts)
            .map(([k, v]) => `<span class="flex items-center justify-between bg-neutral-900 text-neutral-200 border border-neutral-700/80 px-2 py-1 rounded-full text-[11px] font-semibold tracking-wide min-w-0"><span class="truncate">${k}</span><span class="bg-limepill text-black font-black px-1.5 py-0.2 rounded-full text-[10px] ml-auto shrink-0">${v}</span></span>`).join('');
          
          if (platforms.length) {
            document.getElementById('platformCountBadge').innerText = `${platforms.length} Aggregators`;
            const displayedPlatforms = platforms.length > 6 
              ? `${platforms.slice(0, 6).join(', ')} +${platforms.length - 6} more`
              : platforms.join(', ');
            document.getElementById('platformNamesBanner').innerText = `Continuous automated aggregation across ${displayedPlatforms}.`;
            
            const menuEl = document.getElementById('sourceFilterMenu');
            menuEl.innerHTML = `
              <div onclick="selectPlatform('', 'All Platforms')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-200 cursor-pointer flex items-center justify-between transition">
                <span>All Platforms</span>
              </div>` +
              platforms.map(s => `
                <div onclick="selectPlatform('${s}', '${s} (${data.sourceCounts[s] || 0})')" class="px-4 py-2 hover:bg-neutral-800 text-neutral-300 hover:text-white cursor-pointer flex items-center justify-between transition">
                  <span>${s}</span>
                  <span class="text-[10px] bg-neutral-800 px-1.5 py-0.5 rounded-full text-neutral-400">${data.sourceCounts[s] || 0}</span>
                </div>
              `).join('');
          }
        }
      } catch (e) { console.error(e); }
    }

    async function loadJobs() {
      try {
        // ponytail: initial fetch 100 jobs to avoid long JSON parsing and chain latency on mobile. Add dynamic pagination query when dataset exceeds 500.
        const res = await fetch('/api/jobs?limit=100');
        const data = await res.json();
        allJobs = data.jobs || [];
        currentPage = 1;
        renderJobs();
      } catch (e) {
        document.getElementById('jobsList').innerHTML = '<div class="text-neutral-500 text-sm py-4">Failed to load opportunities.</div>';
      }
    }

    function formatSalary(j) {
      if (j.salary) return j.salary;
      if (j.salary_min && j.salary_max) {
        const min = (j.salary_min / 1000000).toFixed(j.salary_min % 1000000 === 0 ? 0 : 1);
        const max = (j.salary_max / 1000000).toFixed(j.salary_max % 1000000 === 0 ? 0 : 1);
        return `IDR ${min}M – ${max}M`;
      }
      if (j.salary_min) return `IDR ${(j.salary_min / 1000000).toFixed(0)}M+`;
      return 'NOT DISCLOSED';
    }

    function translateWorkType(val) {
      if (!val) return null;
      const lower = val.toLowerCase();
      if (lower.includes('kontrak') || lower.includes('sementara')) return 'CONTRACT';
      if (lower.includes('penuh') || lower.includes('full')) return 'FULL TIME';
      if (lower.includes('paruh') || lower.includes('part')) return 'PART TIME';
      if (lower.includes('magang') || lower.includes('intern')) return 'INTERNSHIP';
      return val.toUpperCase();
    }

    function translateWorkMode(val) {
      if (!val) return null;
      const lower = val.toLowerCase();
      if (lower.includes('remote')) return 'REMOTE';
      if (lower.includes('hybrid')) return 'HYBRID';
      if (lower.includes('on-site') || lower.includes('onsite')) return 'ON-SITE';
      return val.toUpperCase();
    }

    function renderJobs() {
      const q = (document.getElementById('searchInput').value || '').toLowerCase();
      const src = (selectedPlatform || '').toLowerCase();
      const mode = (selectedMode || '').toLowerCase();
      const savedIds = getSavedIds();
      
      let filtered = allJobs.filter(j => {
        const matchText = (j.title || '').toLowerCase().includes(q) || 
                          (j.company || '').toLowerCase().includes(q);
        const matchSrc = !src || (j.source || '').toLowerCase() === src;
        const matchMode = !mode || (j.work_mode || '').toLowerCase().includes(mode);
        const matchBookmark = !showBookmarksOnly || savedIds.includes(j.id);
        return matchText && matchSrc && matchMode && matchBookmark;
      });

      filtered.sort((a, b) => {
        if (selectedSort === 'salary_high') {
          const salA = a.salary_max || a.salary_min || 0;
          const salB = b.salary_max || b.salary_min || 0;
          return salB - salA;
        }
        if (selectedSort === 'title_asc') {
          return (a.title || '').localeCompare(b.title || '');
        }
        const dateA = a.posted_at || a.scraped_at || '';
        const dateB = b.posted_at || b.scraped_at || '';
        return dateB.localeCompare(dateA);
      });

      const total = filtered.length;
      filteredTotal = total;
      const totalPages = Math.ceil(total / pageSize) || 1;
      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, total);
      const pageJobs = filtered.slice(startIdx, endIdx);

      document.getElementById('paginationInfo').innerText = total ? `Showing ${startIdx + 1}–${endIdx} of ${total} jobs` : '0 jobs';
      document.getElementById('pageBadge').innerText = `Page ${currentPage} / ${totalPages}`;
      document.getElementById('prevBtn').disabled = currentPage <= 1;
      document.getElementById('nextBtn').disabled = currentPage >= totalPages;
      const jump = document.getElementById('pageJump');
      if (jump) { jump.max = totalPages; jump.placeholder = `1-${totalPages}`; }

      const el = document.getElementById('jobsList');
      if (!pageJobs.length) {
        el.innerHTML = '<div class="text-neutral-500 text-sm py-12 text-center font-medium">No opportunities match the selected criteria.</div>';
        return;
      }
      el.innerHTML = pageJobs.map(j => `
        <div class="p-5 bg-[#161616] hover:bg-[#1C1C1C] border border-neutral-800/80 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 transition group">
          <div class="space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[9px] font-black tracking-widest px-2.5 py-0.5 rounded-full uppercase bg-neutral-800 text-neutral-300 border border-neutral-700">${j.source || 'JOB'}</span>
              <span class="text-[9px] font-black tracking-wider px-2.5 py-0.5 rounded-full uppercase ${formatSalary(j) === 'NOT DISCLOSED' ? 'bg-neutral-800/80 text-neutral-400 border border-neutral-700/60' : 'bg-limepill text-black'}">${formatSalary(j)}</span>
              ${translateWorkMode(j.work_mode) ? `<span class="text-[9px] font-bold tracking-wider px-2 py-0.5 rounded-full uppercase border border-neutral-700 text-neutral-400">${translateWorkMode(j.work_mode)}</span>` : ''}
              ${translateWorkType(j.work_type) ? `<span class="text-[9px] font-medium tracking-wider px-2 py-0.5 rounded-full uppercase bg-neutral-900 text-neutral-400">${translateWorkType(j.work_type)}</span>` : ''}
            </div>
            <h4 class="font-bold text-white text-base md:text-xl tracking-tight group-hover:text-limepill transition">${j.title || 'Untitled'}</h4>
            <div class="text-xs text-neutral-400 flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-x-2">
              <span class="text-neutral-200 font-semibold text-[13px] sm:text-xs">${j.company || 'Unknown Company'}</span>
              <span class="hidden sm:inline text-neutral-600">/</span>
              <span class="text-neutral-400 text-xs">${j.location || 'Surabaya'}</span>
            </div>
          </div>
          <div class="flex items-center gap-2 self-end sm:self-center shrink-0 pt-1 sm:pt-0">
            <button onclick="toggleSaveJob('${j.id}')" title="Save job" class="w-9 h-9 rounded-full border ${savedIds.includes(j.id) ? 'border-limepill bg-limepill text-black' : 'border-neutral-700 bg-neutral-800/80 hover:bg-neutral-700 text-neutral-400 hover:text-white'} flex items-center justify-center transition">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="${savedIds.includes(j.id) ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
              </svg>
            </button>
            <a href="${j.url || '#'}" target="_blank" class="pill-btn bg-white hover:bg-limepill text-black font-bold text-xs px-5 py-2.5 transition shrink-0 flex items-center gap-1.5">
              <span>View Job</span>
              <span>↗</span>
            </a>
          </div>
        </div>
      `).join('');
    }

    function changePage(delta) {
      currentPage += delta;
      renderJobs();
      scrollToFeed();
    }

    function jumpToPage(value) {
      const totalPages = Math.ceil(filteredTotal / pageSize) || 1;
      const n = Math.floor(Number(value));
      if (!Number.isFinite(n) || n < 1) return;
      currentPage = Math.min(n, totalPages);
      renderJobs();
      scrollToFeed();
    }

    function scrollToFeed() {
      const target = document.getElementById('curatedSection');
      if (!target) return;
      const topOffset = target.getBoundingClientRect().top + window.pageYOffset - (window.innerHeight * 0.06);
      window.scrollTo({ top: topOffset, behavior: 'smooth' });
    }

    function chipFontSize(text) {
      const len = (text || '').length;
      if (len <= 10) return '11px';
      if (len <= 14) return '10px';
      if (len <= 18) return '9px';
      return '8px';
    }
    function chipClass(text) {
      return `inline-flex items-center px-3 py-1 rounded-full font-extrabold tracking-tight shadow-sm whitespace-nowrap`;
    }

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toastNotification');
      const text = document.getElementById('toastMsg');
      const dot = document.getElementById('toastDot');
      text.innerText = msg;
      dot.className = isError ? 'w-2 h-2 rounded-full bg-rose-500' : 'w-2 h-2 rounded-full bg-limepill animate-ping';
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 3500);
    }

    function triggerScrape() {
      document.getElementById('modalTokenInput').value = '';
      document.getElementById('modalErrorMsg').classList.add('hidden');
      document.getElementById('tokenModal').classList.remove('hidden');
      document.getElementById('modalTokenInput').focus();
    }

    function closeTokenModal() {
      document.getElementById('tokenModal').classList.add('hidden');
    }

    async function confirmTriggerScrape() {
      const input = document.getElementById('modalTokenInput');
      const token = input.value.trim();
      if (!token) {
        document.getElementById('modalErrorMsg').innerText = 'Token cannot be empty.';
        document.getElementById('modalErrorMsg').classList.remove('hidden');
        return;
      }

      const confirmBtn = document.getElementById('modalConfirmBtn');
      confirmBtn.disabled = true;
      confirmBtn.innerText = 'Verifying...';

      const btn = document.getElementById('triggerBtn');
      const btnMobile = document.getElementById('triggerBtnMobile');
      btn.disabled = true;
      btn.innerHTML = '<span>Scraping...</span>';
      if (btnMobile) {
        btnMobile.disabled = true;
        btnMobile.innerHTML = '<span>Scraping...</span>';
      }
      try {
        const res = await fetch('/api/trigger', {
          method: 'POST',
          headers: { 'X-Trigger-Token': token }
        });
        if (res.status === 401) {
          document.getElementById('modalErrorMsg').innerText = 'Invalid token. Authorization failed.';
          document.getElementById('modalErrorMsg').classList.remove('hidden');
          confirmBtn.disabled = false;
          confirmBtn.innerText = 'Confirm ↗';
          btn.disabled = false;
          btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          if (btnMobile) {
            btnMobile.disabled = false;
            btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          }
          return;
        }
        closeTokenModal();
        showToast('Scraping initiated across all 6 platforms.');
        setTimeout(() => {
          loadStats();
          loadJobs();
          btn.disabled = false;
          btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          if (btnMobile) {
            btnMobile.disabled = false;
            btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
          }
        }, 3000);
      } catch (e) {
        closeTokenModal();
        showToast('Network error triggering scraper.', true);
        btn.disabled = false;
        btn.innerHTML = '<span>Scrape Now</span><span>↗</span>';
        if (btnMobile) {
          btnMobile.disabled = false;
          btnMobile.innerHTML = '<span>Scrape Now</span><span>↗</span>';
        }
      }
    }

    let typewriterTimeout = null;
    function initTypewriter(words) {
      if (typewriterTimeout) clearTimeout(typewriterTimeout);
      if (!Array.isArray(words)) words = [words];
      if (!words.length) return;
      const target = document.getElementById('heroWordMain');
      let wordIdx = 0;
      let idx = 0;
      let isDeleting = false;

      function fitFont(word) {
        // ponytail: avoid forced synchronous reflow loop. Precompute size from length bracket.
        const len = word.length;
        let size = window.innerWidth >= 768 ? 96 : (window.innerWidth >= 640 ? 72 : 56);
        if (len > 14) {
          size = Math.round(size * 0.65);
        } else if (len > 10) {
          size = Math.round(size * 0.8);
        }
        target.style.fontSize = size + 'px';
      }

      function tick() {
        const word = words[wordIdx];
        if (idx === 0 && !isDeleting) fitFont(word);
        if (!isDeleting) {
          idx++;
          const nextText = word.substring(0, idx);
          target.textContent = nextText || '\u00A0';
          target.classList.toggle('hero-highlight', Boolean(nextText));
          if (idx === word.length) {
            typewriterTimeout = setTimeout(() => { isDeleting = true; tick(); }, 2000);
            return;
          }
          typewriterTimeout = setTimeout(tick, 140);
        } else {
          idx--;
          const nextText = word.substring(0, idx);
          target.textContent = nextText || '\u00A0';
          target.classList.toggle('hero-highlight', Boolean(nextText));
          if (idx === 0) {
            isDeleting = false;
            wordIdx = (wordIdx + 1) % words.length;
            typewriterTimeout = setTimeout(tick, 500);
            return;
          }
          typewriterTimeout = setTimeout(tick, 70);
        }
      }
      tick();
    }

    const logEl = document.getElementById('logTerminal');
    const logLevelClass = (line) => {
      if (line.includes('ERROR') || line.includes('Traceback')) return 'text-[#FF6B6B]';
      if (line.includes('WARNING')) return 'text-[#FFBD2E]';
      if (line.includes('INFO')) return 'text-neutral-400';
      return 'text-neutral-500';
    };
    let logLines = [];
    let logSig = '';
    const logRowHtml = (l) => {
      const safe = l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return `<div class="truncate ${logLevelClass(l)}">${safe}</div>`;
    };
    function renderLogs() {
      if (!logLines.length) return;
      logEl.innerHTML = logLines.map(logRowHtml).join('');
      let guard = logLines.length;
      while (logEl.scrollHeight > logEl.clientHeight && logEl.firstChild && guard--) {
        logEl.removeChild(logEl.firstChild);
      }
    }
    async function loadLogs() {
      try {
        const res = await fetch('/api/logs?lines=80');
        const data = await res.json();
        logLines = data.lines || [];
        const sig = logLines.join('\\n');
        if (sig === logSig) return;
        logSig = sig;
        renderLogs();
      } catch (e) { }
    }
    if (window.ResizeObserver) new ResizeObserver(renderLogs).observe(logEl);

    loadStats();
    loadJobs();
    updateBookmarkUI();
    // ponytail: defer live log stream so initial mobile render finishes before recurring polling begins.
    setTimeout(() => { loadLogs(); setInterval(loadLogs, 4000); }, 1500);