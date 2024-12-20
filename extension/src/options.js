// We need 2 points where we transfer the configuration
// into our `background-script.js`.
//
// 1. The configuration was retrieved from the browser storage.
// 2. The configuration was saved in the preferences of the plugin.
function saveOptions(e) {
  e.preventDefault();

  api_url = document.querySelector("#api_url").value;
  api_token = document.querySelector("#api_token").value;
  urls = document.querySelector("#urls").value;

  browser.storage.sync.set({
    "api_url": api_url,
    "api_token": api_token,
    "urls": urls,
  });

  browser.runtime.sendMessage({"type": "configurationChanged"});
}

function restoreOptions() {

  function setCurrentChoice(result) {

    api_url = result.api_url   || "";
    api_token = result.api_token || "";
    urls = result.urls || "";

    document.querySelector("#api_url").value   = api_url;
    document.querySelector("#api_token").value = api_token;
    document.querySelector("#urls").value      = urls;
  }

  function onError(error) {
    console.log(`Error: ${error}`);
  }

  let getting = browser.storage.sync.get(["api_url", "api_token", "urls"]);
  getting.then(setCurrentChoice, onError);
}

document.addEventListener("DOMContentLoaded", restoreOptions);
document.querySelector("form").addEventListener("submit", saveOptions);

