function saveOptions(e) {
  e.preventDefault();
  console.log("SAVE");
  browser.storage.sync.set({
    "api_url": document.querySelector("#api_url").value,
    "api_token": document.querySelector("#api_token").value
  });
}

function restoreOptions() {

  function setCurrentChoice(result) {
    document.querySelector("#api_url").value   = result.api_url   || "bluee1";
    document.querySelector("#api_token").value = result.api_token || "bluee2";
  }

  function onError(error) {
    console.log(`Error: ${error}`);
  }

  let getting = browser.storage.sync.get(["api_url", "api_token"]);
  getting.then(setCurrentChoice, onError);
}

document.addEventListener("DOMContentLoaded", restoreOptions);
document.querySelector("form").addEventListener("submit", saveOptions);
