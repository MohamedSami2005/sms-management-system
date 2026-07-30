document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss alert banners after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Global Indian Mobile Number Validation (Blur Event)
    function validateIndianMobileNumber(val) {
        if (!val) return true;
        const clean = val.trim();
        // Indian mobile: optional +91 or 91 prefix, followed by 6, 7, 8, or 9 and 9 digits
        return /^(?:\+91|91)?[6789]\d{9}$/.test(clean);
    }

    function initMobileValidation(inputEl, isRequired = false) {
        if (!inputEl) return;

        let feedbackEl = inputEl.parentElement.querySelector('.invalid-feedback.mobile-validation-feedback');
        if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'invalid-feedback mobile-validation-feedback';
            feedbackEl.style.fontSize = '0.78rem';
            inputEl.parentElement.appendChild(feedbackEl);
        }

        function checkAndApplyValidation() {
            const rawVal = inputEl.value.trim();

            if (isRequired && !rawVal) {
                inputEl.classList.add('is-invalid');
                inputEl.classList.remove('is-valid');
                feedbackEl.innerText = 'Mobile number is required.';
                return false;
            }

            if (rawVal && !validateIndianMobileNumber(rawVal)) {
                inputEl.classList.add('is-invalid');
                inputEl.classList.remove('is-valid');
                feedbackEl.innerText = 'Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9 (e.g. 9876543210).';
                return false;
            }

            inputEl.classList.remove('is-invalid');
            feedbackEl.innerText = '';
            return true;
        }

        inputEl.addEventListener('blur', checkAndApplyValidation);

        // Immediate removal of error styling upon correction
        inputEl.addEventListener('input', function() {
            if (inputEl.classList.contains('is-invalid')) {
                checkAndApplyValidation();
            }
        });
    }

    // Auto-attach to all mobile number fields across CCMS
    const mobileFieldIDs = ['id_mobile_number', 'id_phone_number', 'mobileNumberInput'];
    mobileFieldIDs.forEach(function(id) {
        const el = document.getElementById(id);
        if (el) {
            const isReq = el.hasAttribute('required') || id === 'id_mobile_number';
            initMobileValidation(el, isReq);
        }
    });

    document.querySelectorAll('input[data-validate="mobile"]').forEach(function(el) {
        initMobileValidation(el, el.hasAttribute('required'));
    });
});
