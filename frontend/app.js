/* Flavour & Rush frontend — talks to the FastAPI backend on the same origin. */

"use strict";

const API = ""; // same origin as the page

// One session per browser tab so the agent remembers this conversation
const SESSION_ID =
  sessionStorage.getItem("fr-session") ||
  (() => {
    const id = "web-" + Math.random().toString(36).slice(2, 10);
    sessionStorage.setItem("fr-session", id);
    return id;
  })();

const $ = (sel) => document.querySelector(sel);

/* ===================== Tabs ===================== */

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(tab.dataset.panel).classList.add("active");
  });
});

/* ===================== Backend status ===================== */

async function checkHealth() {
  const badge = $("#apiStatus");
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    badge.classList.toggle("ok", data.status === "ok");
    badge.classList.toggle("bad", data.status !== "ok");
    badge.querySelector(".status-text").textContent =
      data.status === "ok" ? "online" : "degraded";
  } catch {
    badge.classList.add("bad");
    badge.querySelector(".status-text").textContent = "offline";
  }
}
checkHealth();
setInterval(checkHealth, 30_000);

/* ===================== Chat ===================== */

const chatHistory = $("#chatHistory");
const chatText = $("#chatText");
const chatLoading = $("#chatLoading");

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chatHistory.appendChild(wrap);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function setChatBusy(busy) {
  chatLoading.classList.toggle("hidden", !busy);
  $("#sendBtn").disabled = busy;
  if (busy) chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
  const text = chatText.value.trim();
  if (!text) return;
  chatText.value = "";
  chatText.style.height = "auto";
  addMessage("user", text);
  setChatBusy(true);

  try {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, message: text }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    addMessage("agent", (await res.json()).reply);
  } catch (err) {
    addMessage("error", `Could not reach the assistant: ${err.message}`);
  } finally {
    setChatBusy(false);
  }
}

$("#sendBtn").addEventListener("click", sendMessage);
chatText.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
chatText.addEventListener("input", () => {
  chatText.style.height = "auto";
  chatText.style.height = Math.min(chatText.scrollHeight, 120) + "px";
});

/* ===================== Voice ===================== */
/* Records mic audio with the Web Audio API, encodes it as 16-bit WAV
   (what the backend expects), sends it to /voice-chat, then plays the
   spoken reply. */

const voiceBtn = $("#voiceBtn");
const voiceHint = $("#voiceHint");
let rec = null; // { ctx, stream, processor, source, chunks, rate }

function encodeWav(float32, rate) {
  // Convert float samples [-1, 1] to 16-bit PCM with a 44-byte WAV header
  const pcm = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const v = new DataView(buf);
  const writeStr = (off, str) => [...str].forEach((c, i) => v.setUint8(off + i, c.charCodeAt(0)));
  writeStr(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); writeStr(8, "WAVE");
  writeStr(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  writeStr(36, "data"); v.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const chunks = [];
  processor.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  source.connect(processor);
  processor.connect(ctx.destination);
  rec = { ctx, stream, processor, source, chunks, rate: ctx.sampleRate };
  voiceBtn.classList.add("recording");
  voiceHint.textContent = "Listening… click the mic again when you're done.";
}

async function stopRecording() {
  const { ctx, stream, processor, source, chunks, rate } = rec;
  rec = null;
  processor.disconnect();
  source.disconnect();
  stream.getTracks().forEach((t) => t.stop());
  await ctx.close();
  voiceBtn.classList.remove("recording");
  voiceHint.textContent = "";

  // Stitch the captured chunks into one buffer
  const total = chunks.reduce((n, c) => n + c.length, 0);
  if (total < rate * 0.3) return; // too short to be real speech
  const samples = new Float32Array(total);
  let off = 0;
  for (const c of chunks) { samples.set(c, off); off += c.length; }

  // Send to the backend
  setChatBusy(true);
  voiceHint.textContent = "Transcribing and thinking…";
  try {
    const form = new FormData();
    form.append("audio", encodeWav(samples, rate), "speech.wav");
    form.append("session_id", SESSION_ID);
    const res = await fetch(`${API}/voice-chat`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    addMessage("user", `🎤 ${data.transcript}`);
    addMessage("agent", data.reply);
    new Audio(`data:audio/wav;base64,${data.audio_base64}`).play().catch(() => {});
  } catch (err) {
    addMessage("error", `Voice message failed: ${err.message}`);
  } finally {
    setChatBusy(false);
    voiceHint.textContent = "";
  }
}

voiceBtn.addEventListener("click", async () => {
  try {
    if (rec) await stopRecording();
    else await startRecording();
  } catch (err) {
    voiceHint.textContent = `Microphone unavailable: ${err.message}`;
  }
});

/* ===================== Menu search ===================== */

$("#menuForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("#menuQuery").value.trim() || "full menu with prices";
  const results = $("#menuResults");
  results.innerHTML = "";
  $("#menuLoading").classList.remove("hidden");

  try {
    const res = await fetch(`${API}/menu?query=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    for (const p of data.passages) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `<div class="meta">Knowledge base · page ${p.page}</div>`;
      const body = document.createElement("div");
      body.textContent = p.content;
      card.appendChild(body);
      results.appendChild(card);
    }
    if (!data.passages.length) {
      results.innerHTML = `<div class="card">Nothing found for “${query}”.</div>`;
    }
  } catch (err) {
    results.innerHTML = `<div class="card error">Search failed: ${err.message}</div>`;
  } finally {
    $("#menuLoading").classList.add("hidden");
  }
});

/* ===================== Order form ===================== */

const itemRows = $("#itemRows");

function addItemRow(name = "", qty = 1, price = "") {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input placeholder="Item name (from the menu)" class="i-name" required maxlength="100" value="${name}" />
    <input type="number" class="i-qty" min="1" max="50" value="${qty}" required title="Quantity" />
    <input type="number" class="i-price" min="0" step="0.01" placeholder="Unit Rs." value="${price}" required title="Unit price" />
    <button type="button" class="remove" title="Remove item">×</button>`;
  row.querySelector(".remove").addEventListener("click", () => {
    if (itemRows.children.length > 1) row.remove();
    updateTotal();
  });
  row.querySelectorAll("input").forEach((i) => i.addEventListener("input", updateTotal));
  itemRows.appendChild(row);
}

function updateTotal() {
  let total = 0;
  itemRows.querySelectorAll(".item-row").forEach((row) => {
    total += (+row.querySelector(".i-qty").value || 0) * (+row.querySelector(".i-price").value || 0);
  });
  $("#orderTotal").textContent = `Rs. ${total.toFixed(0)}`;
}

$("#addItemBtn").addEventListener("click", () => addItemRow());
addItemRow(); // start with one row

// Delivery address only applies to delivery orders
$("#orderType").addEventListener("change", (e) => {
  const isDelivery = e.target.value === "delivery";
  $("#addressField").classList.toggle("hidden", !isDelivery);
  $("#addressField").querySelector("input").required = isDelivery;
});
$("#addressField").querySelector("input").required = true;

$("#orderForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const items = [...itemRows.querySelectorAll(".item-row")].map((row) => ({
    item: row.querySelector(".i-name").value.trim(),
    qty: +row.querySelector(".i-qty").value,
    unit_price: +row.querySelector(".i-price").value,
  }));

  const body = {
    full_name: form.full_name.value.trim(),
    phone: form.phone.value.trim(),
    items,
    payment_method: form.payment_method.value,
    delivery_address:
      $("#orderType").value === "delivery" ? form.delivery_address.value.trim() : null,
  };

  const summary = $("#orderSummary");
  summary.innerHTML = "";
  $("#orderLoading").classList.remove("hidden");

  try {
    const res = await fetch(`${API}/order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    const lines = data.items.map((i) => `  • ${i.item} ×${i.qty} — Rs. ${i.unit_price * i.qty}`);
    summary.innerHTML = `
      <div class="card">
        <h4>✅ Order #${data.order_id} placed</h4>
        <div class="meta">${data.order_type} · ${data.payment_method}</div>
        <div>${lines.join("\n")}</div>
        <div style="margin-top:8px"><strong>Total: Rs. ${data.total_price.toFixed(0)}</strong></div>
        ${data.delivery_address ? `<div class="meta" style="margin-top:6px">To: ${data.delivery_address}</div>` : ""}
        <div style="margin-top:8px">⏱ Estimated: ${data.estimated_time}</div>
      </div>`;
    form.reset();
    itemRows.innerHTML = "";
    addItemRow();
    updateTotal();
  } catch (err) {
    summary.innerHTML = `<div class="card error">Order failed: ${err.message}</div>`;
  } finally {
    $("#orderLoading").classList.add("hidden");
  }
});

/* ===================== Reservation form ===================== */

$("#reservationForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = {
    customer_name: form.customer_name.value.trim(),
    phone: form.phone.value.trim(),
    date: form.date.value,
    time: form.time.value,
    guests: +form.guests.value,
    special_requests: form.special_requests.value.trim() || null,
  };

  const result = $("#reservationResult");
  result.innerHTML = "";
  $("#reservationLoading").classList.remove("hidden");

  try {
    const res = await fetch(`${API}/reservation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    result.innerHTML = `
      <div class="card">
        <h4>📅 Reservation #${data.reservation_id} confirmed</h4>
        <div>${data.customer_name} · ${data.date} at ${data.time} · ${data.guests} guest(s)</div>
        ${data.special_requests ? `<div class="meta" style="margin-top:6px">Requests: ${data.special_requests}</div>` : ""}
        <div class="row right" style="margin-top:10px">
          <button class="btn small" id="cancelResBtn">Cancel this reservation</button>
        </div>
      </div>`;

    $("#cancelResBtn").addEventListener("click", async () => {
      const res2 = await fetch(`${API}/cancel-reservation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reservation_id: data.reservation_id, phone: data.phone }),
      });
      result.innerHTML = res2.ok
        ? `<div class="card">Reservation #${data.reservation_id} cancelled.</div>`
        : `<div class="card error">Cancellation failed.</div>`;
    });
    form.reset();
  } catch (err) {
    result.innerHTML = `<div class="card error">Booking failed: ${err.message}</div>`;
  } finally {
    $("#reservationLoading").classList.add("hidden");
  }
});

/* ===================== Order tracking ===================== */

$("#trackForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#trackQuery").value.trim();
  const results = $("#trackResults");
  results.innerHTML = "";
  $("#trackLoading").classList.remove("hidden");

  // A short pure number = order id; anything else = phone number
  const params = /^\d{1,6}$/.test(q)
    ? `order_id=${q}`
    : `phone=${encodeURIComponent(q)}`;

  try {
    const res = await fetch(`${API}/order-status?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);

    for (const o of data) {
      const badgeClass =
        o.status === "delivered" ? "delivered" : o.status === "cancelled" ? "cancelled" : "";
      const items = o.items.map((i) => `  • ${i.item ?? "item"} ×${i.qty ?? 1}`).join("\n");
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <h4>Order #${o.order_id} <span class="badge ${badgeClass}">${o.status_label.split("—")[0].trim()}</span></h4>
        <div class="meta">${o.order_type} · placed ${o.created_at} UTC</div>
        <div>${items}</div>
        <div style="margin-top:8px"><strong>Total: Rs. ${o.total_price.toFixed(0)}</strong></div>`;
      results.appendChild(card);
    }
  } catch (err) {
    results.innerHTML = `<div class="card error">${err.message}</div>`;
  } finally {
    $("#trackLoading").classList.add("hidden");
  }
});
