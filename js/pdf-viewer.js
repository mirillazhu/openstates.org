const VIEWER_URL = '/static/pdfjs/web/viewer.html';

window.addEventListener('load', function() {
    const pdfUrl = window.PDF_URL;
    const iframe = document.getElementById('pdf-viewer');
    const errorState = document.getElementById('error-state');
    const errorMessage = document.getElementById('error-message');

    function showError(message) {
        iframe.style.display = 'none';
        errorState.style.display = 'block';
        errorMessage.textContent = message;
    }

    async function loadPDF() {
        try {

            // check if PDF is accessible -- change for DB solution
            const pdfResponse = await fetch(pdfUrl, { method: 'HEAD' });
            if (!pdfResponse.ok) {
                throw new Error('This PDF is unavailable or may no longer exist.');
            }
            
            // check if viewer is accessible
            const viewerResponse = await fetch(VIEWER_URL, { method: 'HEAD' });
            if (!viewerResponse.ok) {
                throw new Error('The PDF viewer failed to load.');
            }
            
            // load viewer with PDF
            iframe.src = `${VIEWER_URL}?file=${encodeURIComponent(pdfUrl)}`;
        
            // catch any errors from iframe
            iframe.addEventListener('error', () => {
                showError('The PDF viewer failed to load.'); 
            });

            // to do: what if a specific page fails to load? 
            
        } catch (error) {
            showError(error.message);
        }
    }

    loadPDF();
});



