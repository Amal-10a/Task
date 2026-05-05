
// Network Animation
const networkCanvas = document.getElementById('networkCanvas');
if (networkCanvas) {
    const ctx = networkCanvas.getContext('2d');
    let particles = [];
    
    function getColors() {
        const isDark = document.body.classList.contains('dark');
        return {
            particle: isDark ? '#A57A5A' : '#4A2A18',
            line: isDark ? [165, 122, 90] : [74, 42, 24]
        };
    }
    
    function resizeCanvas() {
        networkCanvas.width = window.innerWidth;
        networkCanvas.height = window.innerHeight;
    }
    
    class Particle {
        constructor() {
            this.x = Math.random() * networkCanvas.width;
            this.y = Math.random() * networkCanvas.height;
            this.vx = (Math.random() - 0.5) * 0.8;
            this.vy = (Math.random() - 0.5) * 0.8;
            this.radius = Math.random() * 2 + 1;
        }
        
        update() {
            this.x += this.vx;
            this.y += this.vy;
            
            if (this.x < 0 || this.x > networkCanvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > networkCanvas.height) this.vy *= -1;
        }
        
        draw() {
            const colors = getColors();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = colors.particle;
            ctx.fill();
        }
    }
    
    function initParticles() {
        particles = [];
        const numParticles = Math.floor((networkCanvas.width * networkCanvas.height) / 18000);
        const count = Math.min(Math.max(numParticles, 30), 80);
        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }
    
    function animate() {
        const colors = getColors();
        ctx.clearRect(0, 0, networkCanvas.width, networkCanvas.height);
        
        // Draw connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 150) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(${colors.line[0]}, ${colors.line[1]}, ${colors.line[2]}, ${0.12 * (1 - distance / 150)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }
        
        // Update and draw particles
        particles.forEach(particle => {
            particle.update();
            particle.draw();
        });
        
        requestAnimationFrame(animate);
    }
    
    // Initialize
    resizeCanvas();
    initParticles();
    animate();
    
    // Handle resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            resizeCanvas();
            initParticles();
        }, 250);
    });
}

// ============================================
// Theme Toggle
// ============================================
function toggleTheme() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeIcon();
    
    // Show toast notification
    showToast(
        isDark ? 'تم تفعيل الوضع الداكن' : 'تم تفعيل الوضع الفاتح',
        isDark ? 'dark' : 'light'
    );
}

function updateThemeIcon() {
    const icon = document.querySelector('.theme-toggle i');
    if (icon) {
        icon.classList.remove('fa-moon', 'fa-sun');
        if (document.body.classList.contains('dark')) {
            icon.classList.add('fa-sun');
        } else {
            icon.classList.add('fa-moon');
        }
    }
}

// Initialize theme on load — الوضع الافتراضي: نهاري (فاتح)
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark');
    }
    setTimeout(updateThemeIcon, 100);
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
} else {
    initTheme();
}

// ============================================
// Modern Toast Notifications
// ============================================
function showToast(message, type = 'success') {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.toast-notification');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    
    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle';
    const iconClass = type === 'dark' ? 'moon' : type === 'light' ? 'sun' : icon;
    
    toast.innerHTML = `
        <i class="fas fa-${iconClass}"></i>
        <span>${message}</span>
    `;
    
    // Add styles dynamically
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'linear-gradient(135deg, #27ae60, #1e8449)' : 
                     type === 'error' ? 'linear-gradient(135deg, #e74c3c, #c0392b)' :
                     type === 'dark' ? 'linear-gradient(135deg, #1a1a2e, #16213e)' :
                     'linear-gradient(135deg, #f39c12, #e67e22)'};
        color: white;
        padding: 16px 24px;
        border-radius: 14px;
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 12px;
        z-index: 10000;
        animation: slideInRight 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
        max-width: 320px;
    `;
    
    document.body.appendChild(toast);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards';
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}

// Add toast animations
const toastAnimations = document.createElement('style');
toastAnimations.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
`;
document.head.appendChild(toastAnimations);

// ============================================
// Auto-hide alerts
// ============================================
function initAutoHideAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'all 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(20px)';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAutoHideAlerts);
} else {
    initAutoHideAlerts();
}

// ============================================
// Confirm Delete
// ============================================
function confirmDelete(message) {
    return confirm(message || 'هل أنت متأكد من الحذف؟');
}

// ============================================
// Modal Functions
// ============================================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.opacity = '1';
        }, 10);
        
        // Add open class for animation
        modal.classList.add('modal-open');
        
        // Focus first input
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 300);
        }
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.opacity = '0';
        modal.classList.remove('modal-open');
        
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
        
        // Restore body scroll
        document.body.style.overflow = '';
    }
}

function closeModalOnOverlay(event, modalId) {
    if (event.target.classList.contains('modal-overlay')) {
        closeModal(modalId);
    }
}

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal-overlay[style*="flex"]');
        openModals.forEach(modal => {
            closeModal(modal.id);
        });
    }
});

// ============================================
// Task Status & Priority Color Coding
// ============================================
function initStatusColors() {
    // Status badges
    const statusBadges = document.querySelectorAll('.status-badge');
    statusBadges.forEach(badge => {
        const text = badge.textContent.trim();
        if (text.includes('معلقة')) {
            badge.classList.add('status-pending');
        } else if (text.includes('قيد التنفيذ')) {
            badge.classList.add('status-progress');
        } else if (text.includes('مكتملة')) {
            badge.classList.add('status-completed');
        }
    });
    
    // Priority elements
    const priorityElements = document.querySelectorAll('.priority, [class*="priority"]');
    priorityElements.forEach(el => {
        const text = el.textContent.trim();
        if (text.includes('عالية')) {
            el.classList.add('priority-high');
        } else if (text.includes('متوسطة')) {
            el.classList.add('priority-medium');
        } else if (text.includes('عادية') || text.includes('منخفضة')) {
            el.classList.add('priority-normal');
        }
    });
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStatusColors);
} else {
    initStatusColors();
}

// ============================================
// Update Task Progress
// ============================================
function updateProgress(taskId, progress) {
    progress = Number(progress);
    if (!Number.isFinite(progress)) progress = 0;
    progress = Math.max(0, Math.min(100, progress));

    // Update UI immediately for smooth experience
    const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
    
    if (taskCard) {
        const progressValue = taskCard.querySelector('.progress-value');
        const progressFill = taskCard.querySelector('.progress-fill');
        const progressSlider = taskCard.querySelector('.progress-slider');
        
        if (progressValue) progressValue.textContent = progress + '%';
        if (progressFill) progressFill.style.width = progress + '%';
        if (progressSlider) progressSlider.value = progress;
    }
    
    // Show loading state
    showLoadingState(taskCard, true);
    
    var headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
    fetch('/update_task_progress/' + taskId, {
        method: 'POST',
        headers: headers,
        body: 'progress=' + encodeURIComponent(progress)
    })
    .then(response => response.json())
    .then(data => {
        showLoadingState(taskCard, false);
        
        if (data.success) {
            showToast('تم تحديث نسبة الإنجاز بنجاح', 'success');
        } else {
            showToast('حدث خطأ أثناء التحديث', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showLoadingState(taskCard, false);
        showToast('حدث خطأ أثناء التحديث', 'error');
    });
}

function showLoadingState(element, show) {
    if (!element) return;
    
    if (show) {
        element.style.opacity = '0.7';
        element.style.pointerEvents = 'none';
    } else {
        element.style.opacity = '1';
        element.style.pointerEvents = 'auto';
    }
}

// ============================================
// Smooth Scroll to Elements
// ============================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href !== '#') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }
    });
});

// ============================================
// Stagger Animation on Page Load
// ============================================
function initStaggerAnimations() {
    // Add stagger animation to cards
    const cards = document.querySelectorAll('.stat-card, .task-card, .alert-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100 + (index * 50));
    });
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStaggerAnimations);
} else {
    initStaggerAnimations();
}

// ============================================
// Progress Slider Real-time Update
// ============================================
function initProgressSliders() {
    const sliders = document.querySelectorAll('.progress-slider');
    
    sliders.forEach(slider => {
        // Update on input (real-time)
        slider.addEventListener('input', function() {
            const taskId = this.closest('.task-card')?.dataset.taskId || 
                          this.dataset.taskId || 
                          this.getAttribute('onchange')?.match(/updateProgress\((\d+)/)?.[1];
            
            const value = this.value;
            const progressValue = this.closest('.task-progress')?.querySelector('.progress-value');
            const progressFill = this.closest('.task-progress')?.querySelector('.progress-fill');
            
            if (progressValue) progressValue.textContent = value + '%';
            if (progressFill) progressFill.style.width = value + '%';
        });
        
        // Update on change (save to server)
        slider.addEventListener('change', function() {
            const match = this.getAttribute('onchange')?.match(/updateProgress\((\d+)/);
            if (match) {
                updateProgress(match[1], this.value);
            }
        });
    });
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProgressSliders);
} else {
    initProgressSliders();
}

// ============================================
// Initialize all functions when DOM is ready
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    initTheme();
    
    // Initialize alerts auto-hide
    initAutoHideAlerts();
    
    // Initialize status colors
    initStatusColors();
    
    // Initialize progress sliders
    initProgressSliders();
    
    // Initialize stagger animations
    initStaggerAnimations();
    
    console.log('✓ Task Management System initialized successfully');
});

// ============================================
// Utility Functions
// ============================================

// Format date to Arabic
function formatDateArabic(dateString) {
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return date.toLocaleDateString('ar-SA', options);
}

// Calculate days remaining
function getDaysRemaining(dueDate) {
    const today = new Date();
    const due = new Date(dueDate);
    const diffTime = due - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) return 'متأخر ' + Math.abs(diffDays) + ' يوم';
    if (diffDays === 0) return 'اليوم';
    if (diffDays === 1) return 'غداً';
    return diffDays + ' يوم';
}

// ============================================
// Add more button animations
// ============================================
document.addEventListener('click', function(e) {
    // Main buttons
    if (e.target.classList.contains('btn') || e.target.closest('.btn')) {
        const button = e.target.classList.contains('btn') ? e.target : e.target.closest('.btn');
        
        // Create ripple element
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.35);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
        `;
        
        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 600);
        
        // Add bounce animation to button
        button.classList.add('btn-bounce');
        setTimeout(() => button.classList.remove('btn-bounce'), 400);
    }
    
    // Nav menu items
    if (e.target.closest('.nav-menu a')) {
        const link = e.target.closest('.nav-menu a');
        link.style.transform = 'scale(0.95)';
        setTimeout(() => {
            link.style.transform = '';
        }, 150);
    }
});

// Add bounce animation style
if (!document.getElementById('btn-animations')) {
    const btnAnimations = document.createElement('style');
    btnAnimations.id = 'btn-animations';
    btnAnimations.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        @keyframes btnBounce {
            0% { transform: scale(1); }
            50% { transform: scale(0.97); }
            100% { transform: scale(1); }
        }
        .btn-bounce {
            animation: btnBounce 0.3s ease;
        }
        @keyframes iconBounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }
        .btn:hover i {
            animation: iconBounce 0.6s ease infinite;
        }
    `;
    document.head.appendChild(btnAnimations);
}

// Export functions for global use
window.toggleTheme = toggleTheme;
window.openModal = openModal;
window.closeModal = closeModal;
window.closeModalOnOverlay = closeModalOnOverlay;
window.confirmDelete = confirmDelete;
window.updateProgress = updateProgress;
window.showToast = showToast;

// ============================================
// Notifications Toggle
// ============================================
function toggleNotifications() {
    const dropdown = document.getElementById('notificationDropdown');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

function markAllRead() {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const headers = {};
    if (csrfMeta) headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
    fetch('/api/notifications/read_all', { method: 'POST', headers: headers })
        .then((response) => {
            if (!response.ok) throw new Error('read_all_failed');
            const dropdown = document.getElementById('notificationDropdown');
            if (dropdown) dropdown.classList.remove('show');
            loadNotifications();
            showToast('تم تعليم جميع التنبيهات كمقروءة', 'success');
        })
        .catch(() => showToast('تعذر تحديث الإشعارات', 'error'));
}

// Close notifications when clicking outside
document.addEventListener('click', function(e) {
    const container = document.querySelector('.notifications-container');
    if (container && !container.contains(e.target)) {
        const dropdown = document.getElementById('notificationDropdown');
        if (dropdown) {
            dropdown.classList.remove('show');
        }
    }
});

window.toggleNotifications = toggleNotifications;
window.markAllRead = markAllRead;

// ============================================
// Mobile Sidebar Navigation
// ============================================
function initMobileMenu() {
    // Only initialize mobile menu on screens smaller than 768px
    if (window.innerWidth > 768) {
        // On desktop, sidebar is always visible
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.remove('active');
        }
        return;
    }
    
    // Create hamburger button if it doesn't exist
    if (!document.querySelector('.hamburger-menu')) {
        const hamburger = document.createElement('button');
        hamburger.className = 'hamburger-menu';
        hamburger.innerHTML = '<i class="fas fa-bars"></i>';
        hamburger.setAttribute('aria-label', 'فتح القائمة');
        document.body.appendChild(hamburger);
    }
    
    // Create sidebar overlay if it doesn't exist
    if (!document.querySelector('.sidebar-overlay')) {
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);
    }
    
    // Toggle sidebar
    const hamburger = document.querySelector('.hamburger-menu');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    if (hamburger && sidebar) {
        hamburger.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            overlay?.classList.toggle('active');
            
            // Update icon
            const icon = hamburger.querySelector('i');
            if (sidebar.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
        
        // Close sidebar when clicking overlay
        if (overlay) {
            overlay.addEventListener('click', function() {
                sidebar.classList.remove('active');
                overlay.classList.remove('active');
                const icon = hamburger.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            });
        }
        
        // Close sidebar when clicking nav link
        const navLinks = sidebar.querySelectorAll('.nav-menu a');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                sidebar.classList.remove('active');
                overlay?.classList.remove('active');
                const icon = hamburger.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            });
        });
    }
}

// Handle window resize
window.addEventListener('resize', function() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    const hamburger = document.querySelector('.hamburger-menu');
    
    if (window.innerWidth > 768) {
        // Desktop - show sidebar, remove hamburger
        if (sidebar) {
            sidebar.classList.remove('active');
            sidebar.style.left = '0';
        }
        if (overlay) {
            overlay.classList.remove('active');
        }
        if (hamburger) {
            hamburger.style.display = 'none';
        }
    } else {
        // Mobile - ensure hamburger exists
        if (hamburger) {
            hamburger.style.display = 'flex';
        }
    }
});

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileMenu);
} else {
    initMobileMenu();
}

// Export mobile menu function
window.initMobileMenu = initMobileMenu;

// ============================================
// Mobile Navigation Toggle
// ============================================
function toggleMobileNav() {
    const mobileNav = document.getElementById('mobileNav');
    const overlay = document.querySelector('.mobile-nav-overlay');
    const hamburger = document.querySelector('.hamburger-menu');
    
    if (mobileNav) {
        mobileNav.classList.toggle('active');
    }
    if (overlay) {
        overlay.classList.toggle('active');
    }
    if (hamburger) {
        const icon = hamburger.querySelector('i');
        if (mobileNav && mobileNav.classList.contains('active')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
        } else if (icon) {
            icon.classList.remove('fa-times');
            icon.classList.add('fa-bars');
        }
    }
}

window.toggleMobileNav = toggleMobileNav;

// ============================================
// Global Notifications Loader
// ============================================
function loadNotifications() {
    const listEl = document.getElementById('notificationList');
    const badgeEl = document.getElementById('globalNotificationBadge');
    if (!listEl || !badgeEl) return;
    fetch('/api/notifications')
        .then(r => r.json())
        .then(data => {
            const items = (data && data.notifications) ? data.notifications : [];
            const unread = items.filter(n => !n.is_read).length;
            if (unread > 0) {
                badgeEl.textContent = unread;
                badgeEl.style.display = 'flex';
            } else {
                badgeEl.style.display = 'none';
            }
            if (items.length === 0) {
                listEl.innerHTML = '<div class="notification-empty">لا توجد إشعارات</div>';
                return;
            }
            listEl.innerHTML = items.map(n => {
                const cls = n.is_read ? '' : ' warning';
                return `<div class="notification-item${cls}" data-id="${n.id}">
                    <div class="notification-item-title">${n.title || 'إشعار'}</div>
                    <div class="notification-item-desc">${n.message || ''}</div>
                </div>`;
            }).join('');
            listEl.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', function() {
                    const id = this.getAttribute('data-id');
                    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                    const headers = {};
                    if (csrfMeta) headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
                    fetch('/api/notifications/read/' + id, { method: 'POST', headers: headers })
                        .then((response) => {
                            if (!response.ok) throw new Error('read_failed');
                            loadNotifications();
                        })
                        .catch(() => showToast('تعذر تحديث الإشعار', 'error'));
                });
            });
        })
        .catch(() => {});
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        loadNotifications();
        setInterval(loadNotifications, 30000);
    });
} else {
    loadNotifications();
    setInterval(loadNotifications, 30000);
}

