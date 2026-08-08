/* ============================================================
   QUICK LOGIN — enter preferred name, no password
   ============================================================ */

(function () {
  'use strict';

  var form = document.getElementById('login-form');
  var input = document.getElementById('login-name');
  var btn = document.getElementById('login-btn');
  var note = document.getElementById('login-note');
  var glow = document.getElementById('mouse-glow');
  var isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

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

  function enter(name) {
    btn.disabled = true;
    btn.querySelector('.login-btn-label').textContent = 'OPENING THE ARCHIVE…';
    fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name })
    }).then(function (res) {
      if (!res.ok) throw new Error('server refused');
      return res.json();
    }).then(function () {
      window.location.href = '/';
    }).catch(function () {
      setCookie('user_name', name, 30);
      window.location.href = '/';
    });
  }

  /* already signed in -> straight in */
  var existing = getCookie('user_name');
  if (existing) {
    window.location.replace('/');
    return;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = input.value.replace(/\s+/g, ' ').trim();
    if (!name) {
      input.focus();
      input.style.boxShadow = '0 0 0 3px rgba(168,50,50,0.25), 0 0 18px rgba(168,50,50,0.25)';
      note.textContent = 'The archive requires a name, keeper.';
      setTimeout(function () {
        input.style.boxShadow = '';
        note.textContent = 'Quick entry — no password needed';
      }, 2200);
      return;
    }
    note.textContent = 'Welcome, ' + name + '.';
    input.blur();
    enter(name);
  });

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