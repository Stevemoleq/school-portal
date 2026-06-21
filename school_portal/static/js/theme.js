// Sidebar Mobile Toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.toggle('-translate-x-full');
    if (overlay) overlay.classList.toggle('hidden');
    document.body.classList.toggle('sidebar-open');
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.add('-translate-x-full');
    if (overlay) overlay.classList.add('hidden');
    document.body.classList.remove('sidebar-open');
}

// Dark Mode
function toggleDarkMode() {
    const html = document.documentElement;
    html.classList.toggle('dark');
    const isDark = html.classList.contains('dark');
    localStorage.setItem('darkMode', isDark ? 'true' : 'false');
    const icon = document.getElementById('darkModeIcon');
    if (icon) {
        icon.className = isDark ? 'fas fa-sun text-yellow-400 text-sm' : 'fas fa-moon text-surface-500 text-sm';
    }
}

// Restore dark mode
(function() {
    const stored = localStorage.getItem('darkMode');
    if (stored === 'true' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
        const icon = document.getElementById('darkModeIcon');
        if (icon) icon.className = 'fas fa-sun text-yellow-400 text-sm';
    }
})();

// User Menu
function toggleUserMenu() {
    const menu = document.getElementById('userMenu');
    if (!menu) return;
    menu.classList.toggle('hidden');
}

document.addEventListener('click', function(e) {
    const menu = document.getElementById('userMenu');
    const userRow = e.target.closest('.sidebar-user-info');
    if (menu && !menu.classList.contains('hidden') && !userRow) {
        menu.classList.add('hidden');
    }
});

// Notifications Dropdown
function toggleNotifications() {
    const dropdown = document.getElementById('notificationDropdown');
    if (!dropdown) return;
    dropdown.classList.toggle('hidden');
    const btn = document.querySelector('[onclick*="toggleNotifications"]');
    if (btn) btn.setAttribute('aria-expanded', !dropdown.classList.contains('hidden'));
}

document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('notificationDropdown');
    if (dropdown && !dropdown.contains(e.target) && !e.target.closest('[onclick*="toggleNotifications"]')) {
        dropdown.classList.add('hidden');
    }
});

// Auto-dismiss toasts
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[role="alert"]').forEach(function(toast, i) {
        setTimeout(function() {
            if (!toast.parentElement) return;
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(function() { if (toast.parentElement) toast.remove(); }, 300);
        }, 4000 + i * 500);
    });
});
