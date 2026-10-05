document.addEventListener('DOMContentLoaded', () => {
    // 状态管理
    const state = {
        currentSiteId: null,
        sites: [],
        currentStatusFilter: 'all',
        keyword: '',
        urls: [],
        selectedUrls: new Set(),
        crawlerTimer: null
    };

    // DOM 元素引用
    const currentSiteSelect = document.getElementById('currentSiteSelect');
    const btnManageSites = document.getElementById('btnManageSites');
    const btnUseSiteHome = document.getElementById('btnUseSiteHome');
    const crawlStartUrl = document.getElementById('crawlStartUrl');
    const crawlMaxDepth = document.getElementById('crawlMaxDepth');
    const crawlMaxPages = document.getElementById('crawlMaxPages');
    const btnToggleCrawl = document.getElementById('btnToggleCrawl') || document.getElementById('btnStartCrawl');
    const crawlBtnIcon = document.getElementById('crawlBtnIcon');
    const crawlBtnText = document.getElementById('crawlBtnText');
    const crawlerBadge = document.getElementById('crawlerBadge');
    const crawlerStateText = document.getElementById('crawlerStateText');
    const crawlProgressBox = document.getElementById('crawlProgressBox');
    const crawlProgressBar = document.getElementById('crawlProgressBar');
    const crawlStatusMsg = document.getElementById('crawlStatusMsg');
    const crawlCounts = document.getElementById('crawlCounts');

    const urlsTableBody = document.getElementById('urlsTableBody');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const selectedCountEl = document.getElementById('selectedCount');
    const btnSelectOnlyUnsubmitted = document.getElementById('btnSelectOnlyUnsubmitted');
    const btnSelectAll = document.getElementById('btnSelectAll');
    const btnDeselectAll = document.getElementById('btnDeselectAll');
    const btnInvertSelect = document.getElementById('btnInvertSelect');
    const btnBatchPush = document.getElementById('btnBatchPush');
    const btnManualAdd = document.getElementById('btnManualAdd');
    const btnExport = document.getElementById('btnExport');
    const btnClearUrls = document.getElementById('btnClearUrls');
    const searchInput = document.getElementById('searchInput');

    // 统计数字元素
    const statQuota = document.getElementById('statQuota');
    const statTotal = document.getElementById('statTotal');
    const statUnsubmitted = document.getElementById('statUnsubmitted');
    const statSuccess = document.getElementById('statSuccess');
    const statFailed = document.getElementById('statFailed');

    const tabCountAll = document.getElementById('tabCountAll');
    const tabCountUnsubmitted = document.getElementById('tabCountUnsubmitted');
    const tabCountSuccess = document.getElementById('tabCountSuccess');
    const tabCountFailed = document.getElementById('tabCountFailed');
    const tabCountIgnored = document.getElementById('tabCountIgnored');

    // 弹窗元素
    const siteModal = document.getElementById('siteModal');
    const btnCloseSiteModal = document.getElementById('btnCloseSiteModal');
    const btnSaveSite = document.getElementById('btnSaveSite');
    const btnResetSiteForm = document.getElementById('btnResetSiteForm');
    const editSiteId = document.getElementById('editSiteId');
    const siteName = document.getElementById('siteName');
    const siteDomain = document.getElementById('siteDomain');
    const siteToken = document.getElementById('siteToken');
    const sitesListBox = document.getElementById('sitesListBox');

    const manualModal = document.getElementById('manualModal');
    const btnCloseManualModal = document.getElementById('btnCloseManualModal');
    const btnCancelManual = document.getElementById('btnCancelManual');
    const btnSubmitManual = document.getElementById('btnSubmitManual');
    const manualUrlsText = document.getElementById('manualUrlsText');

    const pushResultModal = document.getElementById('pushResultModal');
    const btnClosePushResultModal = document.getElementById('btnClosePushResultModal');
    const btnConfirmPushResult = document.getElementById('btnConfirmPushResult');
    const resultSummaryBox = document.getElementById('resultSummaryBox');

    // ================== Toast 提示 ==================
    function showToast(msg, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = 'toast';
        
        let icon = '<i class="fa-solid fa-circle-info"></i>';
        if (type === 'success') icon = '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i>';
        if (type === 'error') icon = '<i class="fa-solid fa-circle-exclamation" style="color:#ef4444;"></i>';
        
        toast.innerHTML = `${icon} <span>${msg}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // ================== 站点管理 ==================
    async function loadSites() {
        try {
            const res = await fetch('/api/sites');
            const data = await res.json();
            if (data.code === 0) {
                state.sites = data.data;
                renderSiteOptions();
                if (state.sites.length > 0 && !state.currentSiteId) {
                    selectSite(state.sites[0].id);
                } else if (state.currentSiteId) {
                    selectSite(state.currentSiteId);
                }
            }
        } catch (e) {
            showToast('获取站点列表失败', 'error');
        }
    }

    function renderSiteOptions() {
        currentSiteSelect.innerHTML = state.sites.length === 0
            ? '<option value="">-- 暂无配置站点，请点击右侧添加 --</option>'
            : state.sites.map(s => `<option value="${s.id}" ${s.id == state.currentSiteId ? 'selected' : ''}>${s.name} (${s.site})</option>`).join('');
    }

    function selectSite(siteId) {
        state.currentSiteId = siteId;
        currentSiteSelect.value = siteId;
        const site = state.sites.find(s => s.id == siteId);
        if (site && !crawlStartUrl.value) {
            crawlStartUrl.value = 'https://' + site.site;
        }
        state.selectedUrls.clear();
        updateSelectedCounter();
        loadUrls();
        loadSiteStats();
    }

    async function loadSiteStats() {
        if (!state.currentSiteId) return;
        try {
            const res = await fetch(`/api/sites/${state.currentSiteId}/stats`);
            const data = await res.json();
            if (data.code === 0) {
                const s = data.data;
                statQuota.textContent = s.remain_quota >= 0 ? s.remain_quota.toLocaleString() : '未测算';
                statTotal.textContent = (s.total || 0).toLocaleString();
                statUnsubmitted.textContent = (s.unsubmitted || 0).toLocaleString();
                statSuccess.textContent = (s.success || 0).toLocaleString();
                statFailed.textContent = (s.failed || 0).toLocaleString();

                tabCountAll.textContent = s.total || 0;
                tabCountUnsubmitted.textContent = s.unsubmitted || 0;
                tabCountSuccess.textContent = s.success || 0;
                tabCountFailed.textContent = s.failed || 0;
                tabCountIgnored.textContent = s.ignored || 0;
            }
        } catch (e) {
            console.error(e);
        }
    }

    currentSiteSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            selectSite(e.target.value);
        }
    });

    btnUseSiteHome.addEventListener('click', () => {
        const site = state.sites.find(s => s.id == state.currentSiteId);
        if (site) {
            crawlStartUrl.value = 'https://' + site.site;
            showToast('已填入站点首页', 'success');
        } else {
            showToast('请先选择或配置一个站点', 'error');
        }
    });

    // 站点管理弹窗
    btnManageSites.addEventListener('click', () => {
        renderSiteListInModal();
        siteModal.classList.add('active');
    });

    btnCloseSiteModal.addEventListener('click', () => siteModal.classList.remove('active'));

    function renderSiteListInModal() {
        if (state.sites.length === 0) {
            sitesListBox.innerHTML = '<p class="text-muted" style="font-size:13px;">暂无配置站点，请在上方填写添加</p>';
            return;
        }
        sitesListBox.innerHTML = state.sites.map(s => `
            <div class="site-list-item">
                <div class="site-item-info">
                    <strong>${s.name}</strong>
                    <div class="site-item-meta">域名: <code>${s.site}</code> | Token: <code>${s.token.substring(0, 4)}****${s.token.substring(s.token.length - 4)}</code></div>
                </div>
                <div class="site-item-ops">
                    <button class="btn btn-outline btn-sm btn-edit-site" data-id="${s.id}">编辑</button>
                    <button class="btn btn-ghost-danger btn-sm btn-del-site" data-id="${s.id}">删除</button>
                </div>
            </div>
        `).join('');

        // 绑定编辑和删除
        document.querySelectorAll('.btn-edit-site').forEach(btn => {
            btn.onclick = () => {
                const id = btn.getAttribute('data-id');
                const s = state.sites.find(item => item.id == id);
                if (s) {
                    editSiteId.value = s.id;
                    siteName.value = s.name;
                    siteDomain.value = s.site;
                    siteToken.value = s.token;
                    btnResetSiteForm.style.display = 'inline-block';
                    siteName.focus();
                }
            };
        });

        document.querySelectorAll('.btn-del-site').forEach(btn => {
            btn.onclick = async () => {
                const id = btn.getAttribute('data-id');
                if (confirm('确认删除该站点及其所有已抓取链接记录吗？')) {
                    const res = await fetch(`/api/sites/${id}`, { method: 'DELETE' });
                    const resData = await res.json();
                    if (resData.code === 0) {
                        showToast('站点已删除', 'success');
                        await loadSites();
                        renderSiteListInModal();
                    }
                }
            };
        });
    }

    btnResetSiteForm.addEventListener('click', () => {
        editSiteId.value = '';
        siteName.value = '';
        siteDomain.value = '';
        siteToken.value = '';
        btnResetSiteForm.style.display = 'none';
    });

    btnSaveSite.addEventListener('click', async () => {
        const payload = {
            id: editSiteId.value ? parseInt(editSiteId.value) : null,
            name: siteName.value.trim(),
            site: siteDomain.value.trim(),
            token: siteToken.value.trim()
        };
        if (!payload.name || !payload.site || !payload.token) {
            showToast('请将站点名称、域名和Token填写完整', 'error');
            return;
        }

        try {
            const res = await fetch('/api/sites', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.code === 0) {
                showToast('保存站点成功', 'success');
                btnResetSiteForm.click();
                await loadSites();
                renderSiteListInModal();
            } else {
                showToast(data.message || '保存失败', 'error');
            }
        } catch (e) {
            showToast('请求接口异常', 'error');
        }
    });

    // ================== 爬虫引擎控制 ==================
    let isCrawling = false;

    function setCrawlButtonState(running, stopping = false) {
        isCrawling = running;
        const btn = document.getElementById('btnToggleCrawl') || document.getElementById('btnStartCrawl');
        const icon = document.getElementById('crawlBtnIcon');
        const text = document.getElementById('crawlBtnText');
        const oldStop = document.getElementById('btnStopCrawl');

        if (stopping) {
            if (btn) {
                btn.className = 'btn btn-danger';
                btn.disabled = true;
                if (text) text.textContent = '正在停止遍历...';
                else btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在停止遍历...';
            }
            if (icon) icon.className = 'fa-solid fa-spinner fa-spin';
        } else if (running) {
            if (btn) {
                btn.className = 'btn btn-danger';
                btn.disabled = false;
                if (text) text.textContent = '停止遍历';
                else btn.innerHTML = '<i class="fa-solid fa-stop"></i> 停止遍历';
            }
            if (icon) icon.className = 'fa-solid fa-stop';
            if (oldStop) oldStop.style.display = 'inline-flex';
        } else {
            if (btn) {
                btn.className = 'btn btn-primary';
                btn.disabled = false;
                if (text) text.textContent = '开始智能遍历';
                else btn.innerHTML = '<i class="fa-solid fa-play"></i> 开始智能遍历';
            }
            if (icon) icon.className = 'fa-solid fa-play';
            if (oldStop) oldStop.style.display = 'none';
        }
    }

    window.handleCrawlToggle = async function() {
        if (isCrawling) {
            // 当前处于遍历状态，点击触发“停止遍历”
            setCrawlButtonState(true, true);
            try {
                const res = await fetch('/api/crawler/stop', { method: 'POST' });
                const data = await res.json();
                showToast(data.message || '已发出停止遍历请求', 'info');
            } catch (e) {
                console.error(e);
                setCrawlButtonState(true);
            }
        } else {
            // 确保获取到当前选中的站点 ID
            const targetSiteId = state.currentSiteId || (currentSiteSelect ? currentSiteSelect.value : null);
            if (!targetSiteId) {
                showToast('请先在右上角选择或添加目标站点', 'error');
                return;
            }
            state.currentSiteId = targetSiteId;

            const startUrl = crawlStartUrl.value.trim();
            if (!startUrl) {
                showToast('请输入起始遍历网址', 'error');
                crawlStartUrl.focus();
                return;
            }

            const payload = {
                site_id: parseInt(targetSiteId),
                start_url: startUrl,
                max_depth: parseInt(crawlMaxDepth.value),
                max_pages: parseInt(crawlMaxPages.value)
            };

            // 立即给按钮一个反馈动画
            btnToggleCrawl.disabled = true;
            crawlBtnText.textContent = '正在启动...';

            try {
                const res = await fetch('/api/crawler/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.code === 0) {
                    showToast('智能遍历已启动', 'success');
                    startPollingCrawler();
                } else {
                    setCrawlButtonState(false);
                    showToast(data.message || '启动失败', 'error');
                }
            } catch (e) {
                setCrawlButtonState(false);
                showToast('网络请求异常，请检查后台是否运行', 'error');
            }
        }
    };

    const allCrawlButtons = [
        document.getElementById('btnToggleCrawl'),
        document.getElementById('btnStartCrawl')
    ].filter(Boolean);

    allCrawlButtons.forEach(b => {
        b.onclick = window.handleCrawlToggle;
    });

    const oldStopBtn = document.getElementById('btnStopCrawl');
    if (oldStopBtn) {
        oldStopBtn.onclick = async () => {
            setCrawlButtonState(true, true);
            try {
                await fetch('/api/crawler/stop', { method: 'POST' });
            } catch (e) {
                console.error(e);
            }
        };
    }

    function startPollingCrawler() {
        if (state.crawlerTimer) clearInterval(state.crawlerTimer);
        setCrawlButtonState(true);
        crawlProgressBox.style.display = 'block';
        crawlerBadge.className = 'crawler-status-badge running';
        crawlerStateText.textContent = '正在遍历中...';

        state.crawlerTimer = setInterval(async () => {
            try {
                const res = await fetch('/api/crawler/status');
                const data = await res.json();
                if (data.code === 0) {
                    const st = data.data;
                    crawlStatusMsg.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${st.message || '遍历中...'}`;
                    crawlCounts.textContent = `已爬取: ${st.visited_count} 页 | 已发现: ${st.found_count} 条有效链接`;

                    if (st.state !== 'running' && st.state !== 'stopping') {
                        // 结束
                        clearInterval(state.crawlerTimer);
                        state.crawlerTimer = null;
                        setCrawlButtonState(false);
                        crawlerBadge.className = 'crawler-status-badge';
                        crawlerStateText.textContent = st.state === 'completed' ? '遍历完成' : '已停止';
                        crawlStatusMsg.innerHTML = `<i class="fa-solid fa-circle-check text-success"></i> ${st.message}`;
                        showToast('遍历结束，正在刷新列表数据...', 'success');
                        loadUrls();
                        loadSiteStats();
                    } else if (st.state === 'stopping') {
                        setCrawlButtonState(true, true);
                    } else {
                        // 运行中定期刷新统计
                        loadSiteStats();
                    }
                }
            } catch (e) {
                console.error(e);
            }
        }, 1000);
    }

    // ================== 链接列表与表格 ==================
    async function loadUrls() {
        if (!state.currentSiteId) {
            urlsTableBody.innerHTML = `
                <tr><td colspan="8" class="text-center empty-tip"><i class="fa-solid fa-inbox"></i><p>请先在上方配置或选择站点</p></td></tr>
            `;
            return;
        }

        const url = `/api/urls?site_id=${state.currentSiteId}&status=${state.currentStatusFilter}&keyword=${encodeURIComponent(state.keyword)}&limit=2000`;
        try {
            const res = await fetch(url);
            const data = await res.json();
            if (data.code === 0) {
                state.urls = data.data;
                renderUrlsTable();
            }
        } catch (e) {
            showToast('获取链接列表失败', 'error');
        }
    }

    function renderUrlsTable() {
        if (state.urls.length === 0) {
            urlsTableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center empty-tip">
                        <i class="fa-solid fa-inbox"></i>
                        <p>当前筛选条件下暂无链接记录，请点击上方【开始智能遍历】抓取本站页面，或点击【手动粘贴链接】</p>
                    </td>
                </tr>
            `;
            selectAllCheckbox.checked = false;
            return;
        }

        urlsTableBody.innerHTML = state.urls.map((row, index) => {
            const isChecked = state.selectedUrls.has(row.url);
            return `
                <tr class="${isChecked ? 'selected-row' : ''}">
                    <td><input type="checkbox" class="row-checkbox" data-url="${escapeHtml(row.url)}" ${isChecked ? 'checked' : ''}></td>
                    <td>${index + 1}</td>
                    <td>
                        <div class="url-cell">
                            <span class="url-title" title="${escapeHtml(row.title || '无标题')}">${escapeHtml(row.title || '未获取页面标题')}</span>
                            <a href="${escapeHtml(row.url)}" target="_blank" class="url-link" title="${escapeHtml(row.url)}">
                                ${escapeHtml(row.url)} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:10px;"></i>
                            </a>
                        </div>
                    </td>
                    <td><span class="badge" style="background:#f1f5f9;color:#475569;">L${row.depth}</span></td>
                    <td>${getStatusBadge(row.status)}</td>
                    <td style="text-align:center;"><strong>${row.push_count}</strong> 次</td>
                    <td>
                        <span style="font-size:12px; color: ${row.status === 'failed' ? 'var(--danger)' : 'var(--text-secondary)'};" title="${escapeHtml(row.last_push_result || '')}">
                            ${escapeHtml(row.last_push_result || (row.status === 'unsubmitted' ? '尚未提交' : '--'))}
                        </span>
                    </td>
                    <td style="font-size:12px; color:var(--text-muted);">${row.discovered_at || '--'}</td>
                </tr>
            `;
        }).join('');

        // 绑定行勾选事件
        document.querySelectorAll('.row-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const url = e.target.getAttribute('data-url');
                if (e.target.checked) {
                    state.selectedUrls.add(url);
                    e.target.closest('tr').classList.add('selected-row');
                } else {
                    state.selectedUrls.delete(url);
                    e.target.closest('tr').classList.remove('selected-row');
                }
                updateSelectedCounter();
            });
        });

        updateSelectedCounter();
    }

    function getStatusBadge(status) {
        if (status === 'success') {
            return '<span class="badge badge-success"><i class="fa-solid fa-check"></i> 推送成功</span>';
        } else if (status === 'failed') {
            return '<span class="badge badge-failed"><i class="fa-solid fa-xmark"></i> 提交失败</span>';
        } else if (status === 'ignored') {
            return '<span class="badge badge-ignored"><i class="fa-solid fa-ban"></i> 已忽略</span>';
        } else {
            return '<span class="badge badge-unsubmitted"><i class="fa-solid fa-clock"></i> 待推送</span>';
        }
    }

    function updateSelectedCounter() {
        selectedCountEl.textContent = state.selectedUrls.size;
        btnBatchPush.innerHTML = `<i class="fa-solid fa-paper-plane"></i> 立即推送勾选链接 (${state.selectedUrls.size})`;
        
        // 联动全选框
        if (state.urls.length > 0 && state.urls.every(r => state.selectedUrls.has(r.url))) {
            selectAllCheckbox.checked = true;
        } else {
            selectAllCheckbox.checked = false;
        }
    }

    // 勾选操作工具
    selectAllCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            state.urls.forEach(r => state.selectedUrls.add(r.url));
        } else {
            state.selectedUrls.clear();
        }
        renderUrlsTable();
    });

    btnSelectAll.addEventListener('click', () => {
        state.urls.forEach(r => state.selectedUrls.add(r.url));
        renderUrlsTable();
    });

    btnDeselectAll.addEventListener('click', () => {
        state.selectedUrls.clear();
        renderUrlsTable();
    });

    btnInvertSelect.addEventListener('click', () => {
        state.urls.forEach(r => {
            if (state.selectedUrls.has(r.url)) {
                state.selectedUrls.delete(r.url);
            } else {
                state.selectedUrls.add(r.url);
            }
        });
        renderUrlsTable();
    });

    // 关键核心功能：仅勾选待推送链接（防重复提交）
    btnSelectOnlyUnsubmitted.addEventListener('click', () => {
        state.selectedUrls.clear();
        let count = 0;
        state.urls.forEach(r => {
            if (r.status === 'unsubmitted') {
                state.selectedUrls.add(r.url);
                count++;
            }
        });
        renderUrlsTable();
        showToast(`已智能勾选 ${count} 条待推送链接，已自动过滤已提交成功的旧链接！`, 'success');
    });

    // Tab 状态筛选
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.currentStatusFilter = tab.getAttribute('data-status');
            loadUrls();
        });
    });

    // 搜索过滤
    let searchDebounceTimer = null;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            state.keyword = e.target.value.trim();
            loadUrls();
        }, 300);
    });

    // 清空当前站点记录
    btnClearUrls.addEventListener('click', async () => {
        if (!state.currentSiteId) return;
        if (confirm('确认清空当前站点的所有抓取记录与历史提交记录吗？该操作不可撤销。')) {
            await fetch('/api/urls/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ site_id: state.currentSiteId })
            });
            showToast('已清空当前站点链接记录', 'success');
            state.selectedUrls.clear();
            loadUrls();
            loadSiteStats();
        }
    });

    // ================== 手动粘贴添加链接 ==================
    btnManualAdd.addEventListener('click', () => {
        if (!state.currentSiteId) {
            showToast('请先选择目标站点', 'error');
            return;
        }
        manualUrlsText.value = '';
        manualModal.classList.add('active');
    });

    btnCloseManualModal.addEventListener('click', () => manualModal.classList.remove('active'));
    btnCancelManual.addEventListener('click', () => manualModal.classList.remove('active'));

    btnSubmitManual.addEventListener('click', async () => {
        const text = manualUrlsText.value.trim();
        if (!text) {
            showToast('请输入至少一条网址', 'error');
            return;
        }
        try {
            const res = await fetch('/api/urls/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ site_id: state.currentSiteId, urls: text })
            });
            const data = await res.json();
            if (data.code === 0) {
                showToast(data.message, 'success');
                manualModal.classList.remove('active');
                loadUrls();
                loadSiteStats();
            } else {
                showToast(data.message || '录入失败', 'error');
            }
        } catch (e) {
            showToast('请求异常', 'error');
        }
    });

    // ================== 导出链接 ==================
    btnExport.addEventListener('click', () => {
        if (!state.currentSiteId) {
            showToast('请先选择站点', 'error');
            return;
        }
        const format = confirm('点击【确定】导出为 CSV 表格（含标题与状态）\n点击【取消】导出为纯文本 TXT（一行一个 URL）') ? 'csv' : 'txt';
        window.open(`/api/export?site_id=${state.currentSiteId}&status=${state.currentStatusFilter}&type=${format}`);
    });

    // ================== 批量推送到百度 API ==================
    btnBatchPush.addEventListener('click', async () => {
        if (!state.currentSiteId) {
            showToast('请先选择目标站点', 'error');
            return;
        }

        const urlsToPush = Array.from(state.selectedUrls);
        if (urlsToPush.length === 0) {
            showToast('请先勾选需要推送的链接！可点击“仅勾选待推送链接”快捷选择', 'error');
            return;
        }

        const site = state.sites.find(s => s.id == state.currentSiteId);
        if (!confirm(`确认向百度搜索资源平台推送勾选的 ${urlsToPush.length} 条链接吗？\n目标站点：${site.site}`)) {
            return;
        }

        btnBatchPush.disabled = true;
        btnBatchPush.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在向百度 API 提交中...';

        try {
            const res = await fetch('/api/baidu/push', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_id: state.currentSiteId,
                    urls: urlsToPush
                })
            });
            const result = await res.json();

            // 渲染结果弹窗
            renderPushResultModal(result);
            pushResultModal.classList.add('active');

            // 重新刷新数据
            state.selectedUrls.clear();
            loadUrls();
            loadSiteStats();
        } catch (e) {
            showToast('请求接口异常或网络超时', 'error');
        } finally {
            btnBatchPush.disabled = false;
            updateSelectedCounter();
        }
    });

    function renderPushResultModal(res) {
        if (!res.data) {
            resultSummaryBox.innerHTML = `<p class="text-danger">${res.message || '推送失败'}</p>`;
            return;
        }
        const d = res.data;
        resultSummaryBox.innerHTML = `
            <div class="push-summary-metric">
                <div class="metric-box">
                    <div class="num text-primary">${d.total_submitted}</div>
                    <div class="desc">本次提交总数</div>
                </div>
                <div class="metric-box">
                    <div class="num text-success">${d.total_success}</div>
                    <div class="desc">百度确认成功数 (success)</div>
                </div>
                <div class="metric-box">
                    <div class="num highlight">${d.remain >= 0 ? d.remain.toLocaleString() : '--'}</div>
                    <div class="desc">当日剩余可用配额 (remain)</div>
                </div>
            </div>

            <h4 class="sub-heading" style="margin-top:16px;">分批次推送详情 (共 ${d.batches.length} 个批次)</h4>
            <div class="batch-logs-list">
                ${d.batches.map(b => `
                    <div class="batch-log-item ${b.status === 'success' ? 'batch-log-success' : 'batch-log-failed'}">
                        <strong>批次 #${b.batch_index} (${b.count}条)：</strong>
                        ${b.status === 'success' 
                            ? `成功 ${b.success_count} 条，余量 ${b.remain} 条 ${b.not_same_site_count ? `[非本站排除: ${b.not_same_site_count}]` : ''}` 
                            : `失败 [${b.error_code || '异常'}]: ${b.error_message || '未知原因'}`
                        }
                    </div>
                `).join('')}
            </div>
        `;
    }

    btnClosePushResultModal.addEventListener('click', () => pushResultModal.classList.remove('active'));
    btnConfirmPushResult.addEventListener('click', () => pushResultModal.classList.remove('active'));

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // 页面加载时检测爬虫是否正在运行，若在运行则自动恢复“停止遍历”状态和轮询
    async function checkInitialCrawlerStatus() {
        try {
            const res = await fetch('/api/crawler/status');
            const data = await res.json();
            if (data.code === 0 && (data.data.state === 'running' || data.data.state === 'stopping')) {
                startPollingCrawler();
            }
        } catch (e) {
            console.error(e);
        }
    }

    // 初始化
    loadSites();
    checkInitialCrawlerStatus();
});
