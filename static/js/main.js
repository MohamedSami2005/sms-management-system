document.addEventListener('DOMContentLoaded', function () {
    // 1. Auto-dismiss alert banners after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // 2. Universal Debounced Auto-Search & Instant Filter across all CCMS modules
    const filterForms = document.querySelectorAll('form[method="get"], .filter-toolbar form');

    filterForms.forEach(function (form) {
        const textInputs = form.querySelectorAll('input[type="text"], input[type="search"]');
        const selectInputs = form.querySelectorAll('select');
        const dateInputs = form.querySelectorAll('input[type="date"]');

        // Focus & Cursor Position Restoration after Auto-Submit Page Reload
        const activeInputName = sessionStorage.getItem('ccms_active_search_input');
        if (activeInputName) {
            const targetInput = form.querySelector(`input[name="${activeInputName}"]`);
            if (targetInput) {
                targetInput.focus();
                const valLen = targetInput.value.length;
                try {
                    targetInput.setSelectionRange(valLen, valLen);
                } catch (e) {
                    // Fallback for non-supporting input types
                }
            }
            sessionStorage.removeItem('ccms_active_search_input');
        }

        // Debounced text search input handler (400ms)
        textInputs.forEach(function (input) {
            let debounceTimer = null;

            input.addEventListener('input', function () {
                if (debounceTimer) clearTimeout(debounceTimer);
                sessionStorage.setItem('ccms_active_search_input', input.name);

                debounceTimer = setTimeout(function () {
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                }, 400); // 400ms debounce
            });
        });

        // Instant submit on dropdown filter change
        selectInputs.forEach(function (select) {
            // Avoid duplicate submission if inline onchange attribute is present
            if (!select.getAttribute('onchange')) {
                select.addEventListener('change', function () {
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                });
            }
        });

        // Instant submit on date filter change
        dateInputs.forEach(function (dateInput) {
            dateInput.addEventListener('change', function () {
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        });
    });
});
