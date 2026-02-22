document.addEventListener('DOMContentLoaded', function() {
    // Fade out flash messages after 4 seconds
    setTimeout(function() {
        document.querySelectorAll('.alert').forEach(function(el) {
            el.classList.add('fade');
            setTimeout(function() { el.remove(); }, 500);
        });
    }, 4000);
}); 