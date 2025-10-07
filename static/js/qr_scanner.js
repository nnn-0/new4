let video;
let canvas;
let canvasContext;
let scanning = false;
let userLocation = null;

document.addEventListener('DOMContentLoaded', function() {
    video = document.getElementById('video');
    canvas = document.getElementById('canvas');
    canvasContext = canvas.getContext('2d');
    
    const startButton = document.getElementById('start-camera');
    const stopButton = document.getElementById('stop-camera');
    
    startButton.addEventListener('click', startCamera);
    stopButton.addEventListener('click', stopCamera);
    
    // Request location permission when page loads
    requestLocation();
});

function requestLocation() {
    if (navigator.geolocation) {
        updateScanStatus('Getting your location...', 'info');
        
        navigator.geolocation.getCurrentPosition(
            function(position) {
                userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                
                // Verify location with server
                verifyLocation(userLocation.latitude, userLocation.longitude);
            },
            function(error) {
                updateScanStatus('Location access denied. Please enable location services.', 'error');
                console.error('Location error:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    } else {
        updateScanStatus('Location services not supported by this browser.', 'error');
    }
}

function verifyLocation(latitude, longitude) {
    fetch('/api/verify_location', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            latitude: latitude,
            longitude: longitude
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.allowed) {
            updateScanStatus(`Location verified at ${data.college_name}. You may scan QR codes.`, 'success');
            document.getElementById('start-camera').disabled = false;
        } else {
            updateScanStatus(`Location verification failed: ${data.message}`, 'error');
            document.getElementById('start-camera').disabled = true;
        }
    })
    .catch(error => {
        console.error('Location verification error:', error);
        updateScanStatus('Location verification failed. Please try again.', 'error');
        document.getElementById('start-camera').disabled = true;
    });
}

function startCamera() {
    if (!userLocation) {
        alert('Please allow location access to scan QR codes.');
        requestLocation();
        return;
    }
    
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        .then(function(stream) {
            video.srcObject = stream;
            video.play();
            scanning = true;
            
            document.getElementById('start-camera').style.display = 'none';
            document.getElementById('stop-camera').style.display = 'inline-block';
            
            updateScanStatus('Camera started. Position QR code in view.', 'info');
            requestAnimationFrame(scanQRCode);
        })
        .catch(function(error) {
            console.error('Camera error:', error);
            updateScanStatus('Camera access denied or not available.', 'error');
        });
}

function stopCamera() {
    scanning = false;
    if (video.srcObject) {
        let tracks = video.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        video.srcObject = null;
    }
    
    document.getElementById('start-camera').style.display = 'inline-block';
    document.getElementById('stop-camera').style.display = 'none';
    
    updateScanStatus('Camera stopped.', 'info');
}

function scanQRCode() {
    if (!scanning) return;
    
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const imageData = canvasContext.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height);
        
        if (code) {
            updateScanStatus('QR Code detected! Processing...', 'success');
            processQRCode(code.data);
            return;
        }
    }
    
    requestAnimationFrame(scanQRCode);
}

function processQRCode(codeData) {
    // Verify location again before processing
    if (!userLocation) {
        showResult('Location verification required', 'Please refresh and allow location access.', 'error');
        return;
    }
    
    // Send QR code data to server for verification
    fetch('/scan_qr', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `qr_code=${encodeURIComponent(codeData)}&latitude=${userLocation.latitude}&longitude=${userLocation.longitude}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showResult('Attendance Marked!', data.message, 'success');
        } else {
            showResult('Attendance Failed', data.message, 'error');
        }
        stopCamera();
    })
    .catch(error => {
        console.error('QR processing error:', error);
        showResult('Processing Error', 'Failed to process QR code. Please try again.', 'error');
        stopCamera();
    });
}

function verifyManualCode() {
    const manualCode = document.getElementById('manual-code').value.trim();
    
    if (!manualCode) {
        alert('Please enter a QR code');
        return;
    }
    
    if (!userLocation) {
        alert('Please allow location access to mark attendance.');
        requestLocation();
        return;
    }
    
    updateScanStatus('Verifying manual code...', 'info');
    processQRCode(manualCode);
}

function updateScanStatus(message, type) {
    const statusElement = document.getElementById('scan-status');
    let className = 'text-muted';
    
    switch(type) {
        case 'success':
            className = 'text-success';
            break;
        case 'error':
            className = 'text-danger';
            break;
        case 'info':
            className = 'text-info';
            break;
    }
    
    statusElement.innerHTML = `<p class="${className}"><strong>${message}</strong></p>`;
}

function showResult(title, message, type) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = `
        <div class="alert alert-${type === 'success' ? 'success' : 'danger'}" role="alert">
            ${message}
        </div>
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('resultModal'));
    modal.show();
}

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (document.hidden && scanning) {
        stopCamera();
    }
});