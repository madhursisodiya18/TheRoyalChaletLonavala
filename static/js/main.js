/**
 * Royal Chalet - Main JavaScript Utilities
 * A comprehensive collection of utility functions for enhanced UI/UX
 */

// Initialize on DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize AOS (Animate On Scroll)
    if (window.AOS) {
        AOS.init();
    }

    // Initialize all components
    initThemeToggle();
    initMobileMenu();
    initLoadingSpinner();
    initFormValidation();
    initTooltips();
    initModals();
    initTabSwitching();
    initQuantitySelectors();
    initImageGallery();
    initSmoothScrolling();
    initDatePickers();
    initPriceCalculator();
});

/**
 * Theme Toggle Functionality
 * Handles dark/light mode switching with localStorage persistence
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');
    
    // Check if button is in dark mode from localStorage
    const isDarkMode = localStorage.getItem('buttonDarkMode') === 'true';
    
    // Set initial button state
    if (isDarkMode) {
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    } else {
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    }
    
    // Toggle button appearance only
    themeToggle.addEventListener('click', function() {
        // Toggle icons
        sunIcon.classList.toggle('hidden');
        moonIcon.classList.toggle('hidden');
        
        // Store button state
        const currentIsDark = sunIcon.classList.contains('hidden');
        localStorage.setItem('buttonDarkMode', currentIsDark);
    });
}

/**
 * Mobile Menu Functionality
 * Handles the mobile hamburger menu toggle and outside click detection
 */
function initMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (!mobileMenuButton || !mobileMenu) return;
    
    mobileMenuButton.addEventListener('click', () => {
        mobileMenu.classList.toggle('hidden');
        mobileMenuButton.classList.toggle('hamburger-active');
    });
    
    // Close mobile menu when clicking outside
    document.addEventListener('click', (event) => {
        if (mobileMenu.classList.contains('hidden')) return;
        if (!mobileMenu.contains(event.target) && !mobileMenuButton.contains(event.target)) {
            mobileMenu.classList.add('hidden');
            mobileMenuButton.classList.remove('hamburger-active');
        }
    });
}

/**
 * Loading Spinner Functionality
 * Provides global methods to show/hide loading spinner during async operations
 */
function initLoadingSpinner() {
    // Create loading spinner if it doesn't exist
    if (!document.getElementById('loading-spinner')) {
        const spinner = document.createElement('div');
        spinner.id = 'loading-spinner';
        spinner.className = 'loading-container';
        spinner.innerHTML = '<div class="loading-spinner"></div>';
        document.body.appendChild(spinner);
    }
    
    // Global methods for showing/hiding spinner
    window.showLoading = function() {
        document.getElementById('loading-spinner').classList.add('active');
    };
    
    window.hideLoading = function() {
        document.getElementById('loading-spinner').classList.remove('active');
    };
    
    // Automatically show loading on form submissions
    document.querySelectorAll('form:not([data-no-loading])').forEach(form => {
        form.addEventListener('submit', function() {
            if (this.checkValidity()) {
                window.showLoading();
            }
        });
    });
    
    // Hide loading spinner when page is fully loaded
    window.addEventListener('load', function() {
        window.hideLoading();
    });
}

/**
 * Form Validation Functionality
 * Enhances form validation with custom styling and feedback
 */
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
        // Add validation styling to inputs
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            // Skip hidden inputs
            if (input.type === 'hidden') return;
            
            // Add blur event for real-time validation
            input.addEventListener('blur', function() {
                validateInput(this);
            });
            
            // Add input event for real-time validation on typing
            input.addEventListener('input', function() {
                if (this.dataset.validateRealtime === 'true') {
                    validateInput(this);
                }
            });
        });
        
        // Validate form on submit
        form.addEventListener('submit', function(e) {
            let isValid = true;
            
            inputs.forEach(input => {
                if (!validateInput(input)) {
                    isValid = false;
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                // Scroll to first invalid input
                const firstInvalid = form.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
        });
    });
    
    // Input validation function
    function validateInput(input) {
        // Skip disabled inputs
        if (input.disabled) return true;
        
        let isValid = input.checkValidity();
        
        // Custom validation rules
        if (input.dataset.validateEmail === 'true' && input.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            isValid = emailRegex.test(input.value);
        }
        
        if (input.dataset.validateMatch) {
            const matchInput = document.getElementById(input.dataset.validateMatch);
            if (matchInput && input.value !== matchInput.value) {
                isValid = false;
            }
        }
        
        // Update input styling
        if (isValid) {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            
            // Clear error message
            const errorElement = input.parentElement.querySelector('.error-message');
            if (errorElement) {
                errorElement.textContent = '';
            }
        } else {
            input.classList.remove('is-valid');
            input.classList.add('is-invalid');
            
            // Show error message
            let errorMessage = input.dataset.errorMessage || 'Please enter a valid value';
            
            // Get specific error message based on validation type
            if (input.validity.valueMissing) {
                errorMessage = input.dataset.errorRequired || 'This field is required';
            } else if (input.validity.typeMismatch) {
                errorMessage = input.dataset.errorType || 'Please enter a valid format';
            } else if (input.validity.tooShort) {
                errorMessage = input.dataset.errorMinLength || `Minimum length is ${input.minLength} characters`;
            } else if (input.validity.tooLong) {
                errorMessage = input.dataset.errorMaxLength || `Maximum length is ${input.maxLength} characters`;
            } else if (input.dataset.validateMatch && input.dataset.errorMatch) {
                errorMessage = input.dataset.errorMatch;
            }
            
            // Create or update error message element
            let errorElement = input.parentElement.querySelector('.error-message');
            if (!errorElement) {
                errorElement = document.createElement('div');
                errorElement.className = 'error-message text-red-500 text-xs mt-1';
                input.parentElement.appendChild(errorElement);
            }
            errorElement.textContent = errorMessage;
        }
        
        return isValid;
    }
}

/**
 * Tooltip Functionality
 * Initializes tooltips for elements with data-tooltip attribute
 */
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        const tooltipText = element.dataset.tooltip;
        const tooltipPosition = element.dataset.tooltipPosition || 'top';
        
        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = `tooltip tooltip-${tooltipPosition} absolute bg-gray-800 text-white text-xs rounded py-1 px-2 opacity-0 transition-opacity duration-300 pointer-events-none z-50`;
        tooltip.textContent = tooltipText;
        
        // Add tooltip to document body
        document.body.appendChild(tooltip);
        
        // Show tooltip on hover/focus
        function showTooltip() {
            const rect = element.getBoundingClientRect();
            const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            // Position tooltip based on specified position
            switch (tooltipPosition) {
                case 'top':
                    tooltip.style.top = `${rect.top + scrollTop - tooltip.offsetHeight - 5}px`;
                    tooltip.style.left = `${rect.left + scrollLeft + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
                    break;
                case 'bottom':
                    tooltip.style.top = `${rect.bottom + scrollTop + 5}px`;
                    tooltip.style.left = `${rect.left + scrollLeft + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
                    break;
                case 'left':
                    tooltip.style.top = `${rect.top + scrollTop + (rect.height / 2) - (tooltip.offsetHeight / 2)}px`;
                    tooltip.style.left = `${rect.left + scrollLeft - tooltip.offsetWidth - 5}px`;
                    break;
                case 'right':
                    tooltip.style.top = `${rect.top + scrollTop + (rect.height / 2) - (tooltip.offsetHeight / 2)}px`;
                    tooltip.style.left = `${rect.right + scrollLeft + 5}px`;
                    break;
            }
            
            tooltip.classList.add('opacity-100');
        }
        
        function hideTooltip() {
            tooltip.classList.remove('opacity-100');
        }
        
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('focus', showTooltip);
        element.addEventListener('blur', hideTooltip);
    });
}

/**
 * Modal Functionality
 * Handles opening/closing modals and backdrop management
 */
function initModals() {
    // Modal triggers
    const modalTriggers = document.querySelectorAll('[data-modal-target]');
    
    modalTriggers.forEach(trigger => {
        const modalId = trigger.dataset.modalTarget;
        const modal = document.getElementById(modalId);
        
        if (!modal) return;
        
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            openModal(modal);
        });
    });
    
    // Close buttons
    const closeButtons = document.querySelectorAll('[data-modal-close]');
    
    closeButtons.forEach(button => {
        const modal = button.closest('.modal');
        
        if (!modal) return;
        
        button.addEventListener('click', () => {
            closeModal(modal);
        });
    });
    
    // Close on backdrop click
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-backdrop')) {
            const modal = e.target.querySelector('.modal-content');
            if (modal && !modal.dataset.noBackdropClose) {
                closeModal(e.target);
            }
        }
    });
    
    // Close on ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal-backdrop:not(.hidden)');
            if (openModal) {
                const modalContent = openModal.querySelector('.modal-content');
                if (modalContent && !modalContent.dataset.noEscClose) {
                    closeModal(openModal);
                }
            }
        }
    });
    
    // Modal open function
    window.openModal = function(modal) {
        if (typeof modal === 'string') {
            modal = document.getElementById(modal);
        }
        
        if (!modal) return;
        
        modal.classList.remove('hidden');
        document.body.classList.add('overflow-hidden');
        
        // Focus first focusable element
        setTimeout(() => {
            const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (focusable.length) {
                focusable[0].focus();
            }
        }, 100);
    };
    
    // Modal close function
    window.closeModal = function(modal) {
        if (typeof modal === 'string') {
            modal = document.getElementById(modal);
        }
        
        if (!modal) return;
        
        modal.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
    };
}

/**
 * Tab Switching Functionality
 * Handles tab navigation for tabbed interfaces
 */
function initTabSwitching() {
    const tabContainers = document.querySelectorAll('[data-tabs]');
    
    tabContainers.forEach(container => {
        const tabs = container.querySelectorAll('[data-tab]');
        const tabContents = document.querySelectorAll(`[data-tab-content="${container.dataset.tabs}"]`);
        
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.dataset.tab;
                
                // Update active tab
                tabs.forEach(t => {
                    if (t.dataset.tab === tabId) {
                        t.classList.add('active-tab');
                        t.setAttribute('aria-selected', 'true');
                    } else {
                        t.classList.remove('active-tab');
                        t.setAttribute('aria-selected', 'false');
                    }
                });
                
                // Show active content
                tabContents.forEach(content => {
                    if (content.dataset.tabId === tabId) {
                        content.classList.remove('hidden');
                    } else {
                        content.classList.add('hidden');
                    }
                });
                
                // Update URL hash if enabled
                if (container.dataset.tabsUpdateHash === 'true') {
                    window.location.hash = tabId;
                }
            });
        });
        
        // Initialize from URL hash if enabled
        if (container.dataset.tabsUpdateHash === 'true' && window.location.hash) {
            const tabId = window.location.hash.substring(1);
            const tab = container.querySelector(`[data-tab="${tabId}"]`);
            if (tab) {
                tab.click();
            }
        }
    });
}

/**
 * Quantity Selector Functionality
 * Handles increment/decrement controls for quantity inputs
 */
function initQuantitySelectors() {
    const quantitySelectors = document.querySelectorAll('.quantity-selector');
    
    quantitySelectors.forEach(selector => {
        const input = selector.querySelector('input[type="number"]');
        const decrementBtn = selector.querySelector('.quantity-decrement');
        const incrementBtn = selector.querySelector('.quantity-increment');
        
        if (!input || !decrementBtn || !incrementBtn) return;
        
        const min = parseInt(input.getAttribute('min')) || 0;
        const max = parseInt(input.getAttribute('max')) || Infinity;
        const step = parseInt(input.getAttribute('step')) || 1;
        
        decrementBtn.addEventListener('click', () => {
            const currentValue = parseInt(input.value) || 0;
            const newValue = Math.max(min, currentValue - step);
            input.value = newValue;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateButtonStates();
        });
        
        incrementBtn.addEventListener('click', () => {
            const currentValue = parseInt(input.value) || 0;
            const newValue = Math.min(max, currentValue + step);
            input.value = newValue;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateButtonStates();
        });
        
        input.addEventListener('change', updateButtonStates);
        
        function updateButtonStates() {
            const currentValue = parseInt(input.value) || 0;
            decrementBtn.disabled = currentValue <= min;
            incrementBtn.disabled = currentValue >= max;
            
            if (decrementBtn.disabled) {
                decrementBtn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                decrementBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
            
            if (incrementBtn.disabled) {
                incrementBtn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                incrementBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
        
        // Initialize button states
        updateButtonStates();
    });
}

/**
 * Image Gallery Functionality
 * Handles lightbox and image navigation for galleries
 */
function initImageGallery() {
    const galleries = document.querySelectorAll('[data-gallery]');
    
    galleries.forEach(gallery => {
        const galleryItems = gallery.querySelectorAll('[data-gallery-item]');
        
        galleryItems.forEach(item => {
            item.addEventListener('click', () => {
                const imageUrl = item.dataset.galleryItem;
                const imageTitle = item.dataset.galleryTitle || '';
                
                openLightbox(imageUrl, imageTitle, galleryItems, item);
            });
        });
    });
    
    function openLightbox(imageUrl, imageTitle, galleryItems, currentItem) {
        // Create lightbox if it doesn't exist
        let lightbox = document.getElementById('gallery-lightbox');
        
        if (!lightbox) {
            lightbox = document.createElement('div');
            lightbox.id = 'gallery-lightbox';
            lightbox.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-90 hidden';
            lightbox.innerHTML = `
                <button class="absolute top-4 right-4 text-white text-2xl" id="lightbox-close">&times;</button>
                <button class="absolute left-4 top-1/2 transform -translate-y-1/2 text-white text-4xl" id="lightbox-prev">&lsaquo;</button>
                <div class="max-w-4xl max-h-full p-4">
                    <img src="" alt="" class="max-h-[80vh] max-w-full object-contain" id="lightbox-image">
                    <div class="text-white text-center mt-2" id="lightbox-caption"></div>
                </div>
                <button class="absolute right-4 top-1/2 transform -translate-y-1/2 text-white text-4xl" id="lightbox-next">&rsaquo;</button>
            `;
            document.body.appendChild(lightbox);
            
            // Add event listeners
            document.getElementById('lightbox-close').addEventListener('click', () => {
                lightbox.classList.add('hidden');
                document.body.classList.remove('overflow-hidden');
            });
            
            document.getElementById('lightbox-prev').addEventListener('click', (e) => {
                e.stopPropagation();
                navigateGallery(-1);
            });
            
            document.getElementById('lightbox-next').addEventListener('click', (e) => {
                e.stopPropagation();
                navigateGallery(1);
            });
            
            // Close on backdrop click
            lightbox.addEventListener('click', (e) => {
                if (e.target === lightbox) {
                    lightbox.classList.add('hidden');
                    document.body.classList.remove('overflow-hidden');
                }
            });
            
            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                if (lightbox.classList.contains('hidden')) return;
                
                if (e.key === 'Escape') {
                    lightbox.classList.add('hidden');
                    document.body.classList.remove('overflow-hidden');
                } else if (e.key === 'ArrowLeft') {
                    navigateGallery(-1);
                } else if (e.key === 'ArrowRight') {
                    navigateGallery(1);
                }
            });
        }
        
        // Set current gallery items for navigation
        lightbox.dataset.currentGallery = currentItem.closest('[data-gallery]').dataset.gallery;
        lightbox.dataset.currentIndex = Array.from(galleryItems).indexOf(currentItem);
        
        // Update lightbox content
        const lightboxImage = document.getElementById('lightbox-image');
        const lightboxCaption = document.getElementById('lightbox-caption');
        
        lightboxImage.src = imageUrl;
        lightboxCaption.textContent = imageTitle;
        
        // Show lightbox
        lightbox.classList.remove('hidden');
        document.body.classList.add('overflow-hidden');
        
        function navigateGallery(direction) {
            const currentIndex = parseInt(lightbox.dataset.currentIndex);
            let newIndex = currentIndex + direction;
            
            // Loop around if at the end
            if (newIndex < 0) newIndex = galleryItems.length - 1;
            if (newIndex >= galleryItems.length) newIndex = 0;
            
            const newItem = galleryItems[newIndex];
            const newImageUrl = newItem.dataset.galleryItem;
            const newImageTitle = newItem.dataset.galleryTitle || '';
            
            lightboxImage.src = newImageUrl;
            lightboxCaption.textContent = newImageTitle;
            lightbox.dataset.currentIndex = newIndex;
        }
    }
}

/**
 * Smooth Scrolling Functionality
 * Enables smooth scrolling for anchor links
 */
function initSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]:not([data-no-scroll])').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            
            // Skip empty anchors or javascript: links
            if (targetId === '#' || targetId.startsWith('javascript:')) return;
            
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                e.preventDefault();
                
                // Close mobile menu if open
                const mobileMenu = document.getElementById('mobile-menu');
                const mobileMenuButton = document.getElementById('mobile-menu-button');
                
                if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
                    mobileMenu.classList.add('hidden');
                    if (mobileMenuButton) {
                        mobileMenuButton.classList.remove('hamburger-active');
                    }
                }
                
                // Scroll to target
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update URL hash without scrolling
                history.pushState(null, null, targetId);
            }
        });
    });
}

/**
 * Date Picker Initialization
 * Sets up Flatpickr date pickers with custom configuration
 */
function initDatePickers() {
    if (typeof flatpickr !== 'function') return;
    
    // Default configuration
    const defaultConfig = {
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'F j, Y',
        disableMobile: true,
        locale: {
            firstDayOfWeek: 1
        }
    };
    
    // Single date pickers
    document.querySelectorAll('.datepicker:not(.datepicker-range)').forEach(input => {
        const config = { ...defaultConfig };
        
        // Add custom configurations
        if (input.dataset.minDate) {
            config.minDate = input.dataset.minDate;
        }
        
        if (input.dataset.maxDate) {
            config.maxDate = input.dataset.maxDate;
        }
        
        if (input.dataset.disableDates) {
            try {
                config.disable = JSON.parse(input.dataset.disableDates);
            } catch (e) {
                console.error('Invalid disable dates format', e);
            }
        }
        
        flatpickr(input, config);
    });
    
    // Date range pickers
    document.querySelectorAll('.datepicker-range').forEach(input => {
        const config = { ...defaultConfig, mode: 'range' };
        
        // Add custom configurations
        if (input.dataset.minDate) {
            config.minDate = input.dataset.minDate;
        }
        
        if (input.dataset.maxDate) {
            config.maxDate = input.dataset.maxDate;
        }
        
        if (input.dataset.disableDates) {
            try {
                config.disable = JSON.parse(input.dataset.disableDates);
            } catch (e) {
                console.error('Invalid disable dates format', e);
            }
        }
        
        flatpickr(input, config);
    });
}

/**
 * Price Calculator for Booking
 * Calculates and updates price based on selected dates and options
 */
function initPriceCalculator() {
    const bookingForm = document.getElementById('booking-form');
    if (!bookingForm) return;
    
    const checkInInput = bookingForm.querySelector('#check_in');
    const checkOutInput = bookingForm.querySelector('#check_out');
    const guestsInput = bookingForm.querySelector('#guests');
    const pricePerNightElement = document.getElementById('price-per-night');
    const totalNightsElement = document.getElementById('total-nights');
    const totalPriceElement = document.getElementById('total-price');
    
    // Base price per night (can be set in data attribute)
    const basePricePerNight = parseFloat(bookingForm.dataset.basePrice) || 5000;
    
    function updatePrice() {
        if (!checkInInput || !checkOutInput || !pricePerNightElement || !totalNightsElement || !totalPriceElement) return;
        
        const checkInDate = new Date(checkInInput.value);
        const checkOutDate = new Date(checkOutInput.value);
        
        if (isNaN(checkInDate.getTime()) || isNaN(checkOutDate.getTime())) return;
        
        // Calculate number of nights
        const timeDiff = checkOutDate.getTime() - checkInDate.getTime();
        const nights = Math.ceil(timeDiff / (1000 * 3600 * 24));
        
        if (nights <= 0) return;
        
        // Calculate price per night (can include dynamic pricing based on season, etc.)
        let pricePerNight = basePricePerNight;
        
        // Adjust price based on number of guests if needed
        const guests = parseInt(guestsInput?.value) || 1;
        if (guests > 2) {
            pricePerNight += (guests - 2) * 500; // Additional charge per guest
        }
        
        // Calculate total price
        const totalPrice = pricePerNight * nights;
        
        // Update display
        pricePerNightElement.textContent = `₹${pricePerNight.toLocaleString()}`;
        totalNightsElement.textContent = nights;
        totalPriceElement.textContent = `₹${totalPrice.toLocaleString()}`;
        
        // Update hidden input for form submission
        const totalPriceInput = bookingForm.querySelector('#total_price');
        if (totalPriceInput) {
            totalPriceInput.value = totalPrice;
        }
    }
    
    // Add event listeners
    if (checkInInput) checkInInput.addEventListener('change', updatePrice);
    if (checkOutInput) checkOutInput.addEventListener('change', updatePrice);
    if (guestsInput) guestsInput.addEventListener('change', updatePrice);
    
    // Initial calculation
    updatePrice();
}

/**
 * Lazy Loading for Images
 * Improves page load performance by loading images only when they enter the viewport
 */
function initLazyLoading() {
    // Use native lazy loading if supported
    document.querySelectorAll('img:not([loading])').forEach(img => {
        img.setAttribute('loading', 'lazy');
    });
    
    // Use Intersection Observer as fallback for browsers that don't support native lazy loading
    if ('IntersectionObserver' in window) {
        const lazyImages = document.querySelectorAll('img[data-src]');
        
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    
                    if (img.dataset.srcset) {
                        img.srcset = img.dataset.srcset;
                    }
                    
                    img.classList.add('loaded');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    } else {
        // Fallback for older browsers
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            if (img.dataset.srcset) {
                img.srcset = img.dataset.srcset;
            }
        });
    }
}

// Initialize lazy loading
document.addEventListener('DOMContentLoaded', function() {
    initLazyLoading();
});

/**
 * Micro-interactions
 * Adds subtle animations and effects to improve user experience
 */
function initMicroInteractions() {
    // Add ripple effect to buttons
    document.querySelectorAll('.btn, button:not([data-no-ripple]), .ripple-effect').forEach(button => {
        button.addEventListener('click', function(e) {
            const rect = button.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            
            button.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
}

// Initialize micro-interactions
document.addEventListener('DOMContentLoaded', function() {
    initMicroInteractions();
});

/**
 * Scroll Progress Indicator
 * Shows a progress bar indicating how far the user has scrolled down the page
 */
function initScrollProgress() {
    // Create progress bar if it doesn't exist
    if (!document.getElementById('scroll-progress')) {
        const progressBar = document.createElement('div');
        progressBar.id = 'scroll-progress';
        document.body.appendChild(progressBar);
    }
    
    const progressBar = document.getElementById('scroll-progress');
    
    function updateProgress() {
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight - windowHeight;
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        const scrollPercentage = (scrollTop / documentHeight) * 100;
        progressBar.style.width = `${scrollPercentage}%`;
        
        // Add class when scrolled
        if (scrollTop > 100) {
            progressBar.classList.add('visible');
        } else {
            progressBar.classList.remove('visible');
        }
    }
    
    window.addEventListener('scroll', updateProgress, { passive: true });
    updateProgress(); // Initialize on page load
}

// Initialize scroll progress
document.addEventListener('DOMContentLoaded', function() {
    initScrollProgress();
});

/**
 * Page Transitions
 * Adds smooth transitions between pages using the View Transition API
 */
function initPageTransitions() {
    // Check if the browser supports the View Transition API
    if (!document.startViewTransition) return;
    
    // Add transition to all internal links
    document.querySelectorAll('a[href^="/"]:not([data-no-transition])').forEach(link => {
        link.addEventListener('click', e => {
            // Skip if modifier keys are pressed
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            
            const href = link.getAttribute('href');
            
            // Skip for downloads, etc.
            if (link.getAttribute('download') || link.getAttribute('target') === '_blank') return;
            
            e.preventDefault();
            
            // Start the transition
            document.startViewTransition(() => {
                // Show loading indicator
                if (window.showLoading) window.showLoading();
                
                // Navigate to the new page
                window.location.href = href;
            });
        });
    });
}

// Initialize page transitions
document.addEventListener('DOMContentLoaded', function() {
    initPageTransitions();
});

/**
 * Header Scroll Functionality
 * Controls header visibility and appearance based on scroll position and direction
 */
function initHeaderScroll() {
    const header = document.querySelector('nav');
    if (!header) return;
    
    let lastScrollTop = 0;
    const scrollThreshold = 100; // Pixels to scroll before changing header appearance
    
    function handleScroll() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Add shadow and background opacity when scrolled
        if (scrollTop > 10) {
            header.classList.add('header-scrolled');
        } else {
            header.classList.remove('header-scrolled');
        }
        
        // Hide header when scrolling down, show when scrolling up
        if (scrollTop > scrollThreshold) {
            if (scrollTop > lastScrollTop && !header.classList.contains('header-hidden')) {
                // Scrolling down
                header.classList.add('header-hidden');
            } else if (scrollTop < lastScrollTop && header.classList.contains('header-hidden')) {
                // Scrolling up
                header.classList.remove('header-hidden');
            }
        } else {
            header.classList.remove('header-hidden');
        }
        
        lastScrollTop = scrollTop;
    }
    
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // Initialize on page load
}

// Initialize header scroll behavior
document.addEventListener('DOMContentLoaded', function() {
    initHeaderScroll();
});