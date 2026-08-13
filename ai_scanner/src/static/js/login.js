/* ============================================================
   QUICK LOGIN / REGISTER / GUEST — no password (placeholder)
   Login = preferred name · Register = name (placeholder)
   Guest = random per-user ID, unique to each visitor
   ============================================================ */

(function () {
  'use strict';

  var form = document.getElementById('login-form');
  var input = document.getElementById('login-name');
  var btn = document.getElementById('login-btn');
  var note = document.getElementById('login-note');
  var invite = document.getElementById('login-invite');
  var guestBtn = document.getElementById('guest-btn');
  var guestHint = document.getElementById('guest-hint');
  var tabs = document.querySelectorAll('.login-tab');
  var glow = document.getElementById('mouse-glow');
  var isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  var mode = 'login';

  var COPY = {
    login: {
      invite: 'State thy name to enter the archive',
      placeholder: 'Your preferred name...',
      btn: 'ENTER THE ARCHIVE',
      note: 'Quick entry — no password needed'
    },
    register: {
      invite: 'Establish a new identity within the archive',
      placeholder: 'Choose a keeper name...',
      btn: 'REGISTER & ENTER',
      note: 'Registration placeholder — creates a local session'
    }
  };

  function getCookie(name) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }

  function setCookie(name, value, days) {
    var d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = name + '=' + encodeURIComponent(value) +
      '; expires=' + d.toUTCString() + '; path=/; SameSite=Lax';
  }

  function setMode(m) {
    mode = m;
    tabs.forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-mode') === m);
    });
    var c = COPY[m];
    invite.textContent = c.invite;
    input.placeholder = c.placeholder;
    btn.querySelector('.login-btn-label').textContent = c.btn;
    note.textContent = c.note;
  }

  function enter(name, m) {
    btn.disabled = true;
    guestBtn.disabled = true;
    btn.querySelector('.login-btn-label').textContent =
      m === 'register' ? 'REGISTERING…' : 'OPENING THE ARCHIVE…';
    fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, mode: m })
    }).then(function (res) {
      if (!res.ok) throw new Error('server refused');
      return res.json();
    }).then(function (d) {
      setCookie('user_mode', d.mode || m, 30);
      window.location.href = '/';
    }).catch(function () {
      setCookie('user_name', name, 30);
      setCookie('user_mode', m, 30);
      window.location.href = '/';
    });
  }

  function enterGuest() {
    btn.disabled = true;
    guestBtn.disabled = true;
    guestBtn.querySelector('.guest-btn-label').textContent = 'FORGING IDENTITY…';
    fetch('/api/guest', {
      method: 'POST'
    }).then(function (res) {
      if (!res.ok) throw new Error('server refused');
      return res.json();
    }).then(function (d) {
      revealGuestId(d.name);
      setCookie('user_mode', 'guest', 30);
      setTimeout(function () { window.location.href = '/'; }, 1400);
    }).catch(function () {
      var id = genGuestId();
      revealGuestId(id);
      setCookie('user_name', id, 30);
      setCookie('user_mode', 'guest', 30);
      setTimeout(function () { window.location.href = '/'; }, 1400);
    });
  }

  function genGuestId() {
    var chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
    var s = '';
    for (var i = 0; i < 8; i++) s += chars.charAt(Math.floor(Math.random() * chars.length));
    return 'GUEST-' + s;
  }

  function revealGuestId(id) {
    guestHint.textContent = 'YOUR TEMPORARY ID: ' + id;
    guestHint.style.color = 'var(--gold)';
    note.textContent = 'Entering as guest visitor…';
  }

  /* already signed in -> straight in */
  var existing = getCookie('user_name');
  if (existing) {
    window.location.replace('/');
    return;
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () { setMode(t.getAttribute('data-mode')); });
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = input.value.replace(/\s+/g, ' ').trim();
    if (!name) {
      input.focus();
      input.style.boxShadow = '0 0 0 3px rgba(168,50,50,0.25), 0 0 18px rgba(168,50,50,0.25)';
      note.textContent = mode === 'register'
        ? 'A keeper must choose a name to register.'
        : 'The archive requires a name, keeper.';
      setTimeout(function () {
        input.style.boxShadow = '';
        note.textContent = COPY[mode].note;
      }, 2200);
      return;
    }
    note.textContent = mode === 'register'
      ? 'Welcome to the archive, ' + name + '.'
      : 'Welcome back, ' + name + '.';
    input.blur();
    enter(name, mode);
  });

  guestBtn.addEventListener('click', enterGuest);

  /* mouse glow (desktop only) */
  if (!isTouch && glow) {
    var timer;
    document.addEventListener('mousemove', function (e) {
      glow.style.left = e.clientX + 'px';
      glow.style.top = e.clientY + 'px';
      glow.classList.add('show');
      clearTimeout(timer);
      timer = setTimeout(function () { glow.classList.remove('show'); }, 3000);
    });
  } else if (glow) {
    glow.style.display = 'none';
  }
})();
