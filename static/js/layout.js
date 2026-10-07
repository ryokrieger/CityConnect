/* Layout behaviour shared by every page: mobile menu, password toggle, dismissible alerts. */
(function () {
  'use strict';

  var sidebar = document.getElementById('sidebar');
  var burger = document.getElementById('hamburgerBtn');

  function setMenu(open) {
    if (!sidebar || !burger) return;
    sidebar.classList.toggle('is-open', open);
    burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  }

  if (burger) {
    burger.addEventListener('click', function () {
      setMenu(!sidebar.classList.contains('is-open'));
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setMenu(false);
  });

  document.addEventListener('click', function (e) {
    var target = e.target;

    // Close the mobile menu after picking a link, or when clicking outside it.
    if (sidebar && sidebar.classList.contains('is-open')) {
      if (target.closest('.nav-item') || !target.closest('#sidebar, #hamburgerBtn')) setMenu(false);
    }

    // Password show/hide: <button class="password-toggle" data-target="input-id">
    var toggle = target.closest('.password-toggle');
    if (toggle) {
      var input = document.getElementById(toggle.getAttribute('data-target'));
      if (!input) return;
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.textContent = show ? 'Hide' : 'Show';
      toggle.setAttribute('aria-pressed', show ? 'true' : 'false');
    }

    // Flash message dismiss.
    var dismiss = target.closest('.alert-dismiss');
    if (dismiss) {
      var alertEl = dismiss.closest('.alert');
      if (alertEl) alertEl.remove();
    }
  });
})();