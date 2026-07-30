document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss alert banners after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Sidebar active link highlighter and expansion logic
    const currentPath = window.location.pathname;
    const currentSearch = window.location.search;
    const currentUrl = currentPath + currentSearch;

    const sidebarLinks = document.querySelectorAll('#sidebar-wrapper a.nav-link-main, #sidebar-wrapper a.sub-link');
    let matchedLink = null;

    // 1. First pass: try exact match including query params
    sidebarLinks.forEach(link => {
        const linkUrl = link.getAttribute('href');
        if (linkUrl && currentUrl === linkUrl) {
            matchedLink = link;
        }
    });

    // 2. Second pass: fallback to pathname matching only (excluding query params)
    if (!matchedLink) {
        sidebarLinks.forEach(link => {
            const linkUrl = link.getAttribute('href');
            if (linkUrl) {
                const pathOnly = linkUrl.split('?')[0];
                if (pathOnly === currentPath) {
                    matchedLink = link;
                }
            }
        });
    }

    if (matchedLink) {
        // Clear active class from all navigation links
        sidebarLinks.forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to the matched link
        matchedLink.classList.add('active');

        // Handle collapsible parent submenus
        const parentCollapse = matchedLink.closest('.collapse');
        if (parentCollapse) {
            parentCollapse.classList.add('show');
            const triggerId = parentCollapse.getAttribute('id');
            const triggerBtn = document.querySelector(`[aria-controls="${triggerId}"]`);
            if (triggerBtn) {
                triggerBtn.setAttribute('aria-expanded', 'true');
                triggerBtn.classList.add('active');
            }
        }
    }
});
