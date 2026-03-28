function cleanUrl(form) {
    /* removes empty filter parameters from URL */
    for (var i = 0; i < form.elements.length; i++) {
        var input = form.elements[i];
        if (input.name && (!input.value || input.value === '')) {
            input.name = ''; 
        }
    }
}

function resetFilters(form) {
    /* clear all form inputs */
    form.querySelectorAll('select').forEach(select => {
        Array.from(select.options).forEach(option => {
            option.selected = false;
        });
    });
    
    form.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    form.querySelectorAll('input[type="radio"]').forEach(radio => {
        radio.checked = false;
    });

    cleanUrl(form)
    form.submit();
}

window.addEventListener('load', function() {
    const searchOptionsForm = document.getElementById('search-options-form');
    const clearFiltersButton = document.getElementById('clear-filters-button');

    searchOptionsForm.onsubmit = function() {
        cleanUrl(searchOptionsForm);
    };

    clearFiltersButton.onclick = function() {
        resetFilters(searchOptionsForm);
    };
});
