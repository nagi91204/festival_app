const button = document.getElementById("display-fullscreen-toggle")
button.addEventListener("click", openFullscreen);

function openFullscreen() {

  const elem = document.documentElement; // Requests fullscreen for the whole page
  if (elem.requestFullscreen) {
    elem.requestFullscreen();
  } else if (elem.webkitRequestFullscreen) { /* Safari / Older Chrome */
    elem.webkitRequestFullscreen();
  } else if (elem.msRequestFullscreen) { /* IE11 / Edge */
      elem.msRequestFullscreen();
  }

  button.hidden = true
}
