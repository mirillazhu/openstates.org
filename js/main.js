import "../static/styles/app.scss";

// polyfills (IE 11)
import "url-search-params-polyfill";
import "promise-polyfill/src/polyfill";
import "whatwg-fetch";

function addBanner(content) {
  var div = document.createElement("div");
  div.className = "notification-banner";
  div.appendChild(document.createTextNode(content));
  document.querySelector("body header").appendChild(div);
}

function handleStateSelect() {
  var stateSelect = document.getElementById('state-select');
    if (stateSelect) {
        stateSelect.addEventListener('change', function() {
            window.location.href = '/' + this.value;
        });
    }
}

document.addEventListener("DOMContentLoaded", handleStateSelect)

function checkIE() {
  var ua = window.navigator.userAgent;
  if (ua.indexOf("MSIE") > 0 || ua.indexOf("Trident/") > 0) {
    document.querySelector(".header__logo").src =
      "/static/images/openstates_ce_logo.png";
    addBanner(
      "You are viewing this site in an outdated browser, some features may not work."
    );
  }
}

window.addEventListener("load", checkIE);

function reloadPage(event) {
  // reload entire page if the page is loaded from back button
  const navEntry = performance.getEntriesByType("navigation")[0];
  if (event.persisted || (navEntry && navEntry.type === "back_forward")) {
    window.location.reload();
  }
}

window.addEventListener("pageshow", reloadPage);
