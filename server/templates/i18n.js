<script>
  // Global translation helper
  let currentLang = localStorage.getItem('lang') || 'en';
  let translations = {};

  async function loadTranslations(lang) {
    try {
      const res = await fetch(`/api/translations/${lang}`);
      if (res.ok) {
        translations = await res.json();
        currentLang = lang;
        localStorage.setItem('lang', lang);
        return true;
      }
    } catch (e) {
      console.error('Failed to load translations:', e);
    }
    return false;
  }

  function t(key, defaultVal = key) {
    const keys = key.split('.');
    let obj = translations;
    for (let k of keys) {
      if (obj && typeof obj === 'object') {
        obj = obj[k];
      } else {
        return defaultVal;
      }
    }
    return obj || defaultVal;
  }

  function createLangSelector() {
    const select = document.createElement('select');
    select.id = 'langSelect';
    select.className = 'form-select form-select-sm d-inline-block';
    select.style.cssText = 'width: auto; margin-left: 10px;';
    select.innerHTML = '<option value="en">English</option><option value="tr">Türkçe</option>';
    select.value = currentLang;
    select.addEventListener('change', (e) => {
      loadTranslations(e.target.value).then(() => {
        window.location.reload();
      });
    });
    return select;
  }

  // Initialize translations on page load
  window.addEventListener('DOMContentLoaded', () => {
    loadTranslations(currentLang);
  });
</script>