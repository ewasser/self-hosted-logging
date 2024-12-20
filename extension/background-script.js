////////////////////////////////////////////////////////////////////////

MAX_ENTRIES = 1000;

// These are my 3 configuration values
API_URL = "";
API_TOKEN = "";
URLS = [];

////////////////////////////////////////////////////////////////////////

VISITED_URLS = []

////////////////////////////////////////////////////////////////////////

function generateFilter() {
    return {
      "urls": URLS
    };
}

function loadConfiguration() {

  function a(result) {

    return new Promise(function(resolve, reject) {

      API_URL = result.api_url   || "";
      API_TOKEN = result.api_token || "";
      URLS = [];

      urls_string = result.urls || "";

      urls_string.split(/\r?\n/).forEach(function(s) {
          if (s.length >= 1) {
              URLS.push(s);
          }
      });
      resolve();
    });
  }

  let getting = browser.storage.sync.get(["api_url", "api_token", "urls"]);

  return getting.then(result => a(result));
}


function update_for_tab(tabId, changeInfo, tabInfo) {
//  console.log(`Updated tab: ${tabId}`);
//  console.log("Changed attributes: ", changeInfo);
//  console.log("New tab Info: ", tabInfo);

  if (tabInfo.status == 'complete')
  {
    var timestamp_ms = Date.now()

    var getting = browser.tabs.get(tabId).then(tab => {
        VISITED_URLS.push({
          "url": tab.url,
          "timestamp_ms": timestamp_ms,
          "title": tab.title,
        });
    });
  }
}

function configurationChanged() {
    browser.tabs.onUpdated.removeListener(update_for_tab);

    loadConfiguration().then(() => {
        if (URLS.length >= 1) {
            console.log("Hau rein");
            browser.tabs.onUpdated.addListener(update_for_tab, generateFilter());
        }
    });
}

function notify(message) {
  if (message['type'] == 'configurationChanged')
  {
    configurationChanged();
  }
}

function cleanup_buffer() {
    if (VISITED_URLS.length > MAX_ENTRIES) {
        VISITED_URLS.splice(0, VISITED_URLS.length-MAX_ENTRIES);
    }
}

async function fetchWithTimeout(resource, options = {}) {
  const { timeout = 8000 } = options;
  
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  const response = await fetch(resource, {
    ...options,
    signal: controller.signal
  });
  clearTimeout(id);
  return response;
}

async function postData(url = '', token = null, data = {}) {

    headers = new Headers({
      'Content-Type': 'application/json',
    });

    if (token) {
      headers.set('Authorization', 'Bearer ' + token);
    }

    try {
      const response = await fetchWithTimeout(url, {
        timeout: 6000,
        // Default options are marked with *
        method: 'POST', // *GET, POST, PUT, DELETE, etc.
        mode: 'cors', // no-cors, *cors, same-origin
        cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
        credentials: 'same-origin', // include, *same-origin, omit
        headers: headers,
        redirect: 'follow', // manual, *follow, error
        referrerPolicy: 'no-referrer', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
        body: JSON.stringify(data) // body data type must match "Content-Type" header
      });
      const answer = await response.json();
      cleanup_buffer();
      return answer;
    } catch (error) {
      // Timeouts if the request takes
      // longer than 6 seconds
      console.log(error.name === 'AbortError');
      cleanup_buffer();
    }

}

function send_urls() {
    json_data = { 'hits': VISITED_URLS };

    postData(API_URL, API_TOKEN, json_data)
      .then(data => {
        VISITED_URLS = [];
      });
}

function save_urls()
{
    console.log("#CAUGHT_URLS = " + VISITED_URLS.length + ", API_URL = " + API_URL + ", API_TOKEN = " + API_TOKEN + ", #WHITELISTED_URLS = " + URLS.length);
    console.log(URLS);

    if (VISITED_URLS.length == 0) {
        return;
    }

    if (API_URL) {
        send_urls();
    }

}

configurationChanged();

browser.runtime.onMessage.addListener(notify);

var intervalID = setInterval(save_urls, 10000);

