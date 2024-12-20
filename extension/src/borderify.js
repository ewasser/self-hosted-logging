console.log("V2");

URL_API_URL = "";
URL_API_TOKEN = "";

entries = []

entries.push({
    'url': window.location.toString(),
    'timestamp_ms': Date.now()
});

document.body.style.border = "5px solid blue";

//console.log(entries);
json_data = { 'urls': entries };

/*
var request = new XMLHttpRequest();
request.open("POST", URL_STORAGE_SERVER);
request.setRequestHeader('Content-Type', 'application/json');
request.send(JSON.stringify(json_data));

// Defining event listener for readystatechange event
request.onreadystatechange = function() {
  // Check if the request is compete and was successful
  if(this.readyState === 4 && this.status === 200) {
  }
};
*/

// Example POST method implementation:
async function postData(url = '', token = null, data = {}) {

  headers = new Headers({
    'Content-Type': 'application/json',
  });

  if (token) {
    headers.set('Authorization', token);
  }

  // Default options are marked with *
  const response = await fetch(url, {
    method: 'POST', // *GET, POST, PUT, DELETE, etc.
    mode: 'cors', // no-cors, *cors, same-origin
    cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
    credentials: 'same-origin', // include, *same-origin, omit
    headers: headers,
    redirect: 'follow', // manual, *follow, error
    referrerPolicy: 'no-referrer', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
    body: JSON.stringify(data) // body data type must match "Content-Type" header
  });
  return response.json(); // parses JSON response into native JavaScript objects
}

function onError(error) {
    console.log(`Error: ${error}`);
}

function onGot(item) {
    console.log(item);

    URL_API_URL = item.api_url;
    URL_API_TOKEN = item.api_token;

    if (URL_API_URL) {
        postData(URL_API_URL, URL_API_TOKEN, json_data)
          .then(data => {
            //console.log(data); // JSON data parsed by `data.json()` call
          });
    }
}

let getting = browser.storage.sync.get(["api_url", "api_token"]);
getting.then(onGot, onError);


//browser.idle.onStateChanged.addEventListener('change', () => {
//  console.log("idle");
//  console.log(detector.userState); // idle | active
//  console.log(detector.screenState); // locked | unlocked
//});

