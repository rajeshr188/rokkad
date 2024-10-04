var width = 320;
var height = 0;
var streaming = false;
var video = null;
var canvas = null;
var photo = null;
var startbutton = null;
var imageDataInput = null;
var mediaStream = null;
var videoSelect = null;

function initializeCamera(deviceId) {
  video = document.getElementById('video');
  canvas = document.getElementById('canvas');
  photo = document.getElementById('photo');
  startbutton = document.getElementById('startbutton');
  imageDataInput = document.getElementById('image-data');
  videoSelect = document.getElementById('videoSource');
  if (!video || !canvas || !photo || !startbutton || !imageDataInput || !videoSelect) {
    console.error("One or more required HTML elements are missing.");
    return;
  }

  const constraints = {
    video: { deviceId: deviceId ? { exact: deviceId } : undefined },
    audio: false
  };

  navigator.mediaDevices.getUserMedia(constraints)
    .then(function(stream) {
      if (mediaStream) {
        stopCamera(); // Stop the previous stream if it exists
      }
      mediaStream = stream;
      video.srcObject = stream;
      video.onloadedmetadata = function() {
        video.play().catch(function(err) {
          console.log("An error occurred while trying to play the video: " + err);
        });
      };
    })
    .catch(function(err) {
      console.log("An error occurred: " + err);
    });

  video.addEventListener('canplay', function(ev){
    if (!streaming) {
      height = video.videoHeight / (video.videoWidth / width);
      if (isNaN(height)) {
        height = width / (4 / 3);
      }
      video.setAttribute('width', width);
      video.setAttribute('height', height);
      canvas.setAttribute('width', width);
      canvas.setAttribute('height', height);
      streaming = true;
    }
  }, false);

  startbutton.addEventListener('click', function(ev){
    takepicture();
    ev.preventDefault();
  }, false);

  clearphoto();
}

function clearphoto() {
  var context = canvas.getContext('2d');
  context.fillStyle = "#AAA";
  context.fillRect(0, 0, canvas.width, canvas.height);

  var data = canvas.toDataURL('image/png');
  photo.setAttribute('src', data);
  imageDataInput.value = data;
}

function takepicture() {
  var context = canvas.getContext('2d');
  if (width && height) {
    canvas.width = width;
    canvas.height = height;
    context.drawImage(video, 0, 0, width, height);

    var data = canvas.toDataURL('image/png');
    photo.setAttribute('src', data);
    imageDataInput.value = data;
  } else {
    clearphoto();
  }
}

function startup() {
  // Initialize camera and other stuff
  initializeCamera();
  // List available video input devices
  navigator.mediaDevices.enumerateDevices()
    .then(function(devices) {
      devices.forEach(function(device) {
        if (device.kind === 'videoinput') {
          var option = document.createElement('option');
          option.value = device.deviceId;
          option.text = device.label || `Camera ${videoSelect.length + 1}`;
          videoSelect.appendChild(option);
        }
      });
    })
    .catch(function(err) {
      console.log("An error occurred: " + err);
    });

  videoSelect.onchange = function() {
    initializeCamera(videoSelect.value);
  };
}

// Function to stop the camera stream and release resources
function stopCamera() {
  if (mediaStream) {
    const tracks = mediaStream.getTracks();
    tracks.forEach(track => track.stop());
    mediaStream = null; // Reset mediaStream variable after stopping the stream
  }
}

// document.addEventListener('DOMContentLoaded', function() {
//   // On initial page load and htmx load
//   document.addEventListener('htmx:load', startup);
//   // On htmx page transition
//   document.addEventListener('htmx:afterSwap', stopCamera);
// });
// Ensure the DOM is fully loaded before running the script
document.addEventListener('DOMContentLoaded', function() {
  // On initial page load
  document.addEventListener('htmx:load', startup);
  // On htmx page transition
  document.addEventListener('htmx:afterSwap', function() {
    stopCamera();
    startup();
  });
});

