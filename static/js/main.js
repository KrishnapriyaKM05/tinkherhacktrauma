/**
 * static/js/main.js
 * =================
 * Global JavaScript utilities for CogMemory.
 * Keeps this file minimal — page-specific logic is in curve.js.
 */

// Highlight selected radio option in quiz
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('.option-label').forEach(function (label) {
        const input = label.querySelector('input[type="radio"]');
        if (input) {
            input.addEventListener('change', function () {
                // Remove highlight from siblings
                const name = this.name;
                document.querySelectorAll(`input[name="${name}"]`).forEach(function (r) {
                    r.closest('.option-label').classList.remove('selected');
                });
                label.classList.add('selected');
            });
        }
    });
});
