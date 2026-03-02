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
    stopCamera(); // Stop the previous stream before switching to a new one
    initializeCamera(videoSelect.value);// Initialize the new camera stream
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

// modular
// Camera configuration object
// const CONFIG = {
//     width: 320,
//     height: 0,
//     aspectRatio: 4/3,
//     imageFormat: 'image/png',
//     defaultFillStyle: '#AAA'
// };

// // DOM Elements cache
// const DOM = {
//     elements: {},
//     requiredIds: ['video', 'canvas', 'photo', 'startbutton', 'image-data', 'videoSource'],
    
//     init() {
//         this.requiredIds.forEach(id => {
//             this.elements[id] = document.getElementById(id);
//         });
//         return this.validateElements();
//     },
    
//     validateElements() {
//         const missingElements = this.requiredIds.filter(id => !this.elements[id]);
//         if (missingElements.length) {
//             console.error('Missing required elements:', missingElements);
//             return false;
//         }
//         return true;
//     }
// };

// class CameraManager {
//     constructor() {
//         this.streaming = false;
//         this.mediaStream = null;
//         this.height = CONFIG.height;
//     }

//     async initializeCamera(deviceId = null) {
//         if (!DOM.elements.video) return;

//         const constraints = {
//             video: deviceId ? { deviceId: { exact: deviceId } } : true,
//             audio: false
//         };

//         try {
//             await this.stopCamera();
//             this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
//             DOM.elements.video.srcObject = this.mediaStream;
//             await this.playVideo();
//         } catch (error) {
//             console.error('Camera initialization failed:', error);
//         }
//     }

//     async playVideo() {
//         try {
//             await DOM.elements.video.play();
//             this.setupVideoEventListeners();
//         } catch (error) {
//             console.error('Video playback failed:', error);
//         }
//     }

//     setupVideoEventListeners() {
//         DOM.elements.video.addEventListener('canplay', () => {
//             if (!this.streaming) {
//                 this.calculateDimensions();
//                 this.setElementDimensions();
//                 this.streaming = true;
//             }
//         });
//     }

//     calculateDimensions() {
//         this.height = DOM.elements.video.videoHeight / 
//                      (DOM.elements.video.videoWidth / CONFIG.width);
        
//         if (isNaN(this.height)) {
//             this.height = CONFIG.width / CONFIG.aspectRatio;
//         }
//     }

//     setElementDimensions() {
//         const dimensions = { width: CONFIG.width, height: this.height };
//         ['video', 'canvas'].forEach(element => {
//             Object.entries(dimensions).forEach(([prop, value]) => {
//                 DOM.elements[element].setAttribute(prop, value);
//             });
//         });
//     }

//     async stopCamera() {
//         if (this.mediaStream) {
//             this.mediaStream.getTracks().forEach(track => track.stop());
//             this.mediaStream = null;
//         }
//     }
// }

// class PhotoCapture {
//     constructor() {
//         this.canvas = DOM.elements.canvas;
//         this.photo = DOM.elements.photo;
//         this.imageDataInput = DOM.elements.imageDataInput;
//     }

//     clearPhoto() {
//         const context = this.canvas.getContext('2d');
//         context.fillStyle = CONFIG.defaultFillStyle;
//         context.fillRect(0, 0, this.canvas.width, this.canvas.height);
//         this.updatePhotoData();
//     }

//     takePhoto() {
//         const context = this.canvas.getContext('2d');
//         if (CONFIG.width && DOM.elements.video) {
//             this.canvas.width = CONFIG.width;
//             this.canvas.height = CONFIG.height;
//             context.drawImage(DOM.elements.video, 0, 0, CONFIG.width, CONFIG.height);
//             this.updatePhotoData();
//         } else {
//             this.clearPhoto();
//         }
//     }

//     updatePhotoData() {
//         const data = this.canvas.toDataURL(CONFIG.imageFormat);
//         this.photo.setAttribute('src', data);
//         this.imageDataInput.value = data;
//     }
// }

// class DeviceManager {
//     static async populateVideoDevices() {
//         try {
//             const devices = await navigator.mediaDevices.enumerateDevices();
//             const videoDevices = devices.filter(device => device.kind === 'videoinput');
            
//             DOM.elements.videoSource.innerHTML = ''; // Clear existing options
//             videoDevices.forEach((device, index) => {
//                 const option = document.createElement('option');
//                 option.value = device.deviceId;
//                 option.text = device.label || `Camera ${index + 1}`;
//                 DOM.elements.videoSource.appendChild(option);
//             });
//         } catch (error) {
//             console.error('Failed to enumerate devices:', error);
//         }
//     }
// }

// // Application initialization
// const initializeApp = () => {
//     if (!DOM.init()) return;

//     const cameraManager = new CameraManager();
//     const photoCapture = new PhotoCapture();

//     // Initialize camera and populate device list
//     DeviceManager.populateVideoDevices();
//     cameraManager.initializeCamera();

//     // Event Listeners
//     DOM.elements.startbutton.addEventListener('click', (e) => {
//         e.preventDefault();
//         photoCapture.takePhoto();
//     });

//     DOM.elements.videoSource.addEventListener('change', () => {
//         cameraManager.initializeCamera(DOM.elements.videoSource.value);
//     });

//     // Clear initial photo
//     photoCapture.clearPhoto();
// };

// // HTMX integration
// document.addEventListener('DOMContentLoaded', () => {
//     document.addEventListener('htmx:load', initializeApp);
//     document.addEventListener('htmx:afterSwap', () => {
//         const cameraManager = new CameraManager();
//         cameraManager.stopCamera().then(initializeApp);
//     });
// });