// Pre-paint theme boot (runs before first paint, no flash of the wrong theme).
// Same key and fallback as dev.thedevrails.com: localStorage "devrails-theme",
// else the OS preference. Kept as a string so it can be inlined in <head>.
export const THEME_STORAGE_KEY = "devrails-theme";

export const THEME_BOOT_SCRIPT = `(function(){var t;try{t=localStorage.getItem('${THEME_STORAGE_KEY}')}catch(e){}if(t!=='dark'&&t!=='light')t=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';var r=document.documentElement;r.setAttribute('data-theme',t);r.style.colorScheme=t;})();`;
