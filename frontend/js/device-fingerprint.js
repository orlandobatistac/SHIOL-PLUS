/**
 * Device Fingerprinting for Guest User Identification
 * Generates browser fingerprint data for verification limits system
 */

class DeviceFingerprinter {
    constructor() {
        this.fingerprintData = null;
        this.initializeFingerprint();
    }

    /**
     * Initialize and generate device fingerprint data
     */
    async initializeFingerprint() {
        try {
            this.fingerprintData = await this.generateFingerprintData();
            console.log('Device fingerprint generated:', Object.keys(this.fingerprintData));
        } catch (error) {
            console.warn('Error generating device fingerprint:', error);
            this.fingerprintData = this.getBasicFingerprintData();
        }
    }

    /**
     * Generate comprehensive device fingerprint data
     */
    async generateFingerprintData() {
        const data = {};

        // Screen resolution
        data.screen_resolution = `${screen.width}x${screen.height}`;

        // Timezone offset (minutes from UTC)
        data.timezone_offset = new Date().getTimezoneOffset();

        // Color depth
        data.color_depth = screen.colorDepth;

        // Platform information
        data.platform = navigator.platform;

        // Language
        data.language = navigator.language || navigator.languages[0];

        // Cookie enabled
        data.cookie_enabled = navigator.cookieEnabled;

        // Touch support
        data.touch_support = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

        // Hardware concurrency (CPU cores)
        data.hardware_concurrency = navigator.hardwareConcurrency;

        // Device memory (if available)
        if ('deviceMemory' in navigator) {
            data.device_memory = navigator.deviceMemory;
        }

        // Canvas fingerprint
        try {
            data.canvas_fingerprint = await this.generateCanvasFingerprint();
        } catch (error) {
            console.warn('Canvas fingerprinting failed:', error);
        }

        // WebGL fingerprint
        try {
            data.webgl_fingerprint = this.generateWebGLFingerprint();
        } catch (error) {
            console.warn('WebGL fingerprinting failed:', error);
        }

        return data;
    }

    /**
     * Generate canvas-based fingerprint
     */
    generateCanvasFingerprint() {
        return new Promise((resolve) => {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = 200;
                canvas.height = 50;
                const ctx = canvas.getContext('2d');

                // Draw text with different fonts and properties
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('Device Fingerprint 🔒', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Device Fingerprint 🔒', 4, 17);

                // Convert to hash
                const canvasData = canvas.toDataURL();
                const hash = this.simpleHash(canvasData);
                resolve(hash);
            } catch (error) {
                resolve(null);
            }
        });
    }

    /**
     * Generate WebGL-based fingerprint
     */
    generateWebGLFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            
            if (!gl) return null;

            // Get WebGL parameters safely
            const webglData = {
                vendor: this.safeGetParameter(gl, gl.VENDOR),
                renderer: this.safeGetParameter(gl, gl.RENDERER),
                version: this.safeGetParameter(gl, gl.VERSION),
                shadingLanguageVersion: this.safeGetParameter(gl, gl.SHADING_LANGUAGE_VERSION),
                maxTextureSize: this.safeGetParameter(gl, gl.MAX_TEXTURE_SIZE),
                maxViewportDims: this.safeGetParameter(gl, gl.MAX_VIEWPORT_DIMS)
            };

            return this.simpleHash(JSON.stringify(webglData));
        } catch (error) {
            console.warn('WebGL fingerprinting failed:', error);
            return null;
        }
    }

    /**
     * Safely get WebGL parameter
     */
    safeGetParameter(gl, parameter) {
        try {
            return gl.getParameter(parameter);
        } catch (error) {
            return null;
        }
    }

    /**
     * Simple hash function for fingerprint components
     */
    simpleHash(str) {
        let hash = 0;
        if (str.length === 0) return hash.toString();
        
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        
        return Math.abs(hash).toString(16);
    }

    /**
     * Get basic fingerprint data if full generation fails
     */
    getBasicFingerprintData() {
        return {
            screen_resolution: `${screen.width}x${screen.height}`,
            timezone_offset: new Date().getTimezoneOffset(),
            color_depth: screen.colorDepth,
            platform: navigator.platform,
            language: navigator.language,
            cookie_enabled: navigator.cookieEnabled,
            touch_support: 'ontouchstart' in window
        };
    }

    /**
     * Get the current fingerprint data
     */
    getFingerprintData() {
        return this.fingerprintData || this.getBasicFingerprintData();
    }

    /**
     * Check if fingerprint is ready
     */
    isReady() {
        return this.fingerprintData !== null;
    }

    /**
     * Wait for fingerprint to be ready
     */
    async waitUntilReady(timeout = 5000) {
        const startTime = Date.now();
        
        while (!this.isReady() && (Date.now() - startTime) < timeout) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        return this.isReady();
    }

    /**
     * Get fingerprint data as JSON string for HTTP headers
     */
    getFingerprintForHeader() {
        const data = this.getFingerprintData();
        try {
            return JSON.stringify(data);
        } catch (error) {
            console.warn('Error serializing fingerprint data:', error);
            return JSON.stringify(this.getBasicFingerprintData());
        }
    }
}

// Create global instance
const deviceFingerprinter = new DeviceFingerprinter();

// Attach to window for global access
window.deviceFingerprinter = deviceFingerprinter;

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DeviceFingerprinter, deviceFingerprinter };
}