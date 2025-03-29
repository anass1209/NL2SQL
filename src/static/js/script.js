// script.js - Enhanced frontend interactivity
document.addEventListener('DOMContentLoaded', () => {
    // Cache DOM elements
    const settingsBtn = document.getElementById('settings-btn');
    const modal = document.getElementById('api-key-modal');
    const closeBtn = modal?.querySelector('.close-btn');
    const apiKeyForm = document.getElementById('api-key-form');
    const geminiKeyInput = document.getElementById('gemini-api-key');
    const validateBtn = document.getElementById('validate-key-btn');
    const validationStatus = document.getElementById('validation-status');
    
    document.querySelector('.container').classList.add('fade-in');
    
    // Handle textarea auto-resize
    const queryTextarea = document.querySelector('textarea[name="query"]');
    if (queryTextarea) {
        queryTextarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        
        // Focus the textarea when page loads
        setTimeout(() => {
            queryTextarea.focus();
        }, 500);
    }

    // --- Modal Control ---
    if (settingsBtn && modal) {
        settingsBtn.addEventListener('click', () => {
            // Animate modal opening
            document.body.style.overflow = 'hidden'; // Prevent scrolling
            modal.style.display = 'block';
            
            // Reset form state
            if (geminiKeyInput && validationStatus) {
                geminiKeyInput.value = ''; 
                validationStatus.textContent = '';
                validationStatus.className = 'validation-message';
            }
        });
    }

    if (closeBtn && modal) {
        closeBtn.addEventListener('click', () => {
            closeModal();
        });
    }

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });
    
    // Add Escape key support for modal
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && modal.style.display === 'block') {
            closeModal();
        }
    });

    function closeModal() {
        if (!modal) return;
        
        // Add closing animation
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.classList.add('modal-closing');
            
            // Wait for animation before hiding
            setTimeout(() => {
                modal.style.display = 'none';
                document.body.style.overflow = 'auto'; // Restore scrolling
                modalContent.classList.remove('modal-closing');
            }, 200);
        } else {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    }

    // --- API Key Validation ---
    if (validateBtn && geminiKeyInput && validationStatus) {
        validateBtn.addEventListener('click', async () => {
            const geminiKey = geminiKeyInput.value.trim();
            
            // Validate input
            if (!geminiKey) {
                validationStatus.textContent = 'Please enter a Google API Key.';
                validationStatus.className = 'validation-message invalid';
                // Shake the input to indicate error
                geminiKeyInput.classList.add('shake');
                setTimeout(() => {
                    geminiKeyInput.classList.remove('shake');
                }, 500);
                return;
            }

            // Update UI for validation in progress
            validationStatus.textContent = 'Validating...';
            validationStatus.className = 'validation-message validating';
            validateBtn.disabled = true;
            validateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            try {
                const response = await fetch('/validate-api-key', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ gemini_api_key: geminiKey }),
                });

                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }

                const result = await response.json();

                // Update validation status with result
                validationStatus.textContent = result.message;
                validationStatus.className = result.valid 
                    ? 'validation-message valid' 
                    : 'validation-message invalid';
                
                // Add subtle indication animation
                validationStatus.classList.add('bounce');
                setTimeout(() => {
                    validationStatus.classList.remove('bounce');
                }, 500);

            } catch (error) {
                console.error("Validation error:", error);
                validationStatus.textContent = 'Validation request failed. Check console.';
                validationStatus.className = 'validation-message invalid';
            } finally {
                validateBtn.disabled = false;
                validateBtn.innerHTML = 'Validate';
            }
        });
    }

    // --- API Key Saving ---
    if (apiKeyForm && validationStatus) {
        apiKeyForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const geminiKey = geminiKeyInput?.value.trim() || '';
            
            // Validate before saving
            if (!geminiKey) {
                validationStatus.textContent = 'Google API Key is required to save.';
                validationStatus.className = 'validation-message invalid';
                return;
            }

            // Update UI for saving in progress
            const submitBtn = apiKeyForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            
            validationStatus.textContent = 'Saving your API key...';
            validationStatus.className = 'validation-message validating';

            try {
                const response = await fetch('/save-api-keys', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        gemini_api_key: geminiKey
                    }),
                });

                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }

                const result = await response.json();

                if (result.success) {
                    validationStatus.textContent = result.message;
                    validationStatus.className = 'validation-message valid';
                    
                    // Show success animation
                    submitBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
                    
                    // Close modal after delay
                    setTimeout(() => {
                        closeModal();
                    }, 1500);
                } else {
                    validationStatus.textContent = `Error: ${result.message}`;
                    validationStatus.className = 'validation-message invalid';
                    submitBtn.innerHTML = originalBtnText;
                    submitBtn.disabled = false;
                }

            } catch (error) {
                console.error("Save keys error:", error);
                validationStatus.textContent = 'Failed to save keys. Server error.';
                validationStatus.className = 'validation-message invalid';
                submitBtn.innerHTML = originalBtnText;
                submitBtn.disabled = false;
            }
        });
    }
    
    // Add animation classes for CSS transitions
    const style = document.createElement('style');
    style.textContent = `
        .fade-in {
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .shake {
            animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both;
        }
        
        @keyframes shake {
            10%, 90% { transform: translateX(-1px); }
            20%, 80% { transform: translateX(2px); }
            30%, 50%, 70% { transform: translateX(-4px); }
            40%, 60% { transform: translateX(4px); }
        }
        
        .bounce {
            animation: bounce 0.5s;
        }
        
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        
        .modal-closing {
            animation: modalFadeOut 0.2s;
        }
        
        @keyframes modalFadeOut {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(-20px); }
        }
    `;
    document.head.appendChild(style);
});