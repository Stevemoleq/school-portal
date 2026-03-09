/* Modern UI Utilities */

// Modal functionality
class Modal {
    constructor(id) {
        this.modal = document.getElementById(id);
        this.overlay = this.modal?.querySelector('[data-modal-overlay]');
    }
    
    open() {
        if (this.modal) {
            this.modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }
    
    close() {
        if (this.modal) {
            this.modal.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    }
    
    toggle() {
        this.modal?.classList.contains('active') ? this.close() : this.open();
    }
}

// Tab functionality
class TabGroup {
    constructor(Container) {
        this.container = document.querySelector(Container);
        this.tabs = this.container?.querySelectorAll('[data-tab]');
        this.tabPanes = this.container?.querySelectorAll('[data-tab-pane]');
        
        this.tabs?.forEach(tab => {
            tab.addEventListener('click', () => this.selectTab(tab));
        });
    }
    
    selectTab(tab) {
        const target = tab.getAttribute('data-tab');
        
        // Hide all panes
        this.tabPanes?.forEach(pane => pane.classList.add('hidden'));
        this.tabs?.forEach(t => t.classList.remove('active'));
        
        // Show selected pane
        document.getElementById(target)?.classList.remove('hidden');
        tab.classList.add('active');
    }
}

// Dropdown functionality
class Dropdown {
    constructor(trigger, menu) {
        this.trigger = document.querySelector(trigger);
        this.menu = document.querySelector(menu);
        
        if (this.trigger && this.menu) {
            this.trigger.addEventListener('click', () => this.toggle());
            document.addEventListener('click', (e) => this.handleClickOutside(e));
        }
    }
    
    toggle() {
        this.menu.classList.toggle('hidden');
    }
    
    handleClickOutside(event) {
        if (!this.trigger.contains(event.target) && !this.menu.contains(event.target)) {
            this.menu.classList.add('hidden');
        }
    }
}

// Smooth number animation
function animateNumber(element, target, duration = 1000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Form validation
class FormValidator {
    constructor(form) {
        this.form = document.querySelector(form);
        this.inputs = this.form?.querySelectorAll('input, textarea, select');
        this.setupValidation();
    }
    
    setupValidation() {
        this.inputs?.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
        });
    }
    
    validateField(field) {
        let isValid = true;
        let error = '';
        
        // Check required
        if (field.hasAttribute('required') && !field.value.trim()) {
            isValid = false;
            error = 'This field is required';
        }
        
        // Check email
        if (field.type === 'email' && field.value && !this.isValidEmail(field.value)) {
            isValid = false;
            error = 'Invalid email format';
        }
        
        // Check min length
        if (field.hasAttribute('minlength') && field.value.length < parseInt(field.getAttribute('minlength'))) {
            isValid = false;
            error = `Minimum length is ${field.getAttribute('minlength')}`;
        }
        
        this.setFieldState(field, isValid, error);
        return isValid;
    }
    
    setFieldState(field, isValid, error) {
        const wrapper = field.parentElement;
        
        if (isValid) {
            wrapper.classList.remove('error');
            const errorEl = wrapper.querySelector('.error-message');
            if (errorEl) errorEl.remove();
        } else {
            wrapper.classList.add('error');
            const errorEl = document.createElement('span');
            errorEl.className = 'error-message text-red-500 text-sm mt-1 block';
            errorEl.textContent = error;
            wrapper.appendChild(errorEl);
        }
    }
    
    isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    
    validate() {
        let isValid = true;
        this.inputs?.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });
        return isValid;
    }
}

// Table sorting
class DataTable {
    constructor(tableSelector) {
        this.table = document.querySelector(tableSelector);
        this.headers = this.table?.querySelectorAll('th[data-sortable]');
        this.setupSorting();
    }
    
    setupSorting() {
        this.headers?.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => this.sortTable(header));
        });
    }
    
    sortTable(header) {
        const column = header.getAttribute('data-sortable');
        const tbody = this.table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        const direction = header.getAttribute('data-direction') === 'asc' ? 'desc' : 'asc';
        
        rows.sort((a, b) => {
            const aValue = a.querySelector(`td:nth-child(${this.getColumnIndex(column)})`).textContent;
            const bValue = b.querySelector(`td:nth-child(${this.getColumnIndex(column)})`).textContent;
            
            if (direction === 'asc') {
                return aValue.localeCompare(bValue);
            } else {
                return bValue.localeCompare(aValue);
            }
        });
        
        rows.forEach(row => tbody.appendChild(row));
        
        // Update header state
        this.headers?.forEach(h => h.removeAttribute('data-direction'));
        header.setAttribute('data-direction', direction);
    }
    
    getColumnIndex(column) {
        let index = 1;
        this.headers?.forEach((header, i) => {
            if (header.getAttribute('data-sortable') === column) {
                index = i + 1;
            }
        });
        return index;
    }
}

// Lazy load images
function lazyLoadImages() {
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.getAttribute('data-src');
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });
    
    images.forEach(img => imageObserver.observe(img));
}

// Export utilities
window.UI = {
    Modal,
    TabGroup,
    Dropdown,
    FormValidator,
    DataTable,
    animateNumber,
    showToast,
    lazyLoadImages
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    lazyLoadImages();
    AOS.init({
        duration: 600,
        once: true
    });
});
