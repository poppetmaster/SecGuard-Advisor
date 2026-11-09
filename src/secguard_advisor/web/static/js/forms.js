/*
 * Estado pendiente de los formularios.
 *
 * Marca el formulario como ocupado, muestra el mensaje del servidor o del
 * cliente, deshabilita el envío y evita envíos duplicados. No envía ni
 * reintenta solicitudes por su cuenta: si la conexión se pierde, informa y
 * deja que la persona decida.
 *
 * Los mensajes y el texto visible vienen del propio formulario
 * (`data-pending-indicator`), así que el JavaScript no inventa etapas.
 */
(function () {
  "use strict";

  var NETWORK_MESSAGE =
    "No se pudo completar la solicitud. Verificá la conexión y volvé a intentarlo.";
  var TIMEOUT_MESSAGE =
    "La solicitud tardó demasiado. El servidor puede seguir procesándola; revisá el estado antes de reenviar.";
  var stashed = new Map();

  function isForm(element) {
    if (!element || !element.closest) {
      return null;
    }
    return element.tagName === "FORM" ? element : element.closest("form");
  }

  function formKey(form) {
    return form.getAttribute("data-form-key") || "";
  }

  function submitButtons(form) {
    return Array.prototype.slice.call(
      form.querySelectorAll('button[type="submit"], button:not([type])')
    );
  }

  // `hidden` es una propiedad de HTMLElement: en un <svg> hay que tocar el
  // atributo, o el estilo del navegador ([hidden]{display:none}) lo mantiene oculto.
  function setHidden(element, hidden) {
    if (!element) {
      return;
    }
    if (hidden) {
      element.setAttribute("hidden", "");
    } else {
      element.removeAttribute("hidden");
    }
  }

  function spinner(form) {
    return form.querySelector("[data-pending-spinner]");
  }

  function pendingText(form) {
    return form.querySelector("[data-pending-text]");
  }

  function errorSlot(form) {
    return form.querySelector("[data-form-error]");
  }

  function showError(form, message) {
    var slot = errorSlot(form);
    if (!slot) {
      return;
    }
    slot.textContent = message;
    slot.hidden = false;
  }

  function clearError(form) {
    var slot = errorSlot(form);
    if (slot) {
      slot.textContent = "";
      slot.hidden = true;
    }
  }

  function setPending(form, pending) {
    if (!form) {
      return;
    }
    var icon = spinner(form);
    var text = pendingText(form);
    var buttons = submitButtons(form);

    if (pending) {
      form.setAttribute("aria-busy", "true");
      setHidden(icon, false);
      setHidden(text, false);
      buttons.forEach(function (button) {
        button.dataset.wasDisabled = button.disabled ? "1" : "0";
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
      });
      return;
    }

    form.removeAttribute("aria-busy");
    setHidden(icon, true);
    setHidden(text, true);
    buttons.forEach(function (button) {
      if (button.dataset.wasDisabled !== "1") {
        button.disabled = false;
      }
      delete button.dataset.wasDisabled;
      button.removeAttribute("aria-disabled");
    });
  }

  function stashValues(form) {
    var key = formKey(form);
    if (!key) {
      return;
    }
    var values = {};
    Array.prototype.forEach.call(form.elements, function (field) {
      if (!field.name || field.type === "file" || field.type === "submit") {
        return;
      }
      if (field.type === "checkbox" || field.type === "radio") {
        values[field.name] = field.checked ? field.value : "";
        return;
      }
      values[field.name] = field.value;
    });
    stashed.set(key, values);
  }

  function restoreValues(form) {
    var key = formKey(form);
    var values = key ? stashed.get(key) : null;
    if (!values) {
      return;
    }
    Array.prototype.forEach.call(form.elements, function (field) {
      if (!field.name || field.type === "file" || !(field.name in values)) {
        return;
      }
      if (field.type === "checkbox" || field.type === "radio") {
        field.checked = field.value === values[field.name];
        return;
      }
      field.value = values[field.name];
    });
    stashed.delete(key);
  }

  function formForResponse(element) {
    return isForm(element);
  }

  document.addEventListener("htmx:beforeRequest", function (event) {
    var form = formForResponse(event.detail.elt);
    if (!form) {
      return;
    }
    clearError(form);
    stashValues(form);
    setPending(form, true);
  });

  // HTMX no reemplaza respuestas 4xx/5xx por defecto. Cuando el cuerpo es el
  // fragmento del propio destino (mismo id que el objetivo), se permite el
  // reemplazo para mostrar el motivo; un cuerpo de otra forma no se inyecta.
  document.addEventListener("htmx:beforeSwap", function (event) {
    var detail = event.detail;
    if (detail.shouldSwap || !detail.xhr || detail.xhr.status < 400) {
      return;
    }
    var target = detail.target || (detail.requestConfig && detail.requestConfig.target);
    var body = detail.xhr.responseText;
    if (!target || !target.id || !body) {
      return;
    }
    try {
      var parsed = new DOMParser().parseFromString(body, "text/html");
      var root = parsed.body.firstElementChild;
      if (root && root.id === target.id) {
        detail.shouldSwap = true;
        detail.isError = false;
      }
    } catch (error) {
      return;
    }
  });

  document.addEventListener("htmx:afterSwap", function (event) {
    var elt = event.detail.requestConfig ? event.detail.requestConfig.elt : null;
    var requestForm = formForResponse(elt);
    var key = requestForm ? formKey(requestForm) : "";
    if (!key) {
      stashed.clear();
      return;
    }
    var xhr = event.detail.xhr;
    var failed = !xhr || xhr.status >= 400;
    if (!failed) {
      stashed.delete(key);
      return;
    }
    var form = document.querySelector('[data-form-key="' + key + '"]');
    if (form) {
      restoreValues(form);
    } else {
      stashed.delete(key);
    }
  });

  document.addEventListener("htmx:afterRequest", function (event) {
    var form = formForResponse(event.detail.elt);
    if (!form) {
      return;
    }
    setPending(form, false);
    if (event.detail.successful === false && event.detail.xhr && event.detail.xhr.status === 0) {
      showError(form, NETWORK_MESSAGE);
    }
  });

  document.addEventListener("htmx:sendError", function (event) {
    var form = formForResponse(event.detail.elt);
    if (!form) {
      return;
    }
    setPending(form, false);
    showError(form, NETWORK_MESSAGE);
  });

  document.addEventListener("htmx:timeout", function (event) {
    var form = formForResponse(event.detail.elt);
    if (!form) {
      return;
    }
    setPending(form, false);
    showError(form, TIMEOUT_MESSAGE);
  });

  // Un formulario ocupado no vuelve a enviarse, ni con Enter ni con doble clic.
  document.addEventListener(
    "submit",
    function (event) {
      var form = isForm(event.target);
      if (form && form.getAttribute("aria-busy") === "true") {
        event.preventDefault();
        event.stopPropagation();
      }
    },
    true
  );

  // Formularios sin HTMX (por ejemplo, el reintento que navega): el envío se
  // bloquea igual y se restablece si el navegador vuelve desde la caché.
  document.addEventListener("submit", function (event) {
    var form = isForm(event.target);
    if (!form || form.getAttribute("hx-post") || form.getAttribute("hx-get")) {
      return;
    }
    clearError(form);
    setPending(form, true);
  });

  window.addEventListener("pageshow", function () {
    Array.prototype.forEach.call(
      document.querySelectorAll('form[aria-busy="true"]'),
      function (form) {
        setPending(form, false);
      }
    );
  });
})();
