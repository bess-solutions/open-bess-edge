// BESS Solutions — app.js
// Micro-interactions y animaciones

// ── Contador animado stats del hero ──────────────────────────────
function animateCounters() {
  const counters = document.querySelectorAll('.stat-number[data-target]');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.target);
      const suffix = el.dataset.suffix || '';
      const duration = 1800;
      const start = performance.now();
      function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = Math.floor(eased * target);
        el.textContent = current + suffix;
        if (progress < 1) requestAnimationFrame(update);
        else el.textContent = target + suffix;
      }
      requestAnimationFrame(update);
      observer.unobserve(el);
    });
  }, { threshold: 0.2 });
  counters.forEach(el => observer.observe(el));
}

// ── Nav scroll effect ─────────────────────────────────────────────
function initNav() {
  const nav = document.getElementById('nav');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 60) {
      nav.style.background = 'rgba(3, 7, 18, 0.97)';
    } else {
      nav.style.background = 'rgba(3, 7, 18, 0.85)';
    }
  });
}

// ── Reveal on scroll ──────────────────────────────────────────────
function initReveal() {
  const targets = document.querySelectorAll(
    '.feature-card, .metric-card, .hw-card, .step, .roadmap-item, .pricing-card'
  );
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  targets.forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = `opacity 0.5s ease ${i * 0.05}s, transform 0.5s ease ${i * 0.05}s`;
    observer.observe(el);
  });
}

// ── Hero parallax grid ─────────────────────────────────────────────
function initParallax() {
  const grid = document.querySelector('.hero-grid');
  if (!grid) return;
  window.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 20;
    const y = (e.clientY / window.innerHeight - 0.5) * 20;
    grid.style.transform = `translate(${x}px, ${y}px)`;
  });
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  animateCounters();
  initNav();
  initReveal();
  initParallax();
});
