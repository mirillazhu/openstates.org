function toggleSponsors(toggle, cells) {
    var expanded = toggle.getAttribute('data-expanded') === 'true';
    
    for (var i = 18; i < cells.length; i++) {
        cells[i].style.display = expanded ? 'none' : '';
    }
    
    toggle.setAttribute('data-expanded', expanded ? 'false' : 'true');
    toggle.textContent = expanded ? '+ More' : '- Less';
}

window.addEventListener('load', function() {
    var grid = document.getElementById('sponsors-grid');
    var cells = grid.getElementsByClassName('cell');
    var toggle = document.getElementById('sponsors-toggle');

    toggle.onclick = function() {
        toggleSponsors(toggle, cells);
    };
});