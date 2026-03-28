window.addEventListener('load', function() {
    const imageViewer    = document.getElementById('image-viewer');
    const zoomOutBtn     = document.getElementById('zoom-out');
    const zoomLevelEl    = document.getElementById('zoom-level');
    const zoomInBtn      = document.getElementById('zoom-in');
    const initialLoading = document.getElementById('initial-loading');
    const pagesWrapper   = document.getElementById('pages-wrapper');
    const errorState     = document.getElementById('error-state');
    const errorMessage   = document.getElementById('error-message');

    let pages          = [];
    let pageWrappers   = [];
    let zoomLevel      = 75;
    const ZOOM_STEP    = 25;
    const ZOOM_MIN     = 50;
    const ZOOM_MAX     = 300;

    function showError(message) {
        imageViewer.style.display = 'none';
        errorState.style.display  = 'block';
        errorMessage.textContent  = message;
    }

    // page zoom

    function applyZoom() {
        const widthPct = `${zoomLevel}%`;
        for (const wrapper of pageWrappers) {
            wrapper.style.width = widthPct;
        }

        // align center if zoom is \leq 100, otherwise left to allow for horizontal scrolling
        pagesWrapper.style.alignItems = (zoomLevel <= 100 ? 'center' : 'flex-start')  

        zoomLevelEl.textContent = `${zoomLevel}%`;
        zoomInBtn.disabled  = zoomLevel >= ZOOM_MAX;
        zoomOutBtn.disabled = zoomLevel <= ZOOM_MIN;
    }

    zoomInBtn.addEventListener('click', () => {
        if (zoomLevel < ZOOM_MAX) {
            zoomLevel += ZOOM_STEP;
            applyZoom();
        }
    });

    zoomOutBtn.addEventListener('click', () => {
        if (zoomLevel > ZOOM_MIN) {
            zoomLevel -= ZOOM_STEP;
            applyZoom();
        }
    });

    // build pages

    function buildPages() {
        pagesWrapper.innerHTML = '';
        pageWrappers = [];

        pages.forEach((url, index) => {
            const pageNum = index + 1;

            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.setAttribute('data-page', pageNum);
            wrapper.style.width = `${zoomLevel}%`;

            const placeholder = document.createElement('div');
            placeholder.className = 'page-placeholder';
            placeholder.innerHTML = '<img src="/static/pdfjs/web/images/loading.svg" class="loading-spinner"/>';
            wrapper.appendChild(placeholder);

            const img = document.createElement('img');
            img.alt = `Page ${pageNum}`;
            img.style.display = 'none';

            img.onload = () => {
                if (placeholder.parentNode === wrapper) {
                    wrapper.removeChild(placeholder);
                }
                img.style.display = 'block';
            };

            img.onerror = () => {
                placeholder.innerHTML =
                    `<p class="page-error-msg">Page ${pageNum} could not be loaded.</p>`;
            };

            img.src = url;
            wrapper.appendChild(img);

            pagesWrapper.appendChild(wrapper);
            pageWrappers.push(wrapper);
        });

        pagesWrapper.style.display = 'flex';
        
    }

    // initialize viewer

    function initViewer(data) {
        if (!data.success || !data.images || !data.images.length) {
            showError(data.message || '');
            return;
        }
        pages = data.images;
        buildPages();
        applyZoom();
        initialLoading.style.display = 'none';
    }

    imageViewer.style.display = 'flex';

    initViewer({
        success: true, 
        images: [ 
            '/static/test-images/image-0000.webp',
            '/static/test-images/image-0001.webp',
            '/static/test-images/image-0002.webp',
            '/static/test-images/image-0003.webp',
            '/static/test-images/image-0004.webp',
        ] 
    }); 
});
