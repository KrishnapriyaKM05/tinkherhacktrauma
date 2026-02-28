/**
 * static/js/curve.js
 * ===================
 * Forgetting curve visualization using HTML5 Canvas (no libraries).
 *
 * WHAT IT DRAWS:
 * --------------
 * 1. Baseline decay curve     — purple line — fixed λ=0.1
 * 2. ML-learned decay curve   — teal line   — ML-adjusted λ
 * 3. Attempt scatter points   — orange dots — actual quiz scores
 * 4. Vertical "current time"  — dashed line — from slider
 * 5. Retention % at cursor    — tooltip overlay
 *
 * PIECEWISE STRUCTURE:
 * --------------------
 * The server returns pre-computed (t, retention) points for the full
 * piecewise curve. Each segment is a separate exponential decay with a
 * visible jump at each reattempt time. The frontend just plots the points.
 *
 * TECH:
 * -----
 * - Pure Canvas 2D API
 * - No chart libraries (Recharts, Chart.js, D3, etc.)
 * - Updates dynamically on slider input
 */

let currentTopic = "";
let curveData = null;  // Cached API response

/**
 * Initialize the curve viewer.
 * Called from the template with the current topic name.
 *
 * @param {string} topic - The study topic to display
 */
function initCurve(topic) {
    currentTopic = topic;
    const slider = document.getElementById("sim-slider");
    const label = document.getElementById("current-day-label");
    const canvas = document.getElementById("curve-canvas");

    if (!canvas || !slider) return;

    // Initial load
    fetchAndDraw(parseFloat(slider.value));

    // Update on slider change
    slider.addEventListener("input", function () {
        label.textContent = this.value;
        fetchAndDraw(parseFloat(this.value));
    });

    // Tooltip on mouse move
    canvas.addEventListener("mousemove", function (e) {
        if (curveData) drawTooltip(canvas, e, curveData);
    });
    canvas.addEventListener("mouseleave", function () {
        if (curveData) drawCurve(canvas, curveData, parseFloat(slider.value));
    });
}

/**
 * Fetch curve data from the API and redraw.
 *
 * @param {number} currentTime - Current slider value (simulated day)
 */
function fetchAndDraw(currentTime) {
    const url = `/api/curve/${encodeURIComponent(currentTopic)}?current_time=${currentTime}`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            curveData = data;
            updateInfoPanel(data);
            const canvas = document.getElementById("curve-canvas");
            drawCurve(canvas, data, currentTime);
        })
        .catch(err => {
            console.error("Failed to load curve data:", err);
            document.getElementById("curve-info").textContent = "Failed to load curve data.";
        });
}

/**
 * Main drawing function. Renders the full curve on the canvas.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Object} data - API response with baseline_curve, learned_curve, attempts
 * @param {number} currentTime - The current simulated time (for marker line)
 */
function drawCurve(canvas, data, currentTime) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;

    // Clear
    ctx.clearRect(0, 0, W, H);

    if (!data.has_data) {
        ctx.fillStyle = "#8891b8";
        ctx.font = "16px system-ui";
        ctx.textAlign = "center";
        ctx.fillText("No quiz attempts yet. Take a quiz to see your forgetting curve.", W / 2, H / 2);
        return;
    }

    const tMin = data.t_min;
    const tMax = data.t_max;
    const padding = { top: 30, right: 30, bottom: 50, left: 55 };
    const plotW = W - padding.left - padding.right;
    const plotH = H - padding.top - padding.bottom;

    // Coordinate mappers
    const tx = t => padding.left + ((t - tMin) / (tMax - tMin)) * plotW;
    const ty = r => padding.top + (1 - r) * plotH;

    // --- Draw grid ---
    ctx.strokeStyle = "#2e3150";
    ctx.lineWidth = 1;
    for (let r = 0; r <= 1.0; r += 0.2) {
        const y = ty(r);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(W - padding.right, y);
        ctx.stroke();
    }
    const dayStep = Math.ceil((tMax - tMin) / 10);
    for (let d = Math.ceil(tMin); d <= tMax; d += dayStep) {
        const x = tx(d);
        ctx.beginPath();
        ctx.moveTo(x, padding.top);
        ctx.lineTo(x, H - padding.bottom);
        ctx.stroke();
    }

    // --- Axes ---
    ctx.strokeStyle = "#8891b8";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, H - padding.bottom);
    ctx.lineTo(W - padding.right, H - padding.bottom);
    ctx.stroke();

    // --- Y-axis labels ---
    ctx.fillStyle = "#8891b8";
    ctx.font = "12px system-ui";
    ctx.textAlign = "right";
    for (let r = 0; r <= 1.0; r += 0.2) {
        ctx.fillText((r * 100).toFixed(0) + "%", padding.left - 6, ty(r) + 4);
    }

    // --- X-axis labels ---
    ctx.textAlign = "center";
    for (let d = Math.ceil(tMin); d <= tMax; d += dayStep) {
        ctx.fillText("Day " + d, tx(d), H - padding.bottom + 18);
    }

    // --- Axis titles ---
    ctx.fillStyle = "#8891b8";
    ctx.font = "12px system-ui";
    ctx.textAlign = "center";
    ctx.fillText("Simulated Time (days)", W / 2, H - 5);
    ctx.save();
    ctx.translate(14, H / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Memory Retention", 0, 0);
    ctx.restore();

    // --- Draw baseline curve (purple) ---
    drawLine(ctx, data.baseline_curve, tMin, tMax, plotW, plotH, padding, "#6c63ff", 2.5);

    // --- Draw learned curve (teal) ---
    drawLine(ctx, data.learned_curve, tMin, tMax, plotW, plotH, padding, "#00d9a3", 2.5);

    // --- Draw current time marker ---
    if (currentTime >= tMin && currentTime <= tMax) {
        const cx = tx(currentTime);
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = "#ffb347";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx, padding.top);
        ctx.lineTo(cx, H - padding.bottom);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        ctx.fillStyle = "#ffb347";
        ctx.font = "11px system-ui";
        ctx.textAlign = "center";
        ctx.fillText("Now", cx, padding.top - 8);
    }

    // --- Draw attempt scatter points ---
    data.attempts.forEach(a => {
        const x = tx(a.t);
        const y = ty(a.score_pct);
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = "#ffb347";
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
    });
}

/**
 * Draw a polyline from a list of {t, retention} points.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array} points - [{t, retention}, ...]
 * @param {number} tMin, tMax - Time range
 * @param {number} plotW, plotH - Plot dimensions
 * @param {Object} padding - Padding object
 * @param {string} color - Stroke color
 * @param {number} lineWidth
 */
function drawLine(ctx, points, tMin, tMax, plotW, plotH, padding, color, lineWidth) {
    if (!points || points.length === 0) return;

    const tx = t => padding.left + ((t - tMin) / (tMax - tMin)) * plotW;
    const ty = r => padding.top + (1 - r) * plotH;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = "round";

    let first = true;
    for (let i = 0; i < points.length; i++) {
        const p = points[i];
        const x = tx(p.t);
        const y = ty(p.retention);

        // Detect jumps (piecewise segments): large retention increase = new segment
        if (!first && i > 0) {
            const prevR = points[i - 1].retention;
            const currR = p.retention;
            if (currR - prevR > 0.05) {
                // End current path and start new one (the "jump")
                ctx.stroke();
                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.lineWidth = lineWidth;
            }
        }

        if (first) {
            ctx.moveTo(x, y);
            first = false;
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
}

/**
 * Draw a tooltip showing retention at the mouse position.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {MouseEvent} e
 * @param {Object} data - Curve data from API
 */
function drawTooltip(canvas, e, data) {
    if (!data.has_data) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const mouseX = (e.clientX - rect.left) * scaleX;

    const padding = { top: 30, right: 30, bottom: 50, left: 55 };
    const tMin = data.t_min;
    const tMax = data.t_max;
    const plotW = canvas.width - padding.left - padding.right;

    // Convert mouse X to simulated time
    const t = tMin + ((mouseX - padding.left) / plotW) * (tMax - tMin);
    if (t < tMin || t > tMax) return;

    // Lookup retention from learned curve
    const pt = _nearestPoint(data.learned_curve, t);
    const basePt = _nearestPoint(data.baseline_curve, t);

    // Redraw then overlay tooltip
    const slider = document.getElementById("sim-slider");
    drawCurve(canvas, data, parseFloat(slider.value));

    const ctx = canvas.getContext("2d");
    const tx = t => padding.left + ((t - tMin) / (tMax - tMin)) * plotW;
    const px = tx(t);

    // Vertical line
    ctx.strokeStyle = "rgba(255,255,255,0.3)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(px, padding.top);
    ctx.lineTo(px, canvas.height - padding.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    // Tooltip box
    if (pt) {
        const boxX = px + 8;
        const boxY = 40;
        const text1 = `Day ${t.toFixed(1)}`;
        const text2 = `Learned: ${(pt.retention * 100).toFixed(1)}%`;
        const text3 = basePt ? `Baseline: ${(basePt.retention * 100).toFixed(1)}%` : "";

        ctx.fillStyle = "rgba(26, 29, 46, 0.95)";
        ctx.strokeStyle = "#6c63ff";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(boxX, boxY, 160, text3 ? 60 : 45, 6);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#e8eaf6";
        ctx.font = "bold 12px system-ui";
        ctx.textAlign = "left";
        ctx.fillText(text1, boxX + 10, boxY + 17);
        ctx.font = "12px system-ui";
        ctx.fillStyle = "#00d9a3";
        ctx.fillText(text2, boxX + 10, boxY + 33);
        if (text3) {
            ctx.fillStyle = "#6c63ff";
            ctx.fillText(text3, boxX + 10, boxY + 49);
        }
    }
}

/**
 * Find the nearest point in a curve array to a given time t.
 *
 * @param {Array} curve - [{t, retention}, ...]
 * @param {number} t
 * @returns {Object|null}
 */
function _nearestPoint(curve, t) {
    if (!curve || curve.length === 0) return null;
    let best = null;
    let bestDist = Infinity;
    for (const p of curve) {
        const d = Math.abs(p.t - t);
        if (d < bestDist) {
            bestDist = d;
            best = p;
        }
    }
    return best;
}

/**
 * Update the info panel below the canvas.
 *
 * @param {Object} data - API response
 */
function updateInfoPanel(data) {
    const panel = document.getElementById("curve-info");
    if (!panel) return;

    if (!data.has_data) {
        panel.innerHTML = "<p>No data yet. Take a quiz to generate your first curve.</p>";
        return;
    }

    panel.innerHTML = `
        <strong>Baseline λ:</strong> ${data.baseline_lambda.toFixed(4)} &nbsp;|&nbsp;
        <strong>ML-Learned λ:</strong> ${data.learned_lambda.toFixed(4)} &nbsp;|&nbsp;
        <strong>Attempts:</strong> ${data.attempts.length} &nbsp;|&nbsp;
        <strong>Segments:</strong> ${data.segments.length}
        ${data.learned_lambda !== data.baseline_lambda
            ? `<br><small>ML has adjusted your decay rate based on ${data.attempts.length} historical attempt(s).</small>`
            : `<small> — Need 2+ attempts to personalize the decay rate.</small>`}
    `;
}
