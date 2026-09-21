/* feedback-widget.js — the reader's half of the site-feedback lane.
 *
 * WHY: Sean must never have to publish an email address on a teaching site.
 * This is the little box that replaces it. It is deliberately boring.
 *
 * WHAT IT COSTS THE PAGE
 *   ~7 KB, no framework, no dependency, no build step, nothing fetched until
 *   the reader actually opens it. Load it with `defer` (or from a module) and
 *   first paint never waits on it. It touches no global except
 *   window.InformedFeedback and creates no DOM until opened.
 *
 * CSP
 *   Every style is set through the CSSOM (el.style.setProperty), never an
 *   inline style attribute or a <style> element, so this runs unchanged under
 *   a strict `style-src 'self'`. The only network call is the POST, which is
 *   same-origin on sean.theinformed.org and therefore satisfies
 *   `connect-src 'self'` with no CSP edit at all.
 *
 * HOW A SITE ADOPTS IT — either one works:
 *   1. Bake it in (recommended, zero runtime dependency on another service):
 *        copy this file into the site, add
 *        <script src="feedback-widget.js" defer></script>
 *   2. Link the shared copy:
 *        <script src="https://sean.theinformed.org/feedback/widget.js" defer></script>
 *   Then give any button `data-informed-feedback` and it opens the box.
 *   Or call window.InformedFeedback.open() from your own handler.
 *
 * THE SITE IS DERIVED, NOT ASKED. The reader never picks a site: the endpoint
 * takes the host from the browser's Origin header and this widget sends
 * location.pathname. Nothing identifying is collected.
 */
(function () {
  "use strict";
  if (window.InformedFeedback) return;

  var ENDPOINT =
    (document.currentScript && document.currentScript.getAttribute("data-endpoint")) ||
    "https://sean.theinformed.org/feedback/submit";
  // Same-origin wherever the page is already on sean.theinformed.org: keeps
  // it inside `connect-src 'self'` and skips the CORS preflight entirely.
  if (location.host === "sean.theinformed.org") ENDPOINT = "/feedback/submit";

  var MAX_CHARS = 2000;
  var open = false;
  var nodes = null;

  function css(el, rules) {
    for (var k in rules) el.style.setProperty(k, rules[k]);
    return el;
  }
  function make(tag, rules, text) {
    var el = document.createElement(tag);
    if (rules) css(el, rules);
    if (text != null) el.textContent = text; // textContent, always. Never innerHTML.
    return el;
  }

  var FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

  function build() {
    // A <dialog> opened with showModal(), NOT a plain z-index overlay.
    //
    // This is load-bearing, not a nicety. A site that opens the feedback box
    // from INSIDE another modal — the Space Environment Explorer's welcome
    // dialog is the first one — puts that dialog in the browser's TOP LAYER,
    // which sits above every z-index there is. A fixed overlay, at any
    // z-index, would render BEHIND it: invisible and unclickable. A second
    // showModal() joins the same top layer above the first, so the feedback
    // box appears over the welcome dialog and the welcome dialog STAYS OPEN
    // underneath.
    //
    // That is deliberately the opposite of "close the host modal first".
    // Closing it would fire that dialog's `close` event, and on the space site
    // scheduleFeaturedToast() starts a ten-second timer on exactly that event
    // — so a flow that dismissed the welcome dialog would pop the
    // constellation-of-the-day note over the reader while they were still
    // typing their comment. Leaving the host modal open avoids that entirely,
    // and returns the reader to what they were reading when they close this.
    //
    // Older browsers with no showModal() fall back to the fixed overlay, which
    // is correct everywhere except stacked-modal case above.
    var useDialog = typeof document.createElement("dialog").showModal === "function";
    var overlay = make(useDialog ? "dialog" : "div", {
      position: "fixed", inset: "0", width: "100%", height: "100%",
      "max-width": "100%", "max-height": "100%", border: "0", margin: "0",
      background: "rgba(8,10,16,0.62)",
      display: "flex", "align-items": "center", "justify-content": "center",
      padding: "16px", "z-index": "2147483000", font: "16px/1.5 " + FONT,
    });
    overlay.__isDialog = useDialog;
    var card = make("div", {
      background: "#12161f", color: "#e8ecf4", "max-width": "34rem", width: "100%",
      "max-height": "90vh", overflow: "auto", "border-radius": "12px",
      padding: "20px 22px", border: "1px solid #2b3344",
      "box-shadow": "0 18px 48px rgba(0,0,0,0.5)",
    });
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-label", "Send a comment to Sean");

    var h = make("h2", { margin: "0 0 6px", "font-size": "1.15rem", "font-weight": "650" },
      "Tell Sean what you think");
    var lede = make("p", { margin: "0 0 14px", "font-size": "0.92rem", color: "#a8b3c7" },
      "Corrections, questions, or anything that reads wrong. It goes to a private page only he sees — no address published, no mailing list, nothing shared.");

    var label = make("label", { display: "block", "font-size": "0.85rem", "margin-bottom": "5px", color: "#c6cfdf" },
      "Your comment");
    var ta = make("textarea", {
      width: "100%", "min-height": "8.5rem", "box-sizing": "border-box", padding: "10px",
      "border-radius": "8px", border: "1px solid #39435a", background: "#0c1017",
      color: "#e8ecf4", font: "0.95rem/1.5 " + FONT, resize: "vertical",
    });
    ta.maxLength = MAX_CHARS;
    ta.id = "informed-feedback-text";
    label.setAttribute("for", ta.id);
    var count = make("div", { "font-size": "0.75rem", color: "#7c879c", margin: "4px 0 12px", "text-align": "right" }, "");
    function updateCount() {
      count.textContent = ta.value.length + " / " + MAX_CHARS;
    }
    ta.addEventListener("input", updateCount);
    updateCount();

    var emailLabel = make("label", { display: "block", "font-size": "0.85rem", "margin-bottom": "5px", color: "#c6cfdf" },
      "Reply address (optional)");
    var email = make("input", {
      width: "100%", "box-sizing": "border-box", padding: "9px 10px", "border-radius": "8px",
      border: "1px solid #39435a", background: "#0c1017", color: "#e8ecf4", font: "0.95rem " + FONT,
    });
    email.type = "email";
    email.id = "informed-feedback-email";
    email.autocomplete = "email";
    email.placeholder = "you@example.com";
    emailLabel.setAttribute("for", email.id);
    var emailHint = make("p", { "font-size": "0.78rem", color: "#7c879c", margin: "6px 0 14px" },
      "Leave it blank and the comment still arrives — you just won't hear back. Fill it in only if you'd like a reply. It is stored on a private page, never published and never added to any list.");

    // Honeypot. No person can see it, focus it or tab to it, so anything that
    // fills it in is automation. Off-screen rather than display:none — some
    // crawlers skip hidden fields, and we want them to find this one.
    var hpWrap = make("div", {
      position: "absolute", left: "-9999px", top: "auto", width: "1px", height: "1px", overflow: "hidden",
    });
    hpWrap.setAttribute("aria-hidden", "true");
    var hp = document.createElement("input");
    hp.type = "text";
    hp.name = "website";
    hp.tabIndex = -1;
    hp.autocomplete = "off";
    hpWrap.appendChild(hp);

    var msg = make("p", { margin: "0 0 12px", "font-size": "0.88rem", "min-height": "1.2em" }, "");
    msg.setAttribute("role", "status");
    msg.setAttribute("aria-live", "polite");

    var row = make("div", { display: "flex", gap: "10px", "justify-content": "flex-end", "flex-wrap": "wrap" });
    var cancel = make("button", {
      padding: "9px 16px", "border-radius": "8px", border: "1px solid #39435a",
      background: "transparent", color: "#c6cfdf", font: "0.92rem " + FONT, cursor: "pointer",
    }, "Close");
    cancel.type = "button";
    var send = make("button", {
      padding: "9px 18px", "border-radius": "8px", border: "1px solid #4c7dff",
      background: "#3b6ae0", color: "#fff", font: "600 0.92rem " + FONT, cursor: "pointer",
    }, "Send");
    send.type = "button";
    row.appendChild(cancel);
    row.appendChild(send);

    card.appendChild(h);
    card.appendChild(lede);
    card.appendChild(label);
    card.appendChild(ta);
    card.appendChild(count);
    card.appendChild(emailLabel);
    card.appendChild(email);
    card.appendChild(emailHint);
    card.appendChild(hpWrap);
    card.appendChild(msg);
    card.appendChild(row);
    overlay.appendChild(card);

    return { overlay: overlay, card: card, ta: ta, email: email, hp: hp, msg: msg, send: send, cancel: cancel };
  }

  function setMsg(text, tone) {
    nodes.msg.textContent = text;
    nodes.msg.style.setProperty("color", tone === "bad" ? "#ffb4a8" : tone === "good" ? "#8fe3b0" : "#a8b3c7");
  }

  function close() {
    if (!open) return;
    open = false;
    document.removeEventListener("keydown", onKey, true);
    if (!nodes) return;
    if (nodes.overlay.__isDialog && nodes.overlay.open) {
      try { nodes.overlay.close(); } catch (e) { /* already closing */ }
    }
    if (nodes.overlay.parentNode) nodes.overlay.parentNode.removeChild(nodes.overlay);
  }

  function onKey(ev) {
    // stopPropagation so Escape closes THIS box and does not also reach a host
    // page's own key handler (or, on the space site, the welcome dialog behind
    // it). A native modal <dialog> handles Escape itself; the `cancel` listener
    // in openBox() catches that path.
    if (ev.key === "Escape") { ev.stopPropagation(); close(); }
  }

  function submit() {
    var text = nodes.ta.value.trim();
    if (!text) { setMsg("Write a line or two first.", "bad"); nodes.ta.focus(); return; }
    nodes.send.disabled = true;
    nodes.send.textContent = "Sending…";
    setMsg("Sending…", "info");

    var payload = {
      comment: text,
      page: location.pathname,
      replyTo: nodes.email.value.trim() || null,
      formShownAt: nodes.shownAt,
      website: nodes.hp.value,
      widget: "informed-feedback/1",
    };

    var done = false;
    var timer = setTimeout(function () {
      if (done) return;
      done = true;
      fail("That's taking longer than it should — the comment box may be down. Nothing was lost: your words are still in the box, so please try again in a little while.");
    }, 15000);

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "omit",
      mode: location.host === "sean.theinformed.org" ? "same-origin" : "cors",
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (out) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (out.status === 200 && out.data && out.data.ok) {
          nodes.card.textContent = "";
          var ok = make("h2", { margin: "0 0 8px", "font-size": "1.15rem" }, "Thank you");
          var p = make("p", { margin: "0 0 18px", color: "#a8b3c7", "font-size": "0.95rem" },
            out.data.message || "That went straight to Sean.");
          var b = make("button", {
            padding: "9px 18px", "border-radius": "8px", border: "1px solid #4c7dff",
            background: "#3b6ae0", color: "#fff", font: "600 0.92rem " + FONT, cursor: "pointer",
          }, "Close");
          b.type = "button";
          b.addEventListener("click", close);
          nodes.card.appendChild(ok);
          nodes.card.appendChild(p);
          nodes.card.appendChild(b);
          b.focus();
          return;
        }
        // The server always sends a plain-English `message`. Show THAT, not a
        // status code — the reader did nothing wrong and deserves a sentence.
        fail((out.data && out.data.message) ||
          "That didn't go through. Your words are still in the box — please try again in a moment.");
      })
      .catch(function () {
        if (done) return;
        done = true;
        clearTimeout(timer);
        // Endpoint down, DNS gone, offline, blocked. Never a silent failure
        // and never an endless spinner.
        fail("The comment box can't be reached right now. Your words are still in the box — try again in a little while.");
      });
  }

  function fail(text) {
    setMsg(text, "bad");
    nodes.send.disabled = false;
    nodes.send.textContent = "Send";
  }

  function openBox() {
    if (open) return;
    open = true;
    nodes = build();
    nodes.shownAt = Date.now(); // the timing gate's other half
    nodes.cancel.addEventListener("click", close);
    nodes.send.addEventListener("click", submit);
    nodes.overlay.addEventListener("click", function (ev) {
      if (ev.target === nodes.overlay) close();
    });
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(nodes.overlay);
    if (nodes.overlay.__isDialog) {
      // The browser's own Escape handling fires `cancel`, then `close`. Route
      // both back through our close() so the node is removed and state resets.
      nodes.overlay.addEventListener("cancel", function () { close(); });
      nodes.overlay.addEventListener("close", function () { close(); });
      try {
        nodes.overlay.showModal();
      } catch (e) {
        // Already-open or detached: fall back to the plain overlay behaviour.
        nodes.overlay.__isDialog = false;
      }
    }
    nodes.ta.focus();
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target && ev.target.closest ? ev.target.closest("[data-informed-feedback]") : null;
    if (t) { ev.preventDefault(); openBox(); }
  });

  window.InformedFeedback = { open: openBox, close: close, endpoint: ENDPOINT };
})();
