/**
 * WebAuthn (Biometric Authentication) JavaScript Utilities
 * Handles fingerprint registration, authentication, and attendance marking
 */

class WebAuthnManager {
    constructor() {
        this.isSupported = this.checkSupport();
        this.inFlight = false; // Prevent concurrent WebAuthn operations
        this.setupEventListeners();
    }

    /**
     * Check if WebAuthn is supported by the browser
     */
    checkSupport() {
        if (!window.PublicKeyCredential) {
            console.log('WebAuthn not supported');
            return false;
        }
        return true;
    }

    /**
     * Check if platform authenticator (biometrics) is available
     */
    async checkBiometricSupport() {
        if (!this.isSupported) return false;
        
        try {
            const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
            return available;
        } catch (error) {
            console.error('Error checking biometric support:', error);
            return false;
        }
    }

    /**
     * Clear pending operation state and error messages
     */
    clearPendingState() {
        this.inFlight = false;
        
        // Clear existing error messages
        const existingAlerts = document.querySelectorAll('.alert-danger');
        existingAlerts.forEach(alert => alert.remove());
    }

    /**
     * Setup event listeners for biometric buttons
     */
    setupEventListeners() {
        // Biometric registration button
        const registerBtn = document.getElementById('biometric-register-btn');
        if (registerBtn) {
            registerBtn.addEventListener('click', () => this.registerBiometric());
        }

        // Biometric login button
        const loginBtn = document.getElementById('biometric-login-btn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => this.authenticateBiometric());
        }

        // Biometric attendance button
        const attendanceBtn = document.getElementById('biometric-attendance-btn');
        if (attendanceBtn) {
            // Prevent rapid double-clicking
            let lastClickTime = 0;
            attendanceBtn.addEventListener('click', (event) => {
                const now = Date.now();
                if (now - lastClickTime < 2000) { // Prevent clicks within 2 seconds
                    console.log('Ignoring rapid click - attendance in progress');
                    event.preventDefault();
                    event.stopPropagation();
                    return;
                }
                lastClickTime = now;
                this.markAttendanceWithBiometric();
            });
        }

        // Faculty biometric registration button (for admin during registration)
        const facultyRegisterBtn = document.getElementById('faculty-biometric-register-btn');
        if (facultyRegisterBtn) {
            facultyRegisterBtn.addEventListener('click', () => this.registerBiometricForNewFaculty());
        }
    }

    /**
     * Convert ArrayBuffer to base64url string (compatible with server)
     */
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    }

    /**
     * Convert base64url string to ArrayBuffer (compatible with server)
     */
    base64ToArrayBuffer(base64) {
        // Add padding if necessary
        const padding = '='.repeat((4 - base64.length % 4) % 4);
        const paddedBase64 = base64.replace(/-/g, '+').replace(/_/g, '/') + padding;
        const binary = atob(paddedBase64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    /**
     * Show loading state for biometric operations
     */
    showBiometricLoading(element, message = 'Please use your fingerprint...') {
        if (element) {
            element.innerHTML = `<i class="fas fa-fingerprint me-2"></i>${message}`;
            element.disabled = true;
        }
    }

    /**
     * Hide loading state for biometric operations
     */
    hideBiometricLoading(element, originalText) {
        if (element) {
            element.innerHTML = originalText;
            element.disabled = false;
        }
    }

    /**
     * Register biometric credential for a user
     */
    async registerBiometric() {
        // Clear any existing pending flags and error messages
        this.clearPendingState();
        
        const registerBtn = document.getElementById('biometric-register-btn');
        const originalText = registerBtn?.innerHTML || '';
        
        try {
            this.inFlight = true;
            
            // Check biometric support
            const supported = await this.checkBiometricSupport();
            if (!supported) {
                throw new Error('Biometric authentication is not available on this device');
            }

            this.showBiometricLoading(registerBtn, 'Preparing biometric registration...');

            // Get registration options from server with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch('/api/webauthn/register/begin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to get registration options');
            }

            const options = await response.json();

            // Convert base64 strings to ArrayBuffers
            options.challenge = this.base64ToArrayBuffer(options.challenge);
            options.user.id = this.base64ToArrayBuffer(options.user.id);

            this.showBiometricLoading(registerBtn, 'Please use your fingerprint...');

            // Create credential using WebAuthn with shorter timeout
            const credential = await Promise.race([
                navigator.credentials.create({
                    publicKey: {
                        ...options,
                        authenticatorSelection: {
                            authenticatorAttachment: 'platform', // Use built-in biometrics
                            userVerification: 'required' // Require fingerprint/biometric
                        },
                        timeout: 60000 // 60 seconds for user interaction
                    }
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Biometric registration timeout - please try again')), 65000)
                )
            ]);

            this.showBiometricLoading(registerBtn, 'Verifying biometric...');

            // Send credential to server for storage
            const registrationResponse = await fetch('/api/webauthn/register/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    id: credential.id,
                    rawId: this.arrayBufferToBase64(credential.rawId),
                    response: {
                        attestationObject: this.arrayBufferToBase64(credential.response.attestationObject),
                        clientDataJSON: this.arrayBufferToBase64(credential.response.clientDataJSON)
                    },
                    type: credential.type,
                    opId: options.opId  // Include operation ID from server
                })
            });

            if (!registrationResponse.ok) {
                const errorData = await registrationResponse.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to register biometric credential');
            }

            const result = await registrationResponse.json();
            
            // Store credential ID for future use
            localStorage.setItem('biometric_credential_id', credential.id);
            
            // Show success message
            this.showSuccess('Biometric registration successful! You can now use fingerprint to login and mark attendance.');
            
            // Update UI to show biometric is registered
            this.updateBiometricStatus(true);

        } catch (error) {
            console.error('Biometric registration failed:', error);
            if (error.name === 'AbortError') {
                this.showError('Registration cancelled or timed out. Please try again.');
            } else if (error.name === 'NotAllowedError') {
                this.showError('Biometric access denied. Please allow biometric access and try again.');
            } else {
                this.showError(`Biometric registration failed: ${error.message}`);
            }
        } finally {
            // Always clear the pending state
            this.clearPendingState();
            this.hideBiometricLoading(registerBtn, originalText);
        }
    }

    /**
     * Authenticate user with biometric
     */
    async authenticateBiometric() {
        // Clear any existing pending flags and error messages
        this.clearPendingState();
        
        const loginBtn = document.getElementById('biometric-login-btn');
        const originalText = loginBtn?.innerHTML || '';
        
        try {
            this.inFlight = true;
            
            const supported = await this.checkBiometricSupport();
            if (!supported) {
                throw new Error('Biometric authentication is not available on this device');
            }

            this.showBiometricLoading(loginBtn, 'Preparing biometric login...');

            // Get authentication options from server - include username if available
            const usernameField = document.getElementById('username') || document.querySelector('input[name="username"]');
            const username = usernameField ? usernameField.value.trim() : '';
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);
            
            const response = await fetch('/api/webauthn/authenticate/begin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username: username }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to get authentication options');
            }

            const options = await response.json();

            // Convert base64 strings to ArrayBuffers
            options.challenge = this.base64ToArrayBuffer(options.challenge);
            if (options.allowCredentials) {
                options.allowCredentials = options.allowCredentials.map(cred => ({
                    ...cred,
                    id: this.base64ToArrayBuffer(cred.id)
                }));
            }

            this.showBiometricLoading(loginBtn, 'Please use your fingerprint...');

            // Authenticate using WebAuthn with timeout
            const assertion = await Promise.race([
                navigator.credentials.get({
                    publicKey: {
                        ...options,
                        userVerification: 'required',
                        timeout: 60000
                    }
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Biometric authentication timeout - please try again')), 65000)
                )
            ]);

            this.showBiometricLoading(loginBtn, 'Verifying fingerprint...');

            // Send assertion to server for verification
            const authResponse = await fetch('/api/webauthn/authenticate/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    id: assertion.id,
                    rawId: this.arrayBufferToBase64(assertion.rawId),
                    response: {
                        authenticatorData: this.arrayBufferToBase64(assertion.response.authenticatorData),
                        clientDataJSON: this.arrayBufferToBase64(assertion.response.clientDataJSON),
                        signature: this.arrayBufferToBase64(assertion.response.signature)
                    },
                    type: assertion.type,
                    opId: options.opId  // Include operation ID from server
                })
            });

            if (!authResponse.ok) {
                const errorData = await authResponse.json().catch(() => ({}));
                throw new Error(errorData.error || 'Biometric authentication failed');
            }

            const result = await authResponse.json();
            
            // Redirect to dashboard on successful authentication
            if (result.success) {
                window.location.href = result.redirect || '/dashboard';
            } else {
                throw new Error(result.error || 'Authentication failed');
            }

        } catch (error) {
            console.error('Biometric authentication failed:', error);
            if (error.name === 'AbortError') {
                this.showError('Authentication cancelled or timed out. Please try again.');
            } else if (error.name === 'NotAllowedError') {
                this.showError('Biometric access denied. Please allow biometric access and try again.');
            } else {
                this.showError(`Biometric login failed: ${error.message}`);
            }
        } finally {
            // Always clear the pending state
            this.clearPendingState();
            this.hideBiometricLoading(loginBtn, originalText);
        }
    }

    /**
     * Mark attendance using biometric authentication
     */
    async markAttendanceWithBiometric() {
        // CRITICAL: Prevent any duplicate requests with lock
        if (this._attendanceLock) {
            console.log('Attendance marking already in progress, blocking duplicate');
            return;
        }
        
        this._attendanceLock = true;
        
        const attendanceBtn = document.getElementById('biometric-attendance-btn');
        const originalText = attendanceBtn?.innerHTML || '';
        
        // Immediately disable button to prevent multiple clicks
        if (attendanceBtn) {
            attendanceBtn.disabled = true;
            attendanceBtn.style.pointerEvents = 'none';
        }
        
        try {
            
            const supported = await this.checkBiometricSupport();
            if (!supported) {
                throw new Error('Biometric authentication is not available on this device');
            }

            this.showBiometricLoading(attendanceBtn, 'Preparing biometric verification...');

            // STEP 1: Get authentication options from the new atomic endpoint
            const optionsResponse = await fetch('/api/webauthn/attendance/mark', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({}) // Empty body to get options
            });

            if (!optionsResponse.ok) {
                const errorData = await optionsResponse.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to get attendance options');
            }

            const options = await optionsResponse.json();

            // Convert base64 strings to ArrayBuffers
            options.challenge = this.base64ToArrayBuffer(options.challenge);
            if (options.allowCredentials) {
                options.allowCredentials = options.allowCredentials.map(cred => ({
                    ...cred,
                    id: this.base64ToArrayBuffer(cred.id)
                }));
            }

            this.showBiometricLoading(attendanceBtn, 'Please use your fingerprint...');

            // STEP 2: Authenticate using WebAuthn
            console.log('About to call navigator.credentials.get with options:', options);
            console.log('navigator.credentials available:', !!navigator.credentials);
            console.log('PublicKeyCredential available:', typeof PublicKeyCredential !== 'undefined');
            
            const assertion = await Promise.race([
                navigator.credentials.get({
                    publicKey: {
                        ...options,
                        userVerification: 'required',
                        timeout: 300000
                    }
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Biometric verification timeout - please try again')), 310000)
                )
            ]);
            
            console.log('WebAuthn assertion received:', assertion);

            this.showBiometricLoading(attendanceBtn, 'Taking photo...');

            // STEP 3: Capture photo
            const photo = await this.capturePhoto();

            this.showBiometricLoading(attendanceBtn, 'Marking attendance...');

            // STEP 4: Send EVERYTHING to the atomic endpoint in ONE request
            const attendanceResponse = await fetch('/api/webauthn/attendance/mark', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    assertion: {
                        id: assertion.id,
                        rawId: this.arrayBufferToBase64(assertion.rawId),
                        response: {
                            authenticatorData: this.arrayBufferToBase64(assertion.response.authenticatorData),
                            clientDataJSON: this.arrayBufferToBase64(assertion.response.clientDataJSON),
                            signature: this.arrayBufferToBase64(assertion.response.signature)
                        },
                        type: assertion.type,
                        opId: options.opId
                    },
                    photo: photo
                })
            });

            if (!attendanceResponse.ok) {
                const errorData = await attendanceResponse.json().catch(() => ({}));
                throw new Error(errorData.error || 'Failed to mark attendance');
            }

            const result = await attendanceResponse.json();
            
            if (result.success) {
                this.showSuccess(`Attendance marked successfully! Session: ${result.session}`);
                // Refresh the page to update attendance status
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                throw new Error(result.error || 'Failed to mark attendance');
            }

        } catch (error) {
            console.error('Biometric attendance failed:', error);
            console.error('Error name:', error.name);
            console.error('Error message:', error.message);
            console.error('Error stack:', error.stack);
            
            if (error.name === 'AbortError') {
                this.showError('Attendance marking cancelled or timed out. Please try again.');
            } else if (error.name === 'NotAllowedError') {
                this.showError('Biometric access denied. Please allow biometric access and try again.');
            } else if (error.message) {
                this.showError(`Biometric attendance failed: ${error.message}`);
            } else {
                this.showError('Biometric authentication failed. Please ensure your device supports fingerprint authentication and try again.');
            }
        } finally {
            // Release the lock
            this._attendanceLock = false;
            
            this.hideBiometricLoading(attendanceBtn, originalText);
            
            // Re-enable button after a short delay
            setTimeout(() => {
                if (attendanceBtn) {
                    attendanceBtn.disabled = false;
                    attendanceBtn.style.pointerEvents = 'auto';
                }
            }, 1000);
        }
    }

    /**
     * Capture photo using device camera
     */
    async capturePhoto() {
        return new Promise((resolve, reject) => {
            const video = document.createElement('video');
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');

            navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => {
                    video.srcObject = stream;
                    video.play();

                    video.onloadedmetadata = () => {
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        
                        // Capture frame after 1 second
                        setTimeout(() => {
                            context.drawImage(video, 0, 0);
                            const photoData = canvas.toDataURL('image/jpeg', 0.8);
                            
                            // Stop the camera
                            stream.getTracks().forEach(track => track.stop());
                            
                            resolve(photoData);
                        }, 1000);
                    };
                })
                .catch(error => {
                    console.error('Camera access failed:', error);
                    reject(new Error('Camera access failed'));
                });
        });
    }

    /**
     * Update UI to show biometric registration status
     */
    updateBiometricStatus(isRegistered) {
        const statusElement = document.getElementById('biometric-status');
        const registerBtn = document.getElementById('biometric-register-btn');
        
        if (statusElement) {
            if (isRegistered) {
                statusElement.innerHTML = '<i class="fas fa-check-circle text-success me-2"></i>Biometric registered';
                statusElement.className = 'alert alert-success';
            } else {
                statusElement.innerHTML = '<i class="fas fa-exclamation-circle text-warning me-2"></i>Biometric not registered';
                statusElement.className = 'alert alert-warning';
            }
        }

        if (registerBtn && isRegistered) {
            registerBtn.style.display = 'none';
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('main.container').insertBefore(alertDiv, document.querySelector('main.container').firstChild);
    }

    /**
     * Show error message
     */
    showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('main.container').insertBefore(alertDiv, document.querySelector('main.container').firstChild);
    }

    /**
     * Register biometric for new faculty during admin registration process
     * This is only a scheduling mechanism - actual registration happens after user creation
     */
    async registerBiometricForNewFaculty() {
        const registerBtn = document.getElementById('faculty-biometric-register-btn');
        const originalText = registerBtn?.innerHTML || '';
        
        try {
            // Check biometric support
            const supported = await this.checkBiometricSupport();
            if (!supported) {
                throw new Error('Biometric authentication is not available on this device');
            }

            // Check if required form fields are filled
            const username = document.getElementById('username')?.value;
            const fullName = document.getElementById('full_name')?.value;
            const email = document.getElementById('email')?.value;
            
            if (!username || !fullName || !email) {
                throw new Error('Please fill in the username, full name, and email fields first');
            }

            this.showBiometricLoading(registerBtn, 'Scheduling biometric registration...');

            // Store intent to register biometric after user creation
            const hiddenField = document.getElementById('biometric-credential-data');
            if (hiddenField) {
                hiddenField.value = 'schedule_biometric_registration';
            }

            // Mark as scheduled but not completed
            const statusElement = document.getElementById('biometric-status');
            if (statusElement) {
                statusElement.innerHTML = '<i class="fas fa-clock text-info me-2"></i>Biometric registration scheduled';
                statusElement.className = 'alert alert-info';
            }

            this.showSuccess('Biometric registration scheduled! The faculty member will be prompted to register their fingerprint after account creation.');

            // Hide the registration button since it's now scheduled
            if (registerBtn) {
                registerBtn.style.display = 'none';
            }

        } catch (error) {
            console.error('Faculty biometric registration failed:', error);
            this.showError(`Error: Failed to complete biometric registration`);
        } finally {
            this.hideBiometricLoading(registerBtn, originalText);
        }
    }

    /**
     * Initialize biometric UI on page load
     */
    async init() {
        const supported = await this.checkBiometricSupport();
        
        // Show/hide biometric options based on support
        const biometricElements = document.querySelectorAll('.biometric-option');
        biometricElements.forEach(element => {
            if (supported) {
                element.style.display = 'block';
            } else {
                element.style.display = 'none';
            }
        });

        // Check if user already has biometric registered
        const credentialId = localStorage.getItem('biometric_credential_id');
        if (credentialId) {
            this.updateBiometricStatus(true);
        }
    }
}

// Initialize WebAuthn manager when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.webauthnManager = new WebAuthnManager();
    window.webauthnManager.init();
});