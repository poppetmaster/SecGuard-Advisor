/*
 * Menú lateral en móvil.
 *
 * El panel ya está en el documento (oculto). Se controla con atributos y foco:
 * abrir mueve el foco al panel, cerrar lo devuelve al botón. Escape, el fondo y
 * el botón de cerrar cierran el menú; elegir un destino también lo cierra.
 * No se inicializan componentes de Flowbite: los estilos son los del componente
 * y el comportamiento se limita a lo que la accesibilidad exige.
 */
(function () {
  "use strict";

  var toggle = document.getElementById("nav-toggle");
  var drawer = document.getElementById("mobile-nav");
  if (!toggle || !drawer) {
    return;
  }

  var lastFocus = null;

  function focusable() {
    return Array.prototype.filter.call(
      drawer.querySelectorAll('a[href], button:not([disabled])'),
      function (element) {
        return element.offsetParent !== null;
      }
    );
  }

  function isOpen() {
    return !drawer.hasAttribute("hidden");
  }

  function open() {
    lastFocus = document.activeElement;
    drawer.removeAttribute("hidden");
    toggle.setAttribute("aria-expanded", "true");
    document.body.classList.add("overflow-hidden");
    var dialog = drawer.querySelector('[role="dialog"]');
    var first = dialog
      ? dialog.querySelector("button[data-drawer-close]") || dialog.querySelector("a[href]")
      : null;
    if (first) {
      first.focus();
    }
  }

  function close(options) {
    if (!isOpen()) {
      return;
    }
    var restore = !options || options.restore !== false;
    drawer.setAttribute("hidden", "");
    toggle.setAttribute("aria-expanded", "false");
    document.body.classList.remove("overflow-hidden");
    if (restore && lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
    lastFocus = null;
  }

  toggle.addEventListener("click", function () {
    if (isOpen()) {
      close();
    } else {
      open();
    }
  });

  Array.prototype.forEach.call(
    drawer.querySelectorAll("[data-drawer-close]"),
    function (element) {
      element.addEventListener("click", function () {
        close();
      });
    }
  );

  drawer.addEventListener("click", function (event) {
    var link = event.target.closest("a[href]");
    if (link) {
      close({ restore: false });
    }
  });

  document.addEventListener("keydown", function (event) {
    if (!isOpen()) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    var items = focusable();
    if (!items.length) {
      return;
    }
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // Al volver desde la caché del navegador el panel debe quedar cerrado.
  window.addEventListener("pageshow", function () {
    close({ restore: false });
  });
})();
