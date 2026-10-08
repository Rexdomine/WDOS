/**
 * WDOS Stage 4 Shell Client Scripts
 * Handles search shortcut, profile menu, accessibility toggle live feedback,
 * and scoped AJAX notifications.
 */
document.addEventListener('DOMContentLoaded', function () {
  // CSRF token helper
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  // Keyboard shortcut: Cmd+K / Ctrl+K opens or focuses search
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('#global-search-input') || document.querySelector('[data-foundation-search]');
      if (searchInput) {
        if (searchInput.tagName === 'INPUT') {
          searchInput.focus();
        } else {
          window.location.href = '/foundation/search/';
        }
      }
    }
  });

  // Profile avatar dropdown trigger
  const profileTriggers = document.querySelectorAll('[data-profile-trigger]');
  profileTriggers.forEach(function (trigger) {
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      const menu = this.closest('[data-profile-menu]');
      const panel = menu ? menu.querySelector('[data-profile-panel]') : null;
      if (panel) {
        const isHidden = panel.hasAttribute('hidden');
        document.querySelectorAll('[data-profile-panel]').forEach(function (p) {
          if (p !== panel) p.setAttribute('hidden', '');
        });
        document.querySelectorAll('[data-profile-trigger]').forEach(function (t) {
          if (t !== trigger) t.setAttribute('aria-expanded', 'false');
        });
        if (isHidden) {
          panel.removeAttribute('hidden');
          this.setAttribute('aria-expanded', 'true');
        } else {
          panel.setAttribute('hidden', '');
          this.setAttribute('aria-expanded', 'false');
        }
      }
    });
  });

  document.querySelectorAll('[data-profile-panel]').forEach(function (panel) {
    panel.addEventListener('click', function (e) {
      e.stopPropagation();
    });
  });

  document.addEventListener('click', function () {
    document.querySelectorAll('[data-profile-panel]').forEach(function (panel) {
      panel.setAttribute('hidden', '');
    });
    document.querySelectorAll('[data-profile-trigger]').forEach(function (trigger) {
      trigger.setAttribute('aria-expanded', 'false');
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('[data-profile-panel]').forEach(function (panel) {
        panel.setAttribute('hidden', '');
      });
      document.querySelectorAll('[data-profile-trigger]').forEach(function (trigger) {
        trigger.setAttribute('aria-expanded', 'false');
      });
    }
  });

  // Mark notification read via API
  document.querySelectorAll('[data-mark-read]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const notifId = this.getAttribute('data-mark-read');
      const card = this.closest('.notification-card');
      fetch('/foundation/api/notifications/' + notifId + '/read/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
          'Content-Type': 'application/json',
        },
      })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.status === 'ok' && card) {
          card.classList.remove('unread');
          btn.remove();
          const badge = document.querySelector('[data-notif-badge]');
          if (badge) {
            let count = parseInt(badge.textContent, 10);
            if (!isNaN(count) && count > 0) {
              count -= 1;
              badge.textContent = count;
              if (count === 0) badge.style.display = 'none';
            }
          }
        }
      })
      .catch(function (err) {
        console.error('Error marking notification read', err);
      });
    });
  });

  // Live accessibility toggle handlers (in settings)
  const highContrastToggle = document.querySelector('#high_contrast_toggle');
  if (highContrastToggle) {
    highContrastToggle.addEventListener('change', function () {
      if (this.checked) {
        document.body.classList.add('theme-high-contrast');
      } else {
        document.body.classList.remove('theme-high-contrast');
      }
    });
  }

  const reducedMotionToggle = document.querySelector('#reduced_motion_toggle');
  if (reducedMotionToggle) {
    reducedMotionToggle.addEventListener('change', function () {
      if (this.checked) {
        document.body.classList.add('reduce-motion');
      } else {
        document.body.classList.remove('reduce-motion');
      }
    });
  }
});
