/**
 * DevOps CLI Dashboard - Main JavaScript
 * ========================================
 * Organized by functionality
 * 
 * TABLE OF CONTENTS:
 * - Section Navigation
 * - UI Utilities
 * - Developer Tools (CLI Commands, Recent Activity)
 * - Configuration & Monitoring
 * - Apps Management
 * - Servers Management
 * - Websites Management
 * - Users Management
 * - Deployments
 * - Repositories
 * - Security
 * - Logs
 * - Activity
 * - Documents
 * - Search Infrastructure
 * - Real-time Updates (SSE)
 * - Initialization
 */

// ============================================================================
// NAVIGATION & UI UTILITIES
// ============================================================================

        // Update time
        function updateTime() {
            document.getElementById('currentTime').textContent = new Date().toLocaleTimeString();
        }
        setInterval(updateTime, 1000);
        updateTime();

        // Section navigation
        function showSection(section) {
            // Hide all sections
            document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
            
            // Show target section
            const target = document.getElementById(`section-${section}`);
            if (target) {
                target.classList.remove('hidden');
            } else {
                document.getElementById('section-overview').classList.remove('hidden');
                section = 'overview';
            }

            // Update sidebar active state
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('data-section') === section || item.dataset.section === section) {
                    item.classList.add('active');
                }
            });

            // Update Header Title
            const titleEl = document.getElementById('pageTitle');
            const titles = {
                'overview': 'Overview',
                'monitoring': 'Monitoring',
                'apps': 'Applications',
                'servers': 'Servers',
                'websites': 'Websites',
                'deployments': 'Deployments',
                'repos': 'Repositories',
                'security': 'Security',
                'logs': 'Logs',
                'activity': 'Activity',
                'users': 'Users',
                'documents': 'Documents'
            };
            if (titleEl) titleEl.textContent = titles[section] || 'Dashboard';

            // Load section data safely
            if (section === 'apps') loadApps();
            if (section === 'servers') loadServers();
            if (section === 'websites') loadWebsites();
            if (section === 'users') loadUsers();
            if (section === 'monitoring') loadMonitoring();
            if (section === 'deployments') loadDeployments();
            if (section === 'repos') loadRepos();
            if (section === 'security') loadSecurityOverview();
            if (section === 'logs') loadLogSources();
            if (section === 'activity') loadActivity();
            if (section === 'documents') { loadDocuments(); loadResourceOptions(); }
        }

        // Safe element update helper
        function safeUpdateText(id, text) {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        }

        // Logout
        async function logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/login';
        }

        // Refresh data
        function refreshData() {
            loadConfigStatus();
            loadMonitoring();
            loadRecentActivityFeed();
            loadInfrastructureForSearch(); // Refresh search data
            const activeSection = document.querySelector('.sidebar-item.active')?.dataset.section;
            if (activeSection) showSection(activeSection);
        }

        // Copy CLI command to clipboard
        async function copyCommand(command) {
            try {
                await navigator.clipboard.writeText(command);
                // Show toast notification
                const toast = document.createElement('div');
                toast.className = 'fixed top-4 right-4 bg-success text-white px-4 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2';
                toast.innerHTML = '<i class="fas fa-check-circle"></i><span>Command copied to clipboard!</span>';
                document.body.appendChild(toast);
                setTimeout(() => toast.remove(), 2000);
            } catch (err) {
                console.error('Failed to copy command:', err);
            }
        }

        // Load recent activity feed
        async function loadRecentActivityFeed() {
            try {
                const response = await fetch('/api/activity?limit=5');
                const data = await response.json();

                const feed = document.getElementById('recent-activity-feed');
                if (!feed) return;

                if (!data.activities || data.activities.length === 0) {
                    feed.innerHTML = '<div class="text-center py-8 text-gray-500 text-sm">No recent activity</div>';
                    return;
                }

                feed.innerHTML = data.activities.map(activity => {
                    // Backend types: login, deploy, config, user, alert, system, server
                    const iconMap = {
                        'login': 'fa-sign-in-alt',
                        'deploy': 'fa-rocket',
                        'config': 'fa-cog',
                        'user': 'fa-user',
                        'alert': 'fa-exclamation-triangle',
                        'system': 'fa-info-circle',
                        'server': 'fa-server'
                    };

                    const colorMap = {
                        'login': 'text-blue-400',
                        'deploy': 'text-purple-400',
                        'config': 'text-yellow-400',
                        'user': 'text-green-400',
                        'alert': 'text-red-400',
                        'system': 'text-gray-400',
                        'server': 'text-orange-400'
                    };

                    let icon = iconMap[activity.type] || 'fa-circle';
                    let color = colorMap[activity.type] || 'text-gray-400';

                    // Override color for failed activities
                    if (activity.status === 'failed') {
                        color = 'text-red-400';
                        icon = 'fa-times-circle';
                    }

                    const timeAgo = getTimeAgo(activity.timestamp);

                    // Use action field from backend, fallback to message if it exists
                    const message = activity.action || activity.message || 'Activity';
                    const statusBadge = activity.status === 'failed' ?
                        '<span class="ml-2 px-2 py-0.5 bg-red-500/20 text-red-400 text-[10px] rounded-full">FAILED</span>' : '';

                    return `
                        <div class="flex items-start space-x-3 p-3 bg-gray-900/30 rounded-lg border border-gray-700/30 hover:border-gray-600/50 transition-all">
                            <i class="fas ${icon} ${color} mt-1"></i>
                            <div class="flex-1 min-w-0">
                                <p class="text-sm text-gray-300">${escapeHtml(message)}${statusBadge}</p>
                                <p class="text-xs text-gray-500 mt-1">
                                    ${activity.user ? escapeHtml(activity.user) + ' • ' : ''}${timeAgo}
                                </p>
                            </div>
                        </div>
                    `;
                }).join('');

            } catch (error) {
                console.error('Error loading recent activity:', error);
                const feed = document.getElementById('recent-activity-feed');
                if (feed) {
                    feed.innerHTML = '<div class="text-center py-8 text-gray-500 text-sm">Failed to load activity</div>';
                }
            }
        }

        // Helper function to get time ago
        function getTimeAgo(timestamp) {
            const now = new Date();
            const time = new Date(timestamp);
            const diff = Math.floor((now - time) / 1000); // seconds

            if (diff < 60) return 'just now';
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
            return `${Math.floor(diff / 86400)}d ago`;
        }

        // Escape HTML to prevent XSS
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Load config status
        async function loadConfigStatus() {
            try {
                const response = await fetch('/api/config/status');
                const data = await response.json();

                safeUpdateText('stat-apps', data.apps_count || 0);
                safeUpdateText('stat-servers', data.servers_count || 0);
                
                if (!healthTrendChart && document.getElementById('healthTrendChart')) {
                    initHealthTrendChart();
                }
            } catch (error) {
                console.error('Error loading config status:', error);
            }
        }

        // Load monitoring data
        async function loadMonitoring() {
            try {
                const response = await fetch('/api/monitoring');
                const data = await response.json();

                document.getElementById('stat-online').textContent = data.summary?.online || 0;
                document.getElementById('stat-offline').textContent = data.summary?.offline || 0;

                // Update live status on overview
                const liveStatus = document.getElementById('live-status');
                const allItems = [...(data.websites || []), ...(data.apps || []), ...(data.servers || [])];

                if (allItems.length === 0) {
                    liveStatus.innerHTML = '<p class="text-gray-500 text-center py-4">No resources configured for monitoring</p>';
                } else {
                    liveStatus.innerHTML = allItems.slice(0, 6).map(item => `
                        <div class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
                            <div class="flex items-center space-x-3">
                                <div class="w-3 h-3 rounded-full ${item.status === 'online' ? 'bg-success' : item.status === 'degraded' ? 'bg-warning' : 'bg-danger'} ${item.status === 'online' ? '' : 'status-pulse'}"></div>
                                <span>${item.name}</span>
                            </div>
                            <span class="text-sm ${item.status === 'online' ? 'text-success' : item.status === 'degraded' ? 'text-warning' : 'text-danger'}">${item.status}</span>
                        </div>
                    `).join('');
                }

                // Update monitoring section
                updateMonitoringSection(data);

            } catch (error) {
                console.error('Error loading monitoring:', error);
            }
        }

        function updateMonitoringSection(data) {
            // Websites
            const websitesList = document.getElementById('websites-list');
            document.getElementById('websites-count').textContent = data.websites?.length || 0;

            if (data.websites && data.websites.length > 0) {
                websitesList.innerHTML = data.websites.map(w => `
                    <div class="flex items-center justify-between p-4 bg-gray-700/30 rounded-xl">
                        <div class="flex items-center space-x-4">
                            <div class="w-3 h-3 rounded-full ${w.status === 'online' ? 'bg-success' : 'bg-danger'}"></div>
                            <div>
                                <p class="font-medium">${w.name}</p>
                                <p class="text-sm text-gray-500">${w.url || ''}</p>
                            </div>
                        </div>
                        <div class="text-right">
                            <p class="${w.status === 'online' ? 'text-success' : 'text-danger'}">${w.status}</p>
                            <p class="text-sm text-gray-500">${w.response_time ? w.response_time + 'ms' : '-'}</p>
                        </div>
                    </div>
                `).join('');
            } else {
                websitesList.innerHTML = '<p class="text-gray-500 text-center py-4">No websites configured</p>';
            }

            // Apps
            const appsList = document.getElementById('monitor-apps-list');
            document.getElementById('monitor-apps-count').textContent = data.apps?.length || 0;

            if (data.apps && data.apps.length > 0) {
                appsList.innerHTML = data.apps.map(a => `
                    <div class="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                        <div class="flex items-center space-x-3">
                            <div class="w-3 h-3 rounded-full ${a.status === 'online' ? 'bg-success' : 'bg-danger'}"></div>
                            <span>${a.name}</span>
                        </div>
                        <span class="${a.status === 'online' ? 'text-success' : 'text-danger'}">${a.status}</span>
                    </div>
                `).join('');
            } else {
                appsList.innerHTML = '<p class="text-gray-500 text-center py-4">No apps in monitoring</p>';
            }

            // Servers
            const serversList = document.getElementById('monitor-servers-list');
            document.getElementById('monitor-servers-count').textContent = data.servers?.length || 0;

            if (data.servers && data.servers.length > 0) {
                serversList.innerHTML = data.servers.map(s => `
                    <div class="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                        <div class="flex items-center space-x-3">
                            <div class="w-3 h-3 rounded-full ${s.status === 'online' ? 'bg-success' : 'bg-danger'}"></div>
                            <span>${s.name}</span>
                        </div>
                        <span class="${s.status === 'online' ? 'text-success' : 'text-danger'}">${s.status}</span>
                    </div>
                `).join('');
            } else {
                serversList.innerHTML = '<p class="text-gray-500 text-center py-4">No servers in monitoring</p>';
            }
        }

        // Load apps
        async function loadApps() {
            try {
                const response = await fetch('/api/apps');
                const data = await response.json();

                const appsList = document.getElementById('apps-list');

                if (data.apps && data.apps.length > 0) {
                    appsList.innerHTML = data.apps.map(app => `
                        <div class="p-4 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-colors">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center">
                                        <i class="fas fa-cube text-primary"></i>
                                    </div>
                                    <div>
                                        <p class="font-medium">${app.name}</p>
                                        <p class="text-sm text-gray-500">${app.type} • ${app.description || 'No description'}</p>
                                    </div>
                                </div>
                                <button onclick="checkAppHealth('${app.name}')" class="px-3 py-1 bg-gray-600 rounded-lg hover:bg-gray-500 transition-colors text-sm">
                                    <i class="fas fa-heartbeat mr-1"></i>Health
                                </button>
                            </div>
                        </div>
                    `).join('');
                } else {
                    appsList.innerHTML = '<p class="text-gray-500 text-center py-8">No applications configured. Run: devops admin app-add</p>';
                }
            } catch (error) {
                console.error('Error loading apps:', error);
            }
        }

        // Check app health
        async function checkAppHealth(appName) {
            try {
                const response = await fetch(`/api/apps/${appName}/health`);
                const data = await response.json();
                alert(`${appName}: ${data.status}\n${data.response_time ? 'Response: ' + data.response_time + 'ms' : ''}\n${data.error || data.message || ''}`);
            } catch (error) {
                alert('Error checking health: ' + error.message);
            }
        }

        // Load servers
        async function loadServers() {
            try {
                const response = await fetch('/api/servers');
                const data = await response.json();

                const serversList = document.getElementById('servers-list');

                if (data.servers && data.servers.length > 0) {
                    serversList.innerHTML = data.servers.map(server => `
                        <div class="p-4 bg-gray-700/30 rounded-xl">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 bg-warning/20 rounded-xl flex items-center justify-center">
                                        <i class="fas fa-server text-warning"></i>
                                    </div>
                                    <div>
                                        <p class="font-medium">${server.name}</p>
                                        <p class="text-sm text-gray-500">${server.user}@${server.host}:${server.port}</p>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-3">
                                    <div class="flex items-center space-x-2 mr-4">
                                        ${server.tags.map(tag => `<span class="px-2 py-1 bg-gray-600/30 rounded text-[10px] uppercase font-bold text-gray-400">${tag}</span>`).join('')}
                                    </div>
                                    <button onclick="openTerminal('${server.name}')" class="px-3 py-1 bg-warning/20 text-warning border border-warning/30 rounded-lg hover:bg-warning/30 transition-colors text-sm">
                                        <i class="fas fa-terminal mr-1"></i>Run Command
                                    </button>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    serversList.innerHTML = '<p class="text-gray-500 text-center py-8">No servers configured. Run: devops admin server-add</p>';
                }
            } catch (error) {
                console.error('Error loading servers:', error);
            }
        }

        // Load websites
        async function loadWebsites() {
            try {
                const response = await fetch('/api/websites');
                const data = await response.json();

                const websitesList = document.getElementById('websites-main-list');

                if (data.websites && data.websites.length > 0) {
                    websitesList.innerHTML = data.websites.map(website => `
                        <div class="p-4 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-colors">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 bg-accent/20 rounded-xl flex items-center justify-center">
                                        <i class="fas fa-globe text-accent"></i>
                                    </div>
                                    <div>
                                        <p class="font-medium">${website.name}</p>
                                        <p class="text-sm text-gray-500">${website.url}</p>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <span class="px-2 py-1 bg-gray-600 rounded text-xs">${website.method}</span>
                                    <span class="px-2 py-1 bg-gray-600 rounded text-xs">Expected: ${website.expected_status}</span>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    websitesList.innerHTML = '<p class="text-gray-500 text-center py-8">No websites configured. Run: devops admin website-add</p>';
                }
            } catch (error) {
                console.error('Error loading websites:', error);
            }
        }

        // Load users
        async function loadUsers() {
            try {
                const response = await fetch('/api/users');
                if (response.status === 403) {
                    document.getElementById('users-list').innerHTML = '<p class="text-gray-500 text-center py-8">Admin access required</p>';
                    return;
                }
                const data = await response.json();

                const usersList = document.getElementById('users-list');

                if (data.users && data.users.length > 0) {
                    usersList.innerHTML = data.users.map(user => `
                        <div class="p-4 bg-gray-700/30 rounded-xl">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 bg-secondary/20 rounded-full flex items-center justify-center">
                                        <span class="font-bold text-secondary">${(user.name || user.email)[0].toUpperCase()}</span>
                                    </div>
                                    <div>
                                        <p class="font-medium">${user.name || user.email.split('@')[0]}</p>
                                        <p class="text-sm text-gray-500">${user.email}</p>
                                    </div>
                                </div>
                                <div class="flex items-center space-x-3">
                                    <span class="px-3 py-1 ${user.role === 'admin' ? 'bg-secondary/20 text-secondary' : 'bg-primary/20 text-primary'} rounded-full text-sm">${user.role}</span>
                                    <span class="px-3 py-1 ${user.active !== false ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'} rounded-full text-sm">${user.active !== false ? 'Active' : 'Inactive'}</span>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    usersList.innerHTML = '<p class="text-gray-500 text-center py-8">No users found</p>';
                }
            } catch (error) {
                console.error('Error loading users:', error);
            }
        }

        // Add user modal
        function showAddUserModal() {
            document.getElementById('addUserModal').classList.remove('hidden');
            document.getElementById('newUserToken').classList.add('hidden');
        }

        function hideAddUserModal() {
            document.getElementById('addUserModal').classList.add('hidden');
            document.getElementById('addUserForm').reset();
            document.getElementById('newUserToken').classList.add('hidden');
        }

        document.getElementById('addUserForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = document.getElementById('newUserEmail').value;
            const name = document.getElementById('newUserName').value;
            const role = document.getElementById('newUserRole').value;

            try {
                const response = await fetch('/api/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, name, role })
                });

                const data = await response.json();

                if (response.ok && data.token) {
                    document.getElementById('tokenValue').textContent = data.token;
                    document.getElementById('newUserToken').classList.remove('hidden');
                    loadUsers();
                } else {
                    alert(data.detail || 'Error creating user');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });

        // ==================== Deployments ====================
        async function loadDeployments() {
            try {
                const appFilter = document.getElementById('deployFilterApp')?.value || '';
                const statusFilter = document.getElementById('deployFilterStatus')?.value || 'all';

                const response = await fetch(`/api/deployments?app_name=${appFilter}&status=${statusFilter}`);
                const data = await response.json();

                // Update stats
                const deployments = data.deployments || [];
                document.getElementById('deploy-total').textContent = deployments.length;
                document.getElementById('deploy-success').textContent = deployments.filter(d => d.status === 'success').length;
                document.getElementById('deploy-failed').textContent = deployments.filter(d => d.status === 'failed').length;
                document.getElementById('deploy-progress').textContent = deployments.filter(d => d.status === 'in_progress').length;

                // Populate app filter
                const appSelect = document.getElementById('deployFilterApp');
                if (appSelect && appSelect.options.length <= 1 && data.apps) {
                    data.apps.forEach(app => {
                        const option = document.createElement('option');
                        option.value = app;
                        option.textContent = app;
                        appSelect.appendChild(option);
                    });
                }

                // Render deployments
                const list = document.getElementById('deployments-list');
                if (deployments.length > 0) {
                    list.innerHTML = deployments.map(d => `
                        <div class="p-4 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-colors">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 rounded-xl flex items-center justify-center ${
                                        d.status === 'success' ? 'bg-success/20' :
                                        d.status === 'failed' ? 'bg-danger/20' :
                                        d.status === 'in_progress' ? 'bg-warning/20' : 'bg-gray-600/20'
                                    }">
                                        <i class="fas ${
                                            d.status === 'success' ? 'fa-check text-success' :
                                            d.status === 'failed' ? 'fa-times text-danger' :
                                            d.status === 'in_progress' ? 'fa-spinner fa-spin text-warning' : 'fa-undo text-gray-400'
                                        } text-xl"></i>
                                    </div>
                                    <div>
                                        <div class="flex items-center space-x-2">
                                            <p class="font-medium">${d.app}</p>
                                            <span class="px-2 py-0.5 bg-gray-600 rounded text-xs">${d.version}</span>
                                            <span class="px-2 py-0.5 ${d.environment === 'production' ? 'bg-danger/20 text-danger' : 'bg-warning/20 text-warning'} rounded text-xs">${d.environment}</span>
                                        </div>
                                        <p class="text-sm text-gray-400">${d.message}</p>
                                        <p class="text-xs text-gray-500 mt-1">
                                            <i class="fas fa-user mr-1"></i>${d.deployed_by} •
                                            <i class="fas fa-clock mr-1"></i>${new Date(d.deployed_at).toLocaleString()} •
                                            <i class="fas fa-stopwatch mr-1"></i>${d.duration}
                                        </p>
                                    </div>
                                </div>
                                <div class="text-right">
                                    <span class="px-3 py-1 rounded-full text-sm ${
                                        d.status === 'success' ? 'bg-success/20 text-success' :
                                        d.status === 'failed' ? 'bg-danger/20 text-danger' :
                                        d.status === 'in_progress' ? 'bg-warning/20 text-warning' : 'bg-gray-600/20 text-gray-400'
                                    }">${d.status.replace('_', ' ')}</span>
                                    <p class="text-xs text-gray-500 mt-2"><i class="fas fa-code-commit mr-1"></i>${d.commit}</p>
                                </div>
                            </div>
                            ${d.error ? `<div class="mt-3 p-2 bg-danger/10 border border-danger/30 rounded-lg text-sm text-danger"><i class="fas fa-exclamation-triangle mr-2"></i>${d.error}</div>` : ''}
                        </div>
                    `).join('');
                } else {
                    list.innerHTML = '<p class="text-gray-500 text-center py-8">No deployments found</p>';
                }
            } catch (error) {
                console.error('Error loading deployments:', error);
            }
        }

        // ==================== GitHub Repos ====================
        async function loadRepos() {
            try {
                const response = await fetch('/api/github/repos');
                const data = await response.json();

                // Update stats
                document.getElementById('repos-total').textContent = data.total || 0;
                document.getElementById('repos-team').textContent = data.team_name || '-';
                document.getElementById('repos-org').textContent = data.org || '-';
                document.getElementById('repos-org-total').textContent = data.all_count || 0;
                document.getElementById('repos-title').textContent = data.org ? `${data.org} Repositories` : 'GitHub Repositories';

                // Show error if any
                const errorDiv = document.getElementById('repos-error');
                if (data.error) {
                    errorDiv.classList.remove('hidden');
                    document.getElementById('repos-error-text').textContent = data.error;
                    document.getElementById('repos-error-hint').textContent = data.hint || '';
                } else {
                    errorDiv.classList.add('hidden');
                }

                // Render repos
                const list = document.getElementById('repos-list');
                const repos = data.repos || [];
                if (repos.length > 0) {
                    list.innerHTML = repos.map(r => `
                        <div class="relative group bg-gray-700/30 rounded-xl border border-gray-600/30 hover:border-primary/50 transition-all repo-card" data-owner="${data.org}" data-repo="${r.name}">
                            <a href="${r.url}" target="_blank" class="block p-4">
                                <div class="flex items-start justify-between mb-2">
                                    <h4 class="font-medium text-white flex items-center">
                                        <i class="${r.private ? 'fas fa-lock text-yellow-500' : 'fab fa-github'} mr-2"></i>
                                        ${r.name}
                                    </h4>
                                    <div class="repo-pipeline-status text-xs">
                                        <span class="px-2 py-0.5 bg-gray-600 rounded animate-pulse">Checking...</span>
                                    </div>
                                </div>
                                <p class="text-sm text-gray-400 mb-3 line-clamp-2 h-10">${r.description || 'No description'}</p>
                                
                                <div class="mb-3 pt-3 border-t border-gray-600/30 repo-commit-info min-h-[60px]">
                                    <div class="text-xs text-gray-500 flex items-center gap-2 mb-1">
                                        <i class="fas fa-code-branch"></i>
                                        <span class="font-mono bg-gray-800 px-1 rounded">${r.default_branch}</span>
                                    </div>
                                    <p class="text-xs text-gray-300 truncate font-mono repo-commit-msg">Loading commit...</p>
                                    <p class="text-[10px] text-gray-500 repo-commit-meta"></p>
                                </div>

                                <div class="flex items-center text-xs text-gray-500 space-x-3 mt-auto">
                                    ${r.language ? `<span class="px-2 py-0.5 bg-primary/20 text-primary rounded">${r.language}</span>` : ''}
                                    <span><i class="fas fa-star text-yellow-500 mr-1"></i>${r.stars}</span>
                                    <span><i class="fas fa-code-branch mr-1"></i>${r.forks}</span>
                                </div>
                            </a>
                        </div>
                    `).join('');

                    // Lazy load status for each repo
                    document.querySelectorAll('.repo-card').forEach(card => {
                        const owner = card.dataset.owner;
                        const repo = card.dataset.repo;
                        if (owner && repo) {
                            loadRepoStatus(card, owner, repo);
                        }
                    });

                } else if (!data.error) {
                    list.innerHTML = '<p class="text-gray-500 text-center py-8 col-span-3">No repositories found for your team</p>';
                } else {
                    list.innerHTML = '';
                }

                // Load config for admin
                loadGitHubConfig();
            } catch (error) {
                console.error('Error loading repos:', error);
            }
        }

        async function loadRepoStatus(card, owner, repo) {
            try {
                // 1. Fetch Status (Pipeline & Commit)
                const statusResponse = await fetch(`/api/github/repos/${owner}/${repo}/status`);
                const data = await statusResponse.json();

                if (data.error) throw new Error(data.error);

                // Update Pipeline Status
                const statusDiv = card.querySelector('.repo-pipeline-status');
                if (data.pipeline && data.pipeline.status !== 'no_runs') {
                    const status = data.pipeline.conclusion || data.pipeline.status;
                    let colorClass = 'bg-gray-600 text-gray-300';
                    let icon = 'fa-circle';
                    
                    if (status === 'success') {
                        colorClass = 'bg-green-500/20 text-green-400 border border-green-500/30';
                        icon = 'fa-check';
                    } else if (status === 'failure') {
                        colorClass = 'bg-red-500/20 text-red-400 border border-red-500/30';
                        icon = 'fa-times';
                    } else if (status === 'in_progress' || status === 'queued') {
                        colorClass = 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30';
                        icon = 'fa-spinner fa-spin';
                    }

                    statusDiv.innerHTML = `
                        <a href="${data.pipeline.html_url}" target="_blank" class="px-2 py-0.5 rounded flex items-center gap-1 ${colorClass}" title="Latest Run: ${status}">
                            <i class="fas ${icon} text-[10px]"></i>
                            <span class="uppercase font-bold text-[10px]">${status}</span>
                        </a>
                    `;
                } else {
                    statusDiv.innerHTML = `<span class="text-[10px] text-gray-600">No CI/CD</span>`;
                }

                // Update Commit Info
                const commitMsg = card.querySelector('.repo-commit-msg');
                const commitMeta = card.querySelector('.repo-commit-meta');
                
                if (data.commit && data.commit.sha) {
                    commitMsg.textContent = data.commit.message;
                    commitMsg.title = data.commit.message; // Tooltip
                    
                    const timeAgo = new Date(data.commit.date).toLocaleDateString();
                    commitMeta.innerHTML = `
                        <i class="fas fa-user-circle mr-1"></i>${data.commit.author} • ${timeAgo} • 
                        <span class="font-mono text-gray-600">${data.commit.sha}</span>
                    `;
                } else {
                    commitMsg.textContent = "No commits found";
                    commitMeta.textContent = "";
                }

                // 2. Fetch Security Alerts
                const securityResponse = await fetch(`/api/github/repos/${owner}/${repo}/security-alerts`);
                const secData = await securityResponse.json();
                
                if (secData.summary && secData.summary.total > 0) {
                    const total = secData.summary.total;
                    const hasHigh = (secData.alerts.dependabot || []).some(a => a.severity === 'high' || a.severity === 'critical') ||
                                   (secData.alerts.code_scanning || []).some(a => a.severity === 'error' || a.severity === 'high');
                    
                    const badgeColor = hasHigh ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-warning/20 text-warning border-warning/30';
                    
                    const secBadge = document.createElement('div');
                    secBadge.className = `absolute -top-2 -right-2 px-2 py-1 ${badgeColor} border rounded-lg text-[10px] font-bold shadow-lg cursor-pointer hover:scale-110 transition-transform z-10`;
                    secBadge.innerHTML = `<i class="fas fa-shield-alt mr-1"></i>${total}`;
                    secBadge.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        showSection('security');
                        loadSecurityAlerts(owner, repo);
                    };
                    card.appendChild(secBadge);
                }

            } catch (e) {
                console.error(`Failed to load status for ${repo}:`, e);
                card.querySelector('.repo-pipeline-status').innerHTML = `<span class="text-red-900 text-[10px]">!</span>`;
                card.querySelector('.repo-commit-msg').textContent = "Failed to load details";
            }
        }

        // ==================== Security Logic ====================
        let currentSecurityRepo = null;
        let allSecurityAlerts = { dependabot: [], secret_scanning: [], code_scanning: [] };
        let securityChart = null;

        function updateSecurityChart(summary) {
            const ctx = document.getElementById('securityChart').getContext('2d');
            
            const data = {
                labels: ['Critical', 'High', 'Medium', 'Low'],
                datasets: [{
                    label: 'Alerts',
                    data: [
                        summary.critical || 0,
                        summary.high || 0,
                        summary.medium || 0,
                        summary.low || 0
                    ],
                    backgroundColor: [
                        '#ef4444', // Red-500
                        '#f97316', // Orange-500
                        '#f59e0b', // Amber-500
                        '#3b82f6'  // Blue-500
                    ],
                    borderRadius: 8,
                    barThickness: 40
                }]
            };

            if (securityChart) {
                securityChart.data = data;
                securityChart.update();
            } else {
                securityChart = new Chart(ctx, {
                    type: 'bar',
                    data: data,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                ticks: { color: '#9ca3af' }
                            },
                            x: {
                                grid: { display: false },
                                ticks: { color: '#9ca3af' }
                            }
                        }
                    }
                });
            }
            
            updateSecurityRecommendations(summary);
        }

        function updateSecurityRecommendations(summary) {
            const recDiv = document.getElementById('security-recommendation');
            const total = (summary.critical || 0) + (summary.high || 0);
            
            if (total > 0) {
                recDiv.innerHTML = `
                    <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                        <p class="text-sm text-red-400 font-medium mb-1">Critical Action Required</p>
                        <p class="text-xs text-gray-400">${total} high-priority threats found. Invalidate credentials and check your CI/CD pipelines immediately.</p>
                    </div>
                    <div class="p-4 bg-gray-700/30 rounded-xl">
                        <p class="text-xs text-gray-300">💡 Tip: Use 'devops secrets set' to migrate hardcoded keys to encrypted storage.</p>
                    </div>
                `;
            } else {
                recDiv.innerHTML = `
                    <div class="p-4 bg-green-500/10 border border-green-500/20 rounded-xl">
                        <p class="text-sm text-green-400 font-medium mb-1">Health Score: Excellent</p>
                        <p class="text-xs text-gray-400">No critical secrets or vulnerabilities detected in this scan.</p>
                    </div>
                `;
            }
        }

        function exportSecurityReport() {
            const report = {
                exported_at: new Date().toISOString(),
                scope: currentSecurityRepo || 'All',
                summary: {
                    total: (allSecurityAlerts.dependabot?.length || 0) + 
                           (allSecurityAlerts.secret_scanning?.length || 0) + 
                           (allSecurityAlerts.code_scanning?.length || 0),
                    details: allSecurityAlerts
                }
            };
            
            const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `security-report-${currentSecurityRepo || 'global'}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        async function loadSecurityOverview() {
            try {
                const response = await fetch('/api/github/repos');
                const data = await response.json();
                const repos = data.repos || [];
                const org = data.org;

                const list = document.getElementById('security-repo-list');
                if (repos.length > 0) {
                    list.innerHTML = `
                        <button onclick="loadSecurityAlerts('*', '*')" class="w-full text-left px-3 py-2 rounded-lg bg-primary/20 transition-colors flex items-center justify-between group security-repo-btn" data-repo="all">
                            <span class="flex items-center"><i class="fas fa-globe mr-2"></i> All Repositories</span>
                        </button>
                    ` + repos.map(r => `
                        <button onclick="loadSecurityAlerts('${org}', '${r.name}')" class="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-700/50 transition-colors flex items-center justify-between group security-repo-btn" data-repo="${org}/${r.name}">
                            <span class="flex items-center text-sm truncate"><i class="fab fa-github text-gray-500 mr-2"></i> ${r.name}</span>
                        </button>
                    `).join('');
                }
                
                loadSecurityEvents();
            } catch (e) {
                console.error('Error loading security overview:', e);
            }
        }

        async function loadSecurityAlerts(owner, repo) {
            currentSecurityRepo = repo === '*' ? 'All' : repo;
            document.getElementById('security-active-repo').textContent = currentSecurityRepo;
            
            // Highlight active repo button
            document.querySelectorAll('.security-repo-btn').forEach(btn => btn.classList.remove('bg-primary/20'));
            const btnKey = repo === '*' ? 'all' : `${owner}/${repo}`;
            document.querySelector(`[data-repo="${btnKey}"]`)?.classList.add('bg-primary/20');

            const list = document.getElementById('security-alerts-list');
            list.innerHTML = '<div class="text-center py-8"><i class="fas fa-spinner fa-spin mr-2"></i>Fetching alerts...</div>';

            try {
                if (repo === '*') {
                    // Aggregated view logic could go here, for now show placeholder
                    list.innerHTML = '<p class="text-gray-500 text-center py-8">Select a specific repository to see detailed alerts.</p>';
                    return;
                }

                const response = await fetch(`/api/github/repos/${owner}/${repo}/security-alerts`);
                const data = await response.json();
                
                allSecurityAlerts = data.alerts || { dependabot: [], secret_scanning: [], code_scanning: [] };
                
                // Update Stats
                document.getElementById('security-dependabot-total').textContent = data.summary?.dependabot || 0;
                document.getElementById('security-secrets-total').textContent = data.summary?.secret_scanning || 0;
                document.getElementById('security-code-total').textContent = data.summary?.code_scanning || 0;
                document.getElementById('security-total').textContent = data.summary?.total || 0;

                const chartSummary = {
                    critical: data.summary?.critical || 0,
                    high: data.summary?.high || 0,
                    medium: data.summary?.medium || 0,
                    low: data.summary?.low || 0
                };
                
                updateSecurityChart(chartSummary);
                renderActiveSecurityAlerts();
            } catch (e) {
                list.innerHTML = `<p class="text-danger text-center py-8">Error: ${e.message}</p>`;
            }
        }

        function renderActiveSecurityAlerts(isLocal = false) {
            const filter = document.getElementById('alertTypeFilter').value;
            const list = document.getElementById('security-alerts-list');
            let html = '';

            const renderAlert = (alert, type) => {
                const severityColors = {
                    'critical': 'bg-red-600 text-white',
                    'high': 'bg-red-500/20 text-red-400',
                    'medium': 'bg-warning/20 text-warning',
                    'low': 'bg-blue-500/20 text-blue-400',
                    'error': 'bg-red-500/20 text-red-400',
                    'warning': 'bg-warning/20 text-warning',
                    'note': 'bg-gray-600/20 text-gray-400'
                };
                const color = severityColors[alert.severity?.toLowerCase()] || 'bg-gray-700 text-gray-300';
                
                const title = alert.summary || alert.secret_type_display_name || alert.description || 'Security Alert';
                const sub = alert.package_name ? `Package: ${alert.package_name} (${alert.vulnerable_version_range})` : 
                            alert.tool ? `Tool: ${alert.tool}` : `Type: ${alert.secret_type || 'Unknown'}`;

                const actionLabel = isLocal ? 'View File' : 'Fix Alert';
                const actionIcon = isLocal ? 'fa-file-code' : 'fa-external-link-alt';

                return `
                    <div class="p-4 bg-gray-700/30 rounded-xl border border-gray-600/30 hover:border-gray-500 transition-all">
                        <div class="flex items-start justify-between">
                            <div class="flex items-start space-x-4">
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center bg-gray-800 border border-gray-700">
                                    <i class="fas ${type === 'dependabot' ? 'fa-box-open text-warning' : type === 'secret_scanning' ? 'fa-key text-danger' : 'fa-code text-primary'}"></i>
                                </div>
                                <div>
                                    <div class="flex items-center space-x-2 mb-1">
                                        <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${color}">${alert.severity || alert.state}</span>
                                        <p class="font-medium text-sm">${title}</p>
                                    </div>
                                    <p class="text-xs text-gray-400 mb-2">${sub}</p>
                                    <div class="flex items-center space-x-3 text-[10px] text-gray-500">
                                        <span><i class="far fa-clock mr-1"></i>${alert.created_at ? new Date(alert.created_at).toLocaleDateString() : 'Unknown Date'}</span>
                                        ${alert.manifest_path ? `<span><i class="fas fa-file-code mr-1"></i>${alert.manifest_path}</span>` : ''}
                                        ${alert.location ? `<span><i class="fas fa-map-marker-alt mr-1"></i>${alert.location}</span>` : ''}
                                        ${alert.file ? `<span class="truncate max-w-[200px]" title="${alert.file}"><i class="fas fa-file mr-1"></i>${alert.file}</span>` : ''}
                                    </div>
                                </div>
                            </div>
                            <a href="${alert.html_url}" target="_blank" class="px-3 py-1 bg-primary/20 text-primary rounded-lg hover:bg-primary/30 text-xs transition-colors whitespace-nowrap">
                                <i class="fas ${actionIcon} mr-1"></i>${actionLabel}
                            </a>
                        </div>
                    </div>
                `;
            };

            if (filter === 'all' || filter === 'dependabot') {
                allSecurityAlerts.dependabot.forEach(a => html += renderAlert(a, 'dependabot'));
            }
            if (filter === 'all' || filter === 'secret_scanning') {
                allSecurityAlerts.secret_scanning.forEach(a => html += renderAlert(a, 'secret_scanning'));
            }
            if (filter === 'all' || filter === 'code_scanning') {
                allSecurityAlerts.code_scanning.forEach(a => html += renderAlert(a, 'code_scanning'));
            }

            list.innerHTML = html || '<p class="text-gray-500 text-center py-8">No alerts found for selected filters</p>';
        }

        async function loadSecurityEvents() {
            try {
                const response = await fetch('/api/github/security-events');
                const data = await response.json();
                const events = data.events || [];
                
                const list = document.getElementById('security-events-list');
                if (events.length > 0) {
                    list.innerHTML = events.map(e => `
                        <div class="flex items-center justify-between p-3 bg-gray-700/20 rounded-lg text-xs">
                            <div class="flex items-center space-x-3">
                                <div class="w-2 h-2 rounded-full bg-accent animate-pulse"></div>
                                <span class="text-gray-300 font-medium">${e.repo}</span>
                                <span class="text-gray-500">${e.event_type} ${e.action}</span>
                            </div>
                            <span class="text-gray-600">${new Date(e.timestamp).toLocaleTimeString()}</span>
                        </div>
                    `).join('');
                }
            } catch (e) {}
        }

        let securityPollInterval = null;

        function startSecurityEventStream() {
            // Clear existing interval if any
            if (securityPollInterval) {
                clearInterval(securityPollInterval);
            }
            // Poll every 30 seconds - only when user is on security section
            securityPollInterval = setInterval(() => {
                const activeSection = document.querySelector('.sidebar-item.active')?.dataset.section;
                if (activeSection === 'security') {
                    loadSecurityEvents();
                }
            }, 30000);
        }

        async function runLocalSecurityScan() {
            const scanPath = prompt("Enter the local path of the codebase to scan:", ".");
            
            if (scanPath === null) return; // User cancelled prompt

            const list = document.getElementById('security-alerts-list');
            const originalContent = list.innerHTML;
            
            list.innerHTML = `
                <div class="text-center py-12">
                    <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4 status-pulse">
                        <i class="fas fa-shield-alt text-red-500 text-2xl"></i>
                    </div>
                    <p class="text-lg font-medium">Scanning Codebase...</p>
                    <p class="text-sm text-gray-500 mt-1">Path: ${scanPath}</p>
                </div>
            `;

            try {
                const response = await fetch(`/api/security/local-scan?path=${encodeURIComponent(scanPath)}`);
                const data = await response.json();

                                if (data.success) {

                                    const results = data.results;

                                    allSecurityAlerts = { 

                                        dependabot: [], 

                                        secret_scanning: results.secrets || [], 

                                        code_scanning: results.vulnerabilities || [] 

                                    };

                                    

                                    const actualPath = data.path || scanPath;

                                    document.getElementById('security-active-repo').textContent = `Local: ${actualPath}`;

                                                        document.getElementById('security-secrets-total').textContent = results.summary.critical || 0;

                                                        document.getElementById('security-total').textContent = results.summary.critical || 0;

                                                        

                                                        updateSecurityChart(results.summary);

                                                        renderActiveSecurityAlerts(true); // Pass true to indicate local scan

                                    

                                }

                 else {
                    alert('Scan failed: ' + (data.detail || data.error));
                    list.innerHTML = originalContent;
                }
            } catch (e) {
                alert('Scan error: ' + e.message);
                list.innerHTML = originalContent;
            }
        }

        async function loadGitHubConfig() {
            try {
                const response = await fetch('/api/github/config');
                if (response.ok) {
                    const data = await response.json();
                    const orgInput = document.getElementById('github-org-input');
                    if (orgInput) orgInput.value = data.org || '';
                }
            } catch (e) {}
        }

        async function saveGitHubConfig() {
            try {
                const org = document.getElementById('github-org-input')?.value || '';
                const token = document.getElementById('github-token-input')?.value || '';

                const response = await fetch('/api/github/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ org, token: token || undefined })
                });

                if (response.ok) {
                    alert('GitHub configuration saved!');
                    loadRepos();
                }
            } catch (error) {
                alert('Error saving configuration');
            }
        }

        // ==================== Logs ====================
        let currentLogSource = null;
        let liveLogEventSource = null;
        let currentLogs = [];

        async function loadLogSources() {
            try {
                const appsResponse = await fetch('/api/apps');
                const appsData = await appsResponse.json();

                const serversResponse = await fetch('/api/servers');
                const serversData = await serversResponse.json();

                const sources = document.getElementById('log-sources');
                let html = '';

                // Apps
                if (appsData.apps && appsData.apps.length > 0) {
                    html += '<p class="text-xs text-gray-500 uppercase mb-2">Applications</p>';
                    html += appsData.apps.map(app => `
                        <button onclick="loadAppLogs('${app.name}')" class="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-700/50 transition-colors flex items-center justify-between group log-source-btn" data-source="app-${app.name}">
                            <span class="flex items-center">
                                <i class="fas fa-cube text-accent mr-2"></i>
                                ${app.name}
                            </span>
                            <span class="text-xs text-gray-500">${app.type}</span>
                        </button>
                    `).join('');
                }

                // Servers
                if (serversData.servers && serversData.servers.length > 0) {
                    html += '<p class="text-xs text-gray-500 uppercase mb-2 mt-4">Servers</p>';
                    html += serversData.servers.map(server => `
                        <button onclick="loadServerLogs('${server.name}')" class="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-700/50 transition-colors flex items-center justify-between group log-source-btn" data-source="server-${server.name}">
                            <span class="flex items-center">
                                <i class="fas fa-server text-warning mr-2"></i>
                                ${server.name}
                            </span>
                            <span class="text-xs text-gray-500">${server.host}</span>
                        </button>
                    `).join('');
                }

                sources.innerHTML = html || '<p class="text-gray-500 text-sm">No log sources configured</p>';
            } catch (error) {
                console.error('Error loading log sources:', error);
            }
        }

        async function loadAppLogs(appName) {
            currentLogSource = { type: 'app', name: appName };
            document.getElementById('log-viewer-title').textContent = `${appName} Logs`;

            // Highlight active source
            document.querySelectorAll('.log-source-btn').forEach(btn => btn.classList.remove('bg-primary/20'));
            document.querySelector(`[data-source="app-${appName}"]`)?.classList.add('bg-primary/20');

            try {
                const level = document.getElementById('logLevelFilter').value;
                const response = await fetch(`/api/apps/${appName}/logs?level=${level}`);
                const data = await response.json();

                currentLogs = data.logs || [];
                renderLogs(currentLogs, data);
            } catch (error) {
                console.error('Error loading app logs:', error);
            }
        }

        async function loadServerLogs(serverName) {
            currentLogSource = { type: 'server', name: serverName };
            document.getElementById('log-viewer-title').textContent = `${serverName} Logs`;

            // Highlight active source
            document.querySelectorAll('.log-source-btn').forEach(btn => btn.classList.remove('bg-primary/20'));
            document.querySelector(`[data-source="server-${serverName}"]`)?.classList.add('bg-primary/20');

            try {
                const response = await fetch(`/api/servers/${serverName}/logs`);
                const data = await response.json();

                currentLogs = data.logs || [];
                renderLogs(currentLogs, data);
            } catch (error) {
                console.error('Error loading server logs:', error);
            }
        }

        function renderLogs(logs, metadata = {}) {
            const viewer = document.getElementById('log-viewer');

            // Build header with source info
            let headerHtml = '';
            if (metadata.source_used || metadata.document_available !== undefined) {
                headerHtml = `<div class="mb-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
                    <div class="flex items-center justify-between flex-wrap gap-2">
                        <div class="flex items-center space-x-3">
                            ${metadata.source_used ? `
                                <span class="px-2 py-1 rounded text-xs ${
                                    metadata.source_used === 'cloudwatch' ? 'bg-orange-500/20 text-orange-400' :
                                    metadata.source_used === 'document' ? 'bg-blue-500/20 text-blue-400' :
                                    metadata.source_used === 'none' ? 'bg-gray-500/20 text-gray-400' :
                                    'bg-green-500/20 text-green-400'
                                }">
                                    <i class="fas ${
                                        metadata.source_used === 'cloudwatch' ? 'fa-cloud' :
                                        metadata.source_used === 'document' ? 'fa-file-alt' :
                                        metadata.source_used === 'none' ? 'fa-info-circle' :
                                        'fa-stream'
                                    } mr-1"></i>
                                    Source: ${metadata.source_used}
                                </span>
                            ` : ''}
                            ${metadata.document_available ? `
                                <span class="px-2 py-1 rounded text-xs bg-blue-500/20 text-blue-400">
                                    <i class="fas fa-file-alt mr-1"></i>Document available
                                </span>
                            ` : ''}
                        </div>
                        ${metadata.message ? `<span class="text-xs text-gray-400">${metadata.message}</span>` : ''}
                    </div>
                    ${metadata.hint ? `<p class="text-xs text-gray-500 mt-2"><i class="fas fa-lightbulb mr-1 text-yellow-500"></i>${metadata.hint}</p>` : ''}
                </div>`;
            }

            if (logs.length > 0) {
                viewer.innerHTML = headerHtml + logs.map(log => `
                    <div class="flex items-start space-x-2 py-1 border-b border-gray-800/50 hover:bg-gray-800/30">
                        <span class="text-gray-500 text-xs whitespace-nowrap">${new Date(log.timestamp).toLocaleTimeString()}</span>
                        <span class="px-1.5 py-0.5 rounded text-xs font-medium ${
                            log.level === 'ERROR' ? 'bg-danger/20 text-danger' :
                            log.level === 'WARN' ? 'bg-warning/20 text-warning' :
                            log.level === 'INFO' ? 'bg-success/20 text-success' :
                            'bg-gray-600/20 text-gray-400'
                        }">${log.level}</span>
                        <span class="text-gray-300 flex-1">${log.message}</span>
                    </div>
                `).join('');
                viewer.scrollTop = viewer.scrollHeight;
            } else {
                viewer.innerHTML = headerHtml + '<p class="text-gray-500">No logs found</p>';
            }
        }

        function filterLogs() {
            const level = document.getElementById('logLevelFilter').value;
            if (level === 'all') {
                renderLogs(currentLogs);
            } else {
                const filtered = currentLogs.filter(l => l.level.toLowerCase() === level);
                renderLogs(filtered);
            }
        }

        function refreshLogs() {
            if (currentLogSource) {
                if (currentLogSource.type === 'app') {
                    loadAppLogs(currentLogSource.name);
                } else {
                    loadServerLogs(currentLogSource.name);
                }
            }
        }

        function toggleLiveLogs() {
            const btn = document.getElementById('liveLogBtn');

            if (liveLogEventSource) {
                liveLogEventSource.close();
                liveLogEventSource = null;
                btn.innerHTML = '<i class="fas fa-play mr-1"></i> Live';
                btn.classList.remove('bg-success', 'text-white');
                return;
            }

            if (!currentLogSource || currentLogSource.type !== 'app') {
                alert('Select an application to stream live logs');
                return;
            }

            btn.innerHTML = '<i class="fas fa-stop mr-1"></i> Stop';
            btn.classList.add('bg-success', 'text-white');

            liveLogEventSource = new EventSource(`/api/apps/${currentLogSource.name}/logs/stream`);

            liveLogEventSource.onmessage = (event) => {
                try {
                    const log = JSON.parse(event.data);
                    currentLogs.push(log);
                    if (currentLogs.length > 100) currentLogs.shift();
                    renderLogs(currentLogs);
                } catch (e) {
                    console.error('Live log parse error:', e);
                }
            };

            liveLogEventSource.onerror = () => {
                toggleLiveLogs(); // Stop on error
            };
        }

        // ==================== Expanded Log Viewer ====================
        let expandedLiveEventSource = null;
        let expandedLogs = [];

        function expandLogViewer() {
            const modal = document.getElementById('expanded-log-modal');
            const title = document.getElementById('expanded-log-title');
            const source = document.getElementById('expanded-log-source');

            if (!currentLogSource) {
                alert('Please select a log source first');
                return;
            }

            // Set title and source
            title.textContent = `Logs: ${currentLogSource.name}`;
            source.textContent = currentLogSource.type === 'app' ? 'Application' : 'Server';

            // Copy current logs to expanded view
            expandedLogs = [...currentLogs];
            renderExpandedLogs(expandedLogs);

            // Sync filter
            document.getElementById('expandedLogLevelFilter').value = document.getElementById('logLevelFilter').value;

            // Show modal
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        function closeExpandedLogViewer() {
            const modal = document.getElementById('expanded-log-modal');
            modal.classList.add('hidden');
            document.body.style.overflow = 'auto';

            // Stop live stream if active
            if (expandedLiveEventSource) {
                expandedLiveEventSource.close();
                expandedLiveEventSource = null;
                document.getElementById('expandedLiveLogBtn').innerHTML = '<i class="fas fa-play mr-1"></i> Live Stream';
                document.getElementById('expanded-live-indicator').classList.add('hidden');
            }
        }

        function renderExpandedLogs(logs) {
            const viewer = document.getElementById('expanded-log-viewer');
            const autoScroll = document.getElementById('expanded-auto-scroll').checked;

            // Update counts
            document.getElementById('expanded-log-count').textContent = logs.length;
            document.getElementById('expanded-error-count').textContent = logs.filter(l => l.level === 'ERROR').length;
            document.getElementById('expanded-warn-count').textContent = logs.filter(l => l.level === 'WARN').length;
            document.getElementById('expanded-info-count').textContent = logs.filter(l => l.level === 'INFO').length;

            if (logs.length > 0) {
                viewer.innerHTML = logs.map((log, index) => `
                    <div class="flex items-start space-x-3 py-2 border-b border-gray-800/50 hover:bg-gray-800/30 log-entry" data-index="${index}">
                        <span class="text-gray-600 text-xs w-8">${index + 1}</span>
                        <span class="text-gray-500 text-xs whitespace-nowrap w-24">${new Date(log.timestamp).toLocaleTimeString()}</span>
                        <span class="px-2 py-0.5 rounded text-xs font-medium w-16 text-center ${
                            log.level === 'ERROR' ? 'bg-red-500/20 text-red-400' :
                            log.level === 'WARN' ? 'bg-yellow-500/20 text-yellow-400' :
                            log.level === 'INFO' ? 'bg-green-500/20 text-green-400' :
                            log.level === 'DEBUG' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-gray-600/20 text-gray-400'
                        }">${log.level}</span>
                        <span class="text-gray-400 text-xs w-32 truncate">${log.source || '-'}</span>
                        <span class="text-gray-200 flex-1 break-all">${escapeHtml(log.message)}</span>
                    </div>
                `).join('');

                if (autoScroll) {
                    viewer.scrollTop = viewer.scrollHeight;
                }
            } else {
                viewer.innerHTML = '<p class="text-gray-500 text-center py-8">No logs to display</p>';
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function filterExpandedLogs() {
            const level = document.getElementById('expandedLogLevelFilter').value;
            if (level === 'all') {
                renderExpandedLogs(expandedLogs);
            } else {
                const filtered = expandedLogs.filter(l => l.level.toLowerCase() === level);
                renderExpandedLogs(filtered);
            }
        }

        function searchExpandedLogs() {
            const query = document.getElementById('expanded-log-search').value.toLowerCase();
            const level = document.getElementById('expandedLogLevelFilter').value;

            let filtered = expandedLogs;

            if (level !== 'all') {
                filtered = filtered.filter(l => l.level.toLowerCase() === level);
            }

            if (query) {
                filtered = filtered.filter(l =>
                    l.message.toLowerCase().includes(query) ||
                    (l.source && l.source.toLowerCase().includes(query))
                );
            }

            renderExpandedLogs(filtered);
        }

        async function refreshExpandedLogs() {
            if (!currentLogSource) return;

            try {
                let response;
                if (currentLogSource.type === 'app') {
                    response = await fetch(`/api/apps/${currentLogSource.name}/logs`);
                } else {
                    response = await fetch(`/api/servers/${currentLogSource.name}/logs`);
                }
                const data = await response.json();
                expandedLogs = data.logs || [];
                filterExpandedLogs();
            } catch (error) {
                console.error('Error refreshing expanded logs:', error);
            }
        }

        function toggleExpandedLiveLogs() {
            const btn = document.getElementById('expandedLiveLogBtn');
            const indicator = document.getElementById('expanded-live-indicator');

            if (expandedLiveEventSource) {
                expandedLiveEventSource.close();
                expandedLiveEventSource = null;
                btn.innerHTML = '<i class="fas fa-play mr-1"></i> Live Stream';
                btn.classList.remove('bg-red-600');
                btn.classList.add('bg-gray-700');
                indicator.classList.add('hidden');
                return;
            }

            if (!currentLogSource || currentLogSource.type !== 'app') {
                alert('Live streaming is only available for applications');
                return;
            }

            btn.innerHTML = '<i class="fas fa-stop mr-1"></i> Stop';
            btn.classList.remove('bg-gray-700');
            btn.classList.add('bg-red-600');
            indicator.classList.remove('hidden');

            expandedLiveEventSource = new EventSource(`/api/apps/${currentLogSource.name}/logs/stream`);

            expandedLiveEventSource.onmessage = (event) => {
                try {
                    const log = JSON.parse(event.data);
                    expandedLogs.push(log);
                    if (expandedLogs.length > 500) expandedLogs.shift();
                    filterExpandedLogs();
                } catch (e) {
                    console.error('Expanded live log parse error:', e);
                }
            };

            expandedLiveEventSource.onerror = () => {
                toggleExpandedLiveLogs();
            };
        }

        function downloadLogs() {
            if (expandedLogs.length === 0) {
                alert('No logs to download');
                return;
            }

            const content = expandedLogs.map(l =>
                `[${l.timestamp}] [${l.level}] [${l.source || '-'}] ${l.message}`
            ).join('\n');

            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `logs-${currentLogSource.name}-${new Date().toISOString().slice(0,10)}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        // Close expanded view on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !document.getElementById('expanded-log-modal').classList.contains('hidden')) {
                closeExpandedLogViewer();
            }
        });

        // ==================== Activity ====================
        async function loadActivity() {
            try {
                const filter = document.getElementById('activityFilter')?.value || 'all';
                const response = await fetch(`/api/activity?activity_type=${filter}`);
                const data = await response.json();

                const list = document.getElementById('activity-list');
                const activities = data.activities || [];

                if (activities.length > 0) {
                    list.innerHTML = activities.map(a => `
                        <div class="flex items-start space-x-4 p-4 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-colors">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center ${
                                a.type === 'login' ? 'bg-primary/20' :
                                a.type === 'deploy' ? 'bg-pink-500/20' :
                                a.type === 'config' ? 'bg-accent/20' :
                                a.type === 'user' ? 'bg-secondary/20' :
                                a.type === 'alert' ? 'bg-warning/20' : 'bg-gray-600/20'
                            }">
                                <i class="fas ${
                                    a.type === 'login' ? 'fa-sign-in-alt text-primary' :
                                    a.type === 'deploy' ? 'fa-rocket text-pink-500' :
                                    a.type === 'config' ? 'fa-cog text-accent' :
                                    a.type === 'user' ? 'fa-user text-secondary' :
                                    a.type === 'alert' ? 'fa-bell text-warning' : 'fa-info text-gray-400'
                                }"></i>
                            </div>
                            <div class="flex-1">
                                <div class="flex items-center justify-between">
                                    <p class="font-medium">${a.action}</p>
                                    <span class="px-2 py-1 rounded text-xs ${
                                        a.status === 'success' ? 'bg-success/20 text-success' :
                                        a.status === 'failed' ? 'bg-danger/20 text-danger' :
                                        'bg-warning/20 text-warning'
                                    }">${a.status}</span>
                                </div>
                                <p class="text-sm text-gray-400 mt-1">
                                    <i class="fas fa-user mr-1"></i>${a.user} •
                                    <i class="fas fa-globe mr-1"></i>${a.ip} •
                                    <i class="fas fa-clock mr-1"></i>${new Date(a.timestamp).toLocaleString()}
                                </p>
                            </div>
                        </div>
                    `).join('');
                } else {
                    list.innerHTML = '<p class="text-gray-500 text-center py-8">No activity found</p>';
                }
            } catch (error) {
                console.error('Error loading activity:', error);
            }
        }

        // ==================== Documents ====================
        async function loadDocuments() {
            try {
                const response = await fetch('/api/documents');
                if (response.status === 403) {
                    document.getElementById('documents-list').innerHTML = '<p class="text-gray-500 text-center py-8">Admin access required</p>';
                    return;
                }
                const data = await response.json();

                const list = document.getElementById('documents-list');
                const documents = data.documents || {};
                const docArray = Object.entries(documents);

                if (docArray.length > 0) {
                    list.innerHTML = docArray.map(([key, doc]) => `
                        <div class="p-4 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-colors">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-4">
                                    <div class="w-12 h-12 ${doc.original_name.endsWith('.pdf') ? 'bg-red-500/20' : 'bg-blue-500/20'} rounded-xl flex items-center justify-center">
                                        <i class="fas ${doc.original_name.endsWith('.pdf') ? 'fa-file-pdf text-red-500' : 'fa-file-alt text-blue-500'} text-xl"></i>
                                    </div>
                                    <div>
                                        <p class="font-medium">${doc.original_name}</p>
                                        <p class="text-sm text-gray-400">
                                            <span class="px-2 py-0.5 ${doc.resource_type === 'app' ? 'bg-accent/20 text-accent' : 'bg-warning/20 text-warning'} rounded text-xs mr-2">${doc.resource_type}</span>
                                            ${doc.resource_name}
                                        </p>
                                        <p class="text-xs text-gray-500 mt-1">
                                            <i class="fas fa-user mr-1"></i>${doc.uploaded_by} •
                                            <i class="fas fa-clock mr-1"></i>${new Date(doc.uploaded_at).toLocaleString()} •
                                            <i class="fas fa-file mr-1"></i>${(doc.size / 1024).toFixed(1)} KB
                                        </p>
                                    </div>
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/api/documents/${doc.resource_type}/${doc.resource_name}/download" class="px-3 py-1 bg-primary/20 text-primary rounded-lg hover:bg-primary/30 text-sm">
                                        <i class="fas fa-download"></i>
                                    </a>
                                    <button onclick="deleteDocument('${doc.resource_type}', '${doc.resource_name}')" class="px-3 py-1 bg-danger/20 text-danger rounded-lg hover:bg-danger/30 text-sm">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </div>
                            ${doc.description ? `<p class="text-sm text-gray-400 mt-2 pl-16">${doc.description}</p>` : ''}
                        </div>
                    `).join('');
                } else {
                    list.innerHTML = `
                        <div class="text-center py-8">
                            <i class="fas fa-file-upload text-4xl text-gray-600 mb-3"></i>
                            <p class="text-gray-500">No documents uploaded yet</p>
                            <p class="text-gray-600 text-sm mt-1">Upload log documentation for apps and servers</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading documents:', error);
            }
        }

        async function loadResourceOptions() {
            const type = document.getElementById('docResourceType').value;
            const select = document.getElementById('docResourceName');

            try {
                let response;
                if (type === 'app') {
                    response = await fetch('/api/apps');
                    const data = await response.json();
                    select.innerHTML = '<option value="">Select application...</option>' +
                        (data.apps || []).map(app => `<option value="${app.name}">${app.name}</option>`).join('');
                } else if (type === 'server') {
                    response = await fetch('/api/servers');
                    const data = await response.json();
                    select.innerHTML = '<option value="">Select server...</option>' +
                        (data.servers || []).map(server => `<option value="${server.name}">${server.name}</option>`).join('');
                } else if (type === 'website') {
                    response = await fetch('/api/websites');
                    const data = await response.json();
                    select.innerHTML = '<option value="">Select website...</option>' +
                        (data.websites || []).map(website => `<option value="${website.name}">${website.name}</option>`).join('');
                }
            } catch (error) {
                console.error('Error loading resources:', error);
            }
        }

        async function deleteDocument(resourceType, resourceName) {
            if (!confirm(`Are you sure you want to delete this document?`)) return;

            try {
                const response = await fetch(`/api/documents/${resourceType}/${resourceName}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    loadDocuments();
                } else {
                    const data = await response.json();
                    alert(data.detail || 'Error deleting document');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        // Handle document upload form
        document.addEventListener('DOMContentLoaded', () => {
            const uploadForm = document.getElementById('uploadDocForm');
            if (uploadForm) {
                uploadForm.addEventListener('submit', async (e) => {
                    e.preventDefault();

                    const resourceType = document.getElementById('docResourceType').value;
                    const resourceName = document.getElementById('docResourceName').value;
                    const file = document.getElementById('docFile').files[0];
                    const description = document.getElementById('docDescription').value;

                    if (!resourceName) {
                        alert('Please select a resource');
                        return;
                    }

                    if (!file) {
                        alert('Please select a file');
                        return;
                    }

                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('description', description);

                    try {
                        const response = await fetch(`/api/documents/${resourceType}/${resourceName}`, {
                            method: 'POST',
                            body: formData
                        });

                        const data = await response.json();

                        if (response.ok) {
                            alert('Document uploaded successfully!');
                            uploadForm.reset();
                            loadDocuments();
                        } else {
                            alert(data.detail || 'Error uploading document');
                        }
                    } catch (error) {
                        alert('Error: ' + error.message);
                    }
                });
            }

            const uploadConfigForm = document.getElementById('uploadConfigForm');
            if (uploadConfigForm) {
                uploadConfigForm.addEventListener('submit', async (e) => {
                    e.preventDefault();

                    const configType = document.getElementById('configType').value;
                    const configFile = document.getElementById('configFile').files[0];
                    const mergeOption = document.getElementById('configMergeOption').value;

                    if (!configFile) {
                        alert('Please select a configuration file');
                        return;
                    }

                    const formData = new FormData();
                    formData.append('file', configFile);
                    formData.append('config_type', configType);
                    formData.append('merge', mergeOption === 'merge');

                    try {
                        const response = await fetch('/api/config/upload', {
                            method: 'POST',
                            body: formData
                        });

                        const data = await response.json();

                        if (response.ok) {
                            alert(data.message || 'Configuration uploaded successfully!');
                            uploadConfigForm.reset();
                            refreshData(); // Refresh all data after config upload
                        } else {
                            alert(data.detail || 'Error uploading configuration');
                        }
                    } catch (error) {
                        alert('Error: ' + error.message);
                    }
                });
            }
        });

        // Real-time updates via SSE
        let monitoringEventSource = null;
        let sseReconnectAttempts = 0;
        const MAX_SSE_RECONNECT_ATTEMPTS = 5;

        function startRealtimeUpdates() {
            // Close existing connection if any
            if (monitoringEventSource) {
                monitoringEventSource.close();
            }

            monitoringEventSource = new EventSource('/api/monitoring/stream');

            monitoringEventSource.onmessage = (event) => {
                // Reset reconnect attempts on successful message
                sseReconnectAttempts = 0;

                try {
                    const data = JSON.parse(event.data);
                    if (!data.error) {
                        updateMonitoringSection(data);

                        // Update overview live status list safely
                        const liveStatusDiv = document.getElementById('live-status');
                        const allItems = [...(data.websites || []), ...(data.apps || []), ...(data.servers || [])];
                        if (liveStatusDiv && allItems.length > 0) {
                            liveStatusDiv.innerHTML = allItems.slice(0, 6).map(item => `
                                <div class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
                                    <div class="flex items-center space-x-3">
                                        <div class="w-3 h-3 rounded-full ${item.status === 'online' ? 'bg-success' : 'bg-danger'}"></div>
                                        <span>${item.name}</span>
                                    </div>
                                    <span class="text-sm ${item.status === 'online' ? 'text-success' : 'text-danger'}">${item.status}</span>
                                </div>
                            `).join('');
                        }

                        // Update stats safely
                        const online = (data.websites?.filter(w => w.status === 'online').length || 0) +
                                      (data.apps?.filter(a => a.status === 'online').length || 0) +
                                      (data.servers?.filter(s => s.status === 'online').length || 0);
                        const offline = (data.websites?.filter(w => w.status === 'offline').length || 0) +
                                       (data.apps?.filter(a => a.status === 'offline').length || 0) +
                                       (data.servers?.filter(s => s.status === 'offline').length || 0);

                        safeUpdateText('stat-online', online);
                        safeUpdateText('stat-offline', offline);

                        updateHealthTrend(online, online + offline);
                    }
                } catch (e) {
                    console.error('SSE parse error:', e);
                }
            };

            monitoringEventSource.onerror = () => {
                monitoringEventSource.close();
                monitoringEventSource = null;

                // Limit reconnection attempts
                if (sseReconnectAttempts < MAX_SSE_RECONNECT_ATTEMPTS) {
                    sseReconnectAttempts++;
                    const delay = Math.min(5000 * sseReconnectAttempts, 30000); // Exponential backoff, max 30s
                    console.log(`SSE connection error, reconnecting in ${delay/1000}s... (attempt ${sseReconnectAttempts}/${MAX_SSE_RECONNECT_ATTEMPTS})`);
                    setTimeout(startRealtimeUpdates, delay);
                } else {
                    console.log('SSE max reconnection attempts reached. Real-time updates disabled.');
                }
            };
        }

        // Cleanup connections on page unload
        window.addEventListener('beforeunload', () => {
            if (monitoringEventSource) monitoringEventSource.close();
            if (liveLogEventSource) liveLogEventSource.close();
            if (expandedLiveEventSource) expandedLiveEventSource.close();
            if (securityPollInterval) clearInterval(securityPollInterval);
        });

        // Pause/resume updates when tab visibility changes (performance optimization)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Tab is hidden - pause intensive operations
                if (monitoringEventSource) {
                    monitoringEventSource.close();
                    monitoringEventSource = null;
                }
            } else {
                // Tab is visible - resume operations
                if (!monitoringEventSource) {
                    sseReconnectAttempts = 0; // Reset attempts
                    startRealtimeUpdates();
                }
                // Refresh data when returning to tab
                loadConfigStatus();
                loadMonitoring();
                loadRecentActivityFeed();
            }
        });

        // ==================== Premium Features: Terminal & Search ====================
        let activeTerminalServer = null;

        function openTerminal(serverName) {
            activeTerminalServer = serverName;
            document.getElementById('terminalServerName').textContent = serverName;
            document.getElementById('terminalModal').classList.remove('hidden');
            document.getElementById('terminalInput').focus();
            document.getElementById('terminalOutput').innerHTML = `<p class="text-gray-500 italic">Connected to ${serverName}. Ready for input...</p>`;
        }

        function closeTerminal() {
            document.getElementById('terminalModal').classList.add('hidden');
            activeTerminalServer = null;
        }

        async function executeRemoteCommand() {
            const input = document.getElementById('terminalInput');
            const output = document.getElementById('terminalOutput');
            const command = input.value.trim();
            
            if (!command || !activeTerminalServer) return;

            // Log command locally in terminal
            output.innerHTML += `<div class="mt-2 text-primary"> <span class="text-gray-500">$</span> ${command}</div>`;
            input.value = '';
            output.scrollTop = output.scrollHeight;

            try {
                const response = await fetch(`/api/servers/${activeTerminalServer}/exec`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command })
                });
                const data = await response.json();

                if (data.success) {
                    output.innerHTML += `<pre class="mt-1 text-gray-300 whitespace-pre-wrap">${data.output || '(No output)'}</pre>`;
                } else {
                    output.innerHTML += `<div class="mt-1 text-red-400">Error: ${data.error}</div>`;
                }
            } catch (e) {
                output.innerHTML += `<div class="mt-1 text-red-400">Connection error: ${e.message}</div>`;
            }
            output.scrollTop = output.scrollHeight;
        }

        // Global infrastructure search cache
        let infraSearchCache = {
            apps: [],
            servers: [],
            websites: [],
            repos: [],
            users: [],
            lastUpdated: null
        };

        // Debounce search input
        let searchTimeout;
        function debounceSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                handleGlobalSearch();
            }, 300); // Wait 300ms after user stops typing
        }

        // Load infrastructure data for search
        async function loadInfrastructureForSearch() {
            try {
                // Only reload if cache is older than 30 seconds
                if (infraSearchCache.lastUpdated && (Date.now() - infraSearchCache.lastUpdated) < 30000) {
                    return;
                }

                const [appsRes, serversRes, websitesRes, reposRes] = await Promise.all([
                    fetch('/api/apps').catch(() => ({json: () => ({apps: []})})),
                    fetch('/api/servers').catch(() => ({json: () => ({servers: []})})),
                    fetch('/api/websites').catch(() => ({json: () => ({websites: []})})),
                    fetch('/api/repos/status').catch(() => ({json: () => ({repos: []})}))
                ]);

                const [apps, servers, websites, repos] = await Promise.all([
                    appsRes.json(),
                    serversRes.json(),
                    websitesRes.json(),
                    reposRes.json()
                ]);

                infraSearchCache = {
                    apps: apps.apps || [],
                    servers: servers.servers || [],
                    websites: websites.websites || [],
                    repos: repos.repos || [],
                    lastUpdated: Date.now()
                };
            } catch (error) {
                console.error('Error loading infrastructure for search:', error);
            }
        }

        // Global Search
        async function handleGlobalSearch() {
            const query = document.getElementById('globalSearch').value.toLowerCase().trim();
            const resultsDiv = document.getElementById('searchResults');

            if (!query) {
                resultsDiv.classList.add('hidden');
                return;
            }

            // Load data if not cached
            await loadInfrastructureForSearch();

            // Search across all resources
            const results = {
                apps: infraSearchCache.apps.filter(app =>
                    app.name?.toLowerCase().includes(query) ||
                    app.type?.toLowerCase().includes(query)
                ),
                servers: infraSearchCache.servers.filter(server =>
                    server.name?.toLowerCase().includes(query) ||
                    server.host?.toLowerCase().includes(query)
                ),
                websites: infraSearchCache.websites.filter(site =>
                    site.name?.toLowerCase().includes(query) ||
                    site.url?.toLowerCase().includes(query)
                ),
                repos: infraSearchCache.repos.filter(repo =>
                    repo.name?.toLowerCase().includes(query) ||
                    repo.owner?.toLowerCase().includes(query)
                )
            };

            const totalResults = results.apps.length + results.servers.length +
                                results.websites.length + results.repos.length;

            if (totalResults === 0) {
                resultsDiv.innerHTML = '<div class="p-4 text-gray-500 text-sm">No results found</div>';
                resultsDiv.classList.remove('hidden');
                return;
            }

            let html = '<div class="p-2">';

            // Apps
            if (results.apps.length > 0) {
                html += '<div class="px-2 py-1 text-xs text-gray-500 uppercase tracking-wider">Applications</div>';
                results.apps.slice(0, 5).forEach(app => {
                    const statusColor = app.status === 'online' ? 'text-green-400' : 'text-red-400';
                    html += `
                        <div class="px-3 py-2 hover:bg-gray-700/50 rounded-lg cursor-pointer transition-colors" onclick="navigateToResource('apps', '${escapeHtml(app.name)}')">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-2">
                                    <i class="fas fa-cube text-purple-400"></i>
                                    <span class="text-sm text-gray-200">${escapeHtml(app.name)}</span>
                                </div>
                                <span class="text-xs ${statusColor}">${app.status || 'unknown'}</span>
                            </div>
                            ${app.type ? `<div class="ml-6 text-xs text-gray-500">${escapeHtml(app.type)}</div>` : ''}
                        </div>
                    `;
                });
                if (results.apps.length > 5) {
                    html += `<div class="px-3 py-1 text-xs text-gray-500">+${results.apps.length - 5} more apps</div>`;
                }
            }

            // Servers
            if (results.servers.length > 0) {
                html += '<div class="px-2 py-1 text-xs text-gray-500 uppercase tracking-wider mt-2">Servers</div>';
                results.servers.slice(0, 5).forEach(server => {
                    const statusColor = server.status === 'online' ? 'text-green-400' : 'text-red-400';
                    html += `
                        <div class="px-3 py-2 hover:bg-gray-700/50 rounded-lg cursor-pointer transition-colors" onclick="navigateToResource('servers', '${escapeHtml(server.name)}')">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-2">
                                    <i class="fas fa-server text-orange-400"></i>
                                    <span class="text-sm text-gray-200">${escapeHtml(server.name)}</span>
                                </div>
                                <span class="text-xs ${statusColor}">${server.status || 'unknown'}</span>
                            </div>
                            ${server.host ? `<div class="ml-6 text-xs text-gray-500">${escapeHtml(server.host)}</div>` : ''}
                        </div>
                    `;
                });
                if (results.servers.length > 5) {
                    html += `<div class="px-3 py-1 text-xs text-gray-500">+${results.servers.length - 5} more servers</div>`;
                }
            }

            // Websites
            if (results.websites.length > 0) {
                html += '<div class="px-2 py-1 text-xs text-gray-500 uppercase tracking-wider mt-2">Websites</div>';
                results.websites.slice(0, 5).forEach(site => {
                    const statusColor = site.status === 'online' ? 'text-green-400' : 'text-red-400';
                    html += `
                        <div class="px-3 py-2 hover:bg-gray-700/50 rounded-lg cursor-pointer transition-colors" onclick="navigateToResource('websites', '${escapeHtml(site.name)}')">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center space-x-2">
                                    <i class="fas fa-globe text-blue-400"></i>
                                    <span class="text-sm text-gray-200">${escapeHtml(site.name)}</span>
                                </div>
                                <span class="text-xs ${statusColor}">${site.status || 'unknown'}</span>
                            </div>
                            ${site.url ? `<div class="ml-6 text-xs text-gray-500">${escapeHtml(site.url)}</div>` : ''}
                        </div>
                    `;
                });
                if (results.websites.length > 5) {
                    html += `<div class="px-3 py-1 text-xs text-gray-500">+${results.websites.length - 5} more websites</div>`;
                }
            }

            // Repositories
            if (results.repos.length > 0) {
                html += '<div class="px-2 py-1 text-xs text-gray-500 uppercase tracking-wider mt-2">Repositories</div>';
                results.repos.slice(0, 5).forEach(repo => {
                    html += `
                        <div class="px-3 py-2 hover:bg-gray-700/50 rounded-lg cursor-pointer transition-colors" onclick="navigateToResource('repos', '${escapeHtml(repo.name)}')">
                            <div class="flex items-center space-x-2">
                                <i class="fab fa-github text-white"></i>
                                <span class="text-sm text-gray-200">${escapeHtml(repo.name)}</span>
                            </div>
                            ${repo.owner ? `<div class="ml-6 text-xs text-gray-500">${escapeHtml(repo.owner)}/${escapeHtml(repo.name)}</div>` : ''}
                        </div>
                    `;
                });
                if (results.repos.length > 5) {
                    html += `<div class="px-3 py-1 text-xs text-gray-500">+${results.repos.length - 5} more repos</div>`;
                }
            }

            html += '</div>';
            resultsDiv.innerHTML = html;
            resultsDiv.classList.remove('hidden');
        }

        // Navigate to resource when clicked in search
        function navigateToResource(section, resourceName) {
            // Close search
            document.getElementById('searchResults').classList.add('hidden');
            document.getElementById('globalSearch').value = '';

            // Navigate to section
            showSection(section);

            // Highlight the resource (optional - could scroll to it)
            setTimeout(() => {
                const resourceElements = document.querySelectorAll(`#section-${section} [data-name="${resourceName}"]`);
                if (resourceElements.length > 0) {
                    resourceElements[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }, 100);
        }

        // Close search when clicking outside
        document.addEventListener('click', (e) => {
            const searchBox = document.getElementById('globalSearch');
            const resultsDiv = document.getElementById('searchResults');
            if (searchBox && resultsDiv && !searchBox.contains(e.target) && !resultsDiv.contains(e.target)) {
                resultsDiv.classList.add('hidden');
            }
        });

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('globalSearch').focus();
            }
        });

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadConfigStatus();
            loadMonitoring();
            loadRecentActivityFeed();
            loadSecurityEvents();
            startSecurityEventStream();
            startRealtimeUpdates(); // Enabled real-time updates
            initHealthTrendChart();
            loadInfrastructureForSearch(); // Pre-load search data for instant search
        });

        let healthTrendChart = null;
        let healthDataPoints = [];

        function initHealthTrendChart() {
            const ctx = document.getElementById('healthTrendChart').getContext('2d');
            healthTrendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Uptime %',
                        data: [],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0, max: 100, ticks: { color: '#9ca3af', stepSize: 20 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { display: false }
                    }
                }
            });
        }

        function updateHealthTrend(online, total) {
            if (!healthTrendChart) return;
            
            const percent = total > 0 ? (online / total) * 100 : 100;
            const time = new Date().toLocaleTimeString();
            
            healthTrendChart.data.labels.push(time);
            healthTrendChart.data.datasets[0].data.push(percent);
            
            if (healthTrendChart.data.labels.length > 20) {
                healthTrendChart.data.labels.shift();
                healthTrendChart.data.datasets[0].data.shift();
            }
            
            healthTrendChart.update('none');
        }
