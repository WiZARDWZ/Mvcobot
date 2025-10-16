const DashboardApp = (() => {
    const state = {
        currentPage: 'dashboard',
        isDarkMode: false,
        isMobileMenuOpen: false,
        userPendingDeletion: null,
        commandHistory: [
            { id: 1, text: 'User executed command: /disable', timestamp: new Date() },
            { id: 2, text: 'User executed command: /enable', timestamp: new Date(Date.now() - 3600000) },
            { id: 3, text: 'User added to blacklist: 123456789', timestamp: new Date(Date.now() - 7200000) },
            { id: 4, text: 'Working hours updated: 08:00 - 18:00', timestamp: new Date(Date.now() - 10800000) }
        ],
        blacklist: [
            { id: 1, userId: '123456789', addedDate: '2024-01-15' },
            { id: 2, userId: '987654321', addedDate: '2024-01-14' },
            { id: 3, userId: '456789123', addedDate: '2024-01-13' }
        ]
    };

    const commands = [
        {
            id: 1,
            title: '1. خاموش کردن ربات',
            text: '⏹️ غیرفعال کردن فعالیت ربات.',
            example: '/disable',
            command: 'disable',
            category: 'danger'
        },
        {
            id: 2,
            title: '2. روشن کردن ربات',
            text: '▶️ فعال کردن مجدد فعالیت ربات.',
            example: '/enable',
            command: 'enable',
            category: 'success'
        },
        {
            id: 3,
            title: '3. تغییر ساعت کاری ربات',
            text: '⏲️ تعریف ساعت فعالیت ربات برای روزهای عادی.',
            example: '/set_hours start=[HH:MM] end=[HH:MM]',
            example2: 'مثال: /set_hours start=08:00 end=18:00',
            command: 'set-hours',
            category: 'primary'
        },
        {
            id: 4,
            title: '4. تغییر ساعت کاری پنج‌شنبه',
            text: '📅 تعریف ساعت فعالیت ربات برای روز پنج‌شنبه.',
            example: '/set_thursday start=[HH:MM] end=[HH:MM]',
            example2: 'مثال: /set_thursday start=08:00 end=14:00',
            command: 'set-thursday',
            category: 'primary'
        },
        {
            id: 5,
            title: '5. غیرفعال کردن فعالیت ربات در جمعه‌ها',
            text: '🚫 تعطیل کردن فعالیت ربات در روز جمعه.',
            example: '/disable_friday',
            command: 'disable-friday',
            category: 'danger'
        },
        {
            id: 6,
            title: '6. فعال کردن مجدد فعالیت ربات در جمعه‌ها',
            text: '✅ اجازه فعالیت مجدد ربات در روز جمعه.',
            example: '/enable_friday',
            command: 'enable-friday',
            category: 'success'
        },
        {
            id: 7,
            title: '7. تنظیم زمان استراحت (ناهار)',
            text: '🍽 تعیین بازه زمانی برای استراحت ناهار که در این مدت ربات غیرفعال خواهد بود.',
            example: '/set_lunch_break start=[HH:MM] end=[HH:MM]',
            example2: 'مثال: /set_lunch_break start=12:00 end=13:00',
            command: 'set-lunch',
            category: 'warning'
        },
        {
            id: 8,
            title: '8. تغییر محدودیت استعلام در 24 ساعت',
            text: '🔢 تغییر تعداد دفعاتی که هر کاربر می‌تواند در 24 ساعت استعلام بگیرد.',
            example: '/set_query_limit limit=[عدد]',
            example2: 'مثال: /set_query_limit limit=50',
            command: 'set-query-limit',
            category: 'info'
        },
        {
            id: 9,
            title: '9. تغییر متن اطلاعات تحویل کالا (قبل از ساعت)',
            text: '📦 تنظیم متن نمایش داده‌شده برای اطلاعات تحویل کالا قبل از ساعت تعیین‌شده.',
            example: '/set_delivery_info_before [متن]',
            example2: 'مثال: /set_delivery_info_before تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار',
            command: 'set-delivery-before',
            category: 'primary'
        },
        {
            id: 10,
            title: '10. تغییر متن اطلاعات تحویل کالا (بعد از ساعت)',
            text: '📦 تنظیم متن نمایش داده‌شده برای اطلاعات تحویل کالا بعد از ساعت تعیین‌شده.',
            example: '/set_delivery_info_after [متن]',
            example2: 'مثال: /set_delivery_info_after ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است.',
            command: 'set-delivery-after',
            category: 'primary'
        },
        {
            id: 11,
            title: '11. تغییر ساعت تغییر متن اطلاعات تحویل کالا',
            text: '⏰ تنظیم ساعتی که بعد از آن، متن تحویل کالا تغییر می‌کند.',
            example: '/set_changeover_hour time=[HH:MM]',
            example2: 'مثال: /set_changeover_hour time=15:30',
            command: 'set-changeover',
            category: 'warning'
        },
        {
            id: 12,
            title: '12. نحوه یافتن User ID کاربر',
            text: 'برای دریافت یوزر آیدی (کد کاربر):',
            info: '1️⃣ یکی از پیام‌های ارسالی توسط کاربر موردنظر را به ربات @userinfobot فوروارد کنید.<br>2️⃣ ربات، کد کاربر موردنظر را نمایش می‌دهد.',
            command: 'user-id-info',
            category: 'secondary'
        },
        {
            id: 13,
            title: '13. خروجی گرفتن از میزان تقاضا محصولات',
            text: 'زمان تقریبی ارسال خروجی به ازای هر ماه حدود 15 دقیقه است',
            example: '/export [تاریخ] to [تاریخ]',
            example2: 'مثال: /export 2024/09/30 to 2025/09/01',
            command: 'export',
            category: 'primary'
        },
        {
            id: 14,
            title: '14. رفرش کردن اطلاعات کش روبات',
            text: 'قیمت و موجودی',
            example: '/refresh_cache',
            command: 'refresh-cache',
            category: 'success'
        },
        {
            id: 15,
            title: '15. فعال سازی پاسخ دهی به کد های ارسالی',
            text: 'در پیام های شخصی',
            example: '/dm_on',
            example2: '/dm_off',
            command: 'dm-toggle',
            category: 'info'
        }
    ];

    const dashboardStats = [
        { value: '2500+', label: 'Users', change: '1%' },
        { value: '180+', label: 'Commands', change: '2%' },
        { value: '100%', label: 'Tasks', change: '2%' }
    ];

    const barChartValues = [60, 50, 70, 80, 65, 68, 85];
    const barChartLabels = ['Jan.', 'Feb', 'Mar', 'Apr', 'Mai', 'Jun.', 'Sep'];

    const elements = {};

    const init = () => {
        cacheElements();
        bindStaticEvents();
        setActiveNavigation(state.currentPage);
        updateSearchVisibility();
        loadPageContent(state.currentPage);
    };

    const cacheElements = () => {
        elements.navItems = document.querySelectorAll('.nav-item');
        elements.darkModeToggle = document.getElementById('dark-mode-toggle');
        elements.themeText = document.getElementById('theme-text');
        elements.mobileMenuButton = document.querySelector('.mobile-menu-button');
        elements.mobileMenuOverlay = document.querySelector('.mobile-menu-overlay');
        elements.mobileMenu = document.getElementById('mobile-menu');
        elements.mobileMenuClose = document.querySelector('.mobile-menu-close');
        elements.searchInput = document.getElementById('search-input');
        elements.deleteModal = document.getElementById('delete-modal');
        elements.cancelDeleteBtn = document.getElementById('cancel-delete');
        elements.confirmDeleteBtn = document.getElementById('confirm-delete');
        elements.contentArea = document.querySelector('.content-area');
    };

    const bindStaticEvents = () => {
        elements.navItems.forEach(item => {
            item.addEventListener('click', () => navigateToPage(item.dataset.page));
        });

        elements.darkModeToggle.addEventListener('click', toggleTheme);
        elements.mobileMenuButton.addEventListener('click', () => toggleMobileMenu());
        elements.mobileMenuClose.addEventListener('click', () => toggleMobileMenu(false));
        elements.mobileMenuOverlay.addEventListener('click', () => toggleMobileMenu(false));
        elements.searchInput.addEventListener('input', handleSearch);
        elements.cancelDeleteBtn.addEventListener('click', closeDeleteModal);
        elements.confirmDeleteBtn.addEventListener('click', confirmDeleteUser);
        window.addEventListener('resize', handleResize);
        window.addEventListener('click', handleWindowClick);
    };

    const navigateToPage = (pageName) => {
        if (!pageName || state.currentPage === pageName) {
            return;
        }

        state.currentPage = pageName;
        setActiveNavigation(pageName);
        updateSearchVisibility();

        if (state.isMobileMenuOpen && window.innerWidth <= 768) {
            toggleMobileMenu(false);
        }

        loadPageContent(pageName);
    };

    const setActiveNavigation = (pageName) => {
        elements.navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });
    };

    const updateSearchVisibility = () => {
        if (!elements.searchInput) {
            return;
        }

        if (state.currentPage === 'commands') {
            document.body.classList.add('commands-page');
        } else {
            document.body.classList.remove('commands-page');
            elements.searchInput.value = '';
        }
    };

    const loadPageContent = (pageName) => {
        showLoading();

        setTimeout(() => {
            updatePageContent(pageName);
        }, 300);
    };

    const showLoading = () => {
        elements.contentArea.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                <div>Loading...</div>
            </div>
        `;
    };

    const updatePageContent = (pageName) => {
        switch (pageName) {
            case 'dashboard':
                elements.contentArea.innerHTML = renderDashboard();
                break;
            case 'commands':
                elements.contentArea.innerHTML = renderCommandsPage();
                break;
            case 'blacklist':
                elements.contentArea.innerHTML = renderBlacklistPage();
                break;
            case 'logs':
                elements.contentArea.innerHTML = renderLogsPage();
                break;
            default:
                elements.contentArea.innerHTML = '';
        }

        elements.contentArea.classList.add('fade-in');
        setTimeout(() => elements.contentArea.classList.remove('fade-in'), 500);

        enhanceDynamicContent(pageName);
    };

    const renderDashboard = () => {
        return `
            <div class="stats-grid">
                ${dashboardStats.map(renderStatCard).join('')}
            </div>
            <div class="charts-container">
                ${renderStatisticsChart()}
                ${renderCommandUsageChart()}
            </div>
            <div class="commands-grid">
                ${renderHighlightedCommands()}
            </div>
            <div class="activity-card">
                <div class="activity-header">Recent Activity</div>
                <ul class="activity-list">
                    ${renderActivityList(state.commandHistory)}
                </ul>
            </div>
        `;
    };

    const renderStatCard = (stat) => `
        <div class="stat-card">
            <div class="stat-value">${stat.value}</div>
            <div class="stat-label">${stat.label}</div>
            <div class="stat-change">${stat.change}</div>
        </div>
    `;

    const renderStatisticsChart = () => `
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title">Statistics</div>
            </div>
            <div class="chart-content">
                <div class="bar-chart">
                    ${barChartValues.map(value => `<div class="bar" style="height: ${value}%;"></div>`).join('')}
                </div>
            </div>
            <div class="bar-labels">
                ${barChartLabels.map(label => `<span>${label}</span>`).join('')}
            </div>
        </div>
    `;

    const renderCommandUsageChart = () => `
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title">Command Usage</div>
            </div>
            <div class="chart-content">
                <div class="pie-chart">
                    <div class="pie-slice" style="transform: rotate(0deg) scale(0.8);"></div>
                    <div class="pie-slice" style="transform: rotate(162deg) scale(0.8);"></div>
                    <div class="pie-slice" style="transform: rotate(234deg) scale(0.8);"></div>
                    <div class="pie-center">
                        <div class="pie-percentage">45%</div>
                        <div class="pie-label">Usage</div>
                    </div>
                </div>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color"></div>
                    <div class="legend-text">45% 25%</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color"></div>
                    <div class="legend-text">25% 30%</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color"></div>
                    <div class="legend-text">30% 45%</div>
                </div>
            </div>
        </div>
    `;

    const renderHighlightedCommands = () => {
        const highlighted = commands.slice(0, 3);
        return highlighted.map(command => `
            <div class="command-card ${command.category}">
                <div class="command-header">
                    <div>
                        <div class="command-title">${command.title}</div>
                        <div class="command-text">${command.text}</div>
                    </div>
                    <span class="command-icon">${getCommandIcon(command.id)}</span>
                </div>
                <div class="command-example">${command.example}</div>
            </div>
        `).join('');
    };

    const renderActivityList = (items) => {
        return items.map((item, index) => `
            <li class="activity-item">
                <div class="activity-number">${index + 1}</div>
                <div class="activity-text">${item.text}</div>
            </li>
        `).join('');
    };

    const renderCommandsPage = () => `
        <h1 class="page-title">دستورات استفاده از ربات</h1>
        <div class="commands-grid" id="commands-container">
            ${renderCommands(commands)}
        </div>
    `;

    const renderCommands = (commandList) => {
        return commandList.map(cmd => {
            let html = `
                <div class="command-card ${cmd.category}" data-command-id="${cmd.id}" data-title="${cmd.title}">
                    <div class="command-header">
                        <div>
                            <div class="command-title">${cmd.title}</div>
                            <div class="command-text">${cmd.text}</div>
                        </div>
                        <span class="command-icon">${getCommandIcon(cmd.id)}</span>
                    </div>
                    ${cmd.example ? `<div class="command-example">${cmd.example}</div>` : ''}
            `;

            if (cmd.example2) {
                html += `<div class="command-example">${cmd.example2}</div>`;
            }

            if (cmd.info) {
                html += `<div class="command-text">${cmd.info}</div>`;
            }

            html += '<div class="command-buttons">';

            if (cmd.id === 12) {
                // informational command, no action buttons
            } else if (cmd.id === 15) {
                html += `
                    <button class="command-button info" type="button" data-command="${cmd.command}-on">فعال سازی DM</button>
                    <button class="command-button outline" type="button" data-command="${cmd.command}-off">غیرفعال سازی DM</button>
                `;
            } else if (cmd.id <= 2 || cmd.id === 5 || cmd.id === 6 || cmd.id === 14) {
                html += `<button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">${extractCommandLabel(cmd.title)}</button>`;
            } else {
                html += renderCommandInputs(cmd);
            }

            html += '</div></div>';
            return html;
        }).join('');
    };

    const extractCommandLabel = (title) => {
        const parts = title.split('. ');
        return parts.length > 1 ? parts[1] : title;
    };

    const getCommandIcon = (id) => {
        const icons = {
            1: '⏹️', 2: '▶️', 3: '⏲️', 4: '📅', 5: '🚫', 6: '✅',
            7: '🍽', 8: '🔢', 9: '📦', 10: '📦', 11: '⏰', 12: '❓',
            13: '📤', 14: '🔄', 15: '💬'
        };
        return icons[id] || '⚙️';
    };

    const renderCommandInputs = (cmd) => {
        switch (cmd.id) {
            case 3:
            case 4:
            case 7:
            case 11:
                return `
                    <div class="input-group">
                        <input type="time" data-input="${cmd.command}-start">
                        <input type="time" data-input="${cmd.command}-end">
                        <button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">اجرا</button>
                    </div>
                `;
            case 8:
                return `
                    <div class="input-group">
                        <input type="number" placeholder="محدودیت" min="1" data-input="${cmd.command}">
                        <button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">اجرا</button>
                    </div>
                `;
            case 9:
            case 10:
                return `
                    <div class="input-group">
                        <input type="text" placeholder="متن اطلاعات تحویل" data-input="${cmd.command}">
                        <button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">اجرا</button>
                    </div>
                `;
            case 13:
                return `
                    <div class="input-group">
                        <input type="date" data-input="${cmd.command}-start">
                        <input type="date" data-input="${cmd.command}-end">
                        <button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">اجرا</button>
                    </div>
                `;
            default:
                return `<button class="command-button ${cmd.category}" type="button" data-command="${cmd.command}">اجرا</button>`;
        }
    };

    const renderBlacklistPage = () => `
        <div class="page-title">
            <span>لیست سیاه</span>
            <button class="add-button" id="add-blacklist-btn" type="button">
                <span>+</span>
                اضافه کردن
            </button>
        </div>
        <div class="activity-card">
            <table class="blacklist-table">
                <thead>
                    <tr>
                        <th>ردیف</th>
                        <th>کد کاربر</th>
                        <th>تاریخ اضافه شدن</th>
                        <th>عملیات</th>
                    </tr>
                </thead>
                <tbody id="blacklist-body">
                    ${renderBlacklistRows()}
                </tbody>
            </table>
        </div>
    `;

    const renderBlacklistRows = () => {
        return state.blacklist.map((user, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${user.userId}</td>
                <td>${user.addedDate}</td>
                <td>
                    <button class="delete-btn" data-user-id="${user.userId}">🗑️</button>
                </td>
            </tr>
        `).join('');
    };

    const renderLogsPage = () => `
        <h1 class="page-title">Logs</h1>
        <div class="activity-card">
            <div class="activity-header">Command Execution History</div>
            <ul class="activity-list">
                ${renderActivityList([...state.commandHistory].reverse())}
            </ul>
        </div>
    `;

    const enhanceDynamicContent = (pageName) => {
        if (pageName === 'commands') {
            elements.contentArea.querySelectorAll('.command-button').forEach(button => {
                button.addEventListener('click', handleCommandClick);
            });
        }

        if (pageName === 'blacklist') {
            const addButton = document.getElementById('add-blacklist-btn');
            if (addButton) {
                addButton.addEventListener('click', showAddBlacklistPrompt);
            }

            elements.contentArea.querySelectorAll('.delete-btn').forEach(button => {
                button.addEventListener('click', () => openDeleteModal(button.dataset.userId));
            });
        }
    };

    const handleCommandClick = (event) => {
        const button = event.currentTarget;
        const card = button.closest('.command-card');
        const command = button.dataset.command;
        const title = card ? card.dataset.title : '';

        const inputs = card ? Array.from(card.querySelectorAll('[data-input]')) : [];
        const inputSummary = inputs
            .map(input => input.value)
            .filter(Boolean)
            .join(' ');

        const activityLabel = extractCommandLabel(title);
        const activityText = inputSummary ? `${activityLabel}: ${inputSummary}` : activityLabel;

        state.commandHistory.unshift({
            id: state.commandHistory.length + 1,
            text: `User executed command: ${activityText}`,
            timestamp: new Date()
        });

        if (state.commandHistory.length > 10) {
            state.commandHistory = state.commandHistory.slice(0, 10);
        }

        console.log('Executing command:', command, 'with value:', inputSummary);

        const originalText = button.textContent;
        button.textContent = 'در حال اجرا...';
        button.disabled = true;

        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;

            if (state.currentPage === 'dashboard' || state.currentPage === 'logs') {
                loadPageContent(state.currentPage);
            }
        }, 1000);
    };

    const handleSearch = (event) => {
        if (state.currentPage !== 'commands') {
            return;
        }

        const searchTerm = event.target.value.toLowerCase();
        elements.contentArea.querySelectorAll('.command-card').forEach(card => {
            const title = (card.dataset.title || '').toLowerCase();
            card.style.display = title.includes(searchTerm) ? 'block' : 'none';
        });
    };

    const showAddBlacklistPrompt = () => {
        const userId = prompt('لطفاً کد کاربر را وارد کنید:');
        if (userId && userId.trim() !== '') {
            addBlacklistUser(userId.trim());
        }
    };

    const addBlacklistUser = (userId) => {
        const exists = state.blacklist.some(user => user.userId === userId);
        if (exists) {
            alert('این کاربر قبلاً به لیست سیاه اضافه شده است.');
            return;
        }

        const newUser = {
            id: state.blacklist.length + 1,
            userId,
            addedDate: new Date().toISOString().split('T')[0]
        };

        state.blacklist.push(newUser);
        state.commandHistory.unshift({
            id: state.commandHistory.length + 1,
            text: `User added to blacklist: ${userId}`,
            timestamp: new Date()
        });
        state.commandHistory = state.commandHistory.slice(0, 10);

        if (state.currentPage === 'blacklist') {
            loadPageContent('blacklist');
        }

        if (state.currentPage === 'dashboard') {
            loadPageContent('dashboard');
        }
    };

    const openDeleteModal = (userId) => {
        state.userPendingDeletion = userId;
        elements.deleteModal.removeAttribute('hidden');
        elements.deleteModal.style.display = 'flex';
    };

    const closeDeleteModal = () => {
        state.userPendingDeletion = null;
        elements.deleteModal.setAttribute('hidden', '');
        elements.deleteModal.style.display = 'none';
    };

    const confirmDeleteUser = () => {
        if (!state.userPendingDeletion) {
            return;
        }

        state.blacklist = state.blacklist.filter(user => user.userId !== state.userPendingDeletion);
        state.commandHistory.unshift({
            id: state.commandHistory.length + 1,
            text: `User removed from blacklist: ${state.userPendingDeletion}`,
            timestamp: new Date()
        });
        state.commandHistory = state.commandHistory.slice(0, 10);

        closeDeleteModal();

        if (state.currentPage === 'blacklist') {
            loadPageContent('blacklist');
        }

        if (state.currentPage === 'dashboard') {
            loadPageContent('dashboard');
        }
    };

    const toggleTheme = () => {
        state.isDarkMode = !state.isDarkMode;

        if (state.isDarkMode) {
            document.body.classList.add('dark-mode');
            elements.themeText.textContent = 'Light Mode';
            elements.darkModeToggle.innerHTML = '<span>☀️</span><span>Light Mode</span>';
        } else {
            document.body.classList.remove('dark-mode');
            elements.themeText.textContent = 'Dark Mode';
            elements.darkModeToggle.innerHTML = '<span>🌙</span><span>Dark Mode</span>';
        }
    };

    const toggleMobileMenu = (forceState) => {
        if (typeof forceState === 'boolean') {
            state.isMobileMenuOpen = forceState;
        } else {
            state.isMobileMenuOpen = !state.isMobileMenuOpen;
        }

        if (state.isMobileMenuOpen) {
            elements.mobileMenu.classList.add('open');
            elements.mobileMenu.setAttribute('aria-hidden', 'false');
            elements.mobileMenuOverlay.style.display = 'block';
            elements.mobileMenuOverlay.hidden = false;
            elements.mobileMenuButton.setAttribute('aria-expanded', 'true');
            document.body.style.overflow = 'hidden';
        } else {
            elements.mobileMenu.classList.remove('open');
            elements.mobileMenu.setAttribute('aria-hidden', 'true');
            elements.mobileMenuOverlay.style.display = 'none';
            elements.mobileMenuOverlay.hidden = true;
            elements.mobileMenuButton.setAttribute('aria-expanded', 'false');
            document.body.style.overflow = 'auto';
        }
    };

    const handleResize = () => {
        if (window.innerWidth > 768 && state.isMobileMenuOpen) {
            toggleMobileMenu(false);
        }
    };

    const handleWindowClick = (event) => {
        if (event.target === elements.deleteModal) {
            closeDeleteModal();
        }
    };

    return {
        init
    };
})();

document.addEventListener('DOMContentLoaded', DashboardApp.init);
