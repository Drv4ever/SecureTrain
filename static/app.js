// SecureTrain - Frontend Logic with Step-by-Step 10-Round Animated Process

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentEmployeeId = null;
  let currentSessionId = null;
  let currentMode = "simulated"; // "simulated" | "live"
  let currentRoundNumber = 0;
  let pendingRoundNumber = null;
  let chartInstance = null;
  let isRunning = false;
  let isSimLoopRunning = false;
  let stopLoopRequested = false;

  // DOM Elements
  const employeeSelect = document.getElementById("employee-select");
  const modeSimulatedBtn = document.getElementById("mode-simulated");
  const modeLiveBtn = document.getElementById("mode-live");
  const btnRun10 = document.getElementById("btn-run-10");
  const btnRunRound = document.getElementById("btn-run-round");
  const btnRunBatch = document.getElementById("btn-run-batch");
  const btnReset = document.getElementById("btn-reset");
  const run10Text = document.getElementById("run-10-text");
  const runBtnText = document.getElementById("run-btn-text");
  const spinner10 = document.getElementById("spinner-10");
  const spinnerSingle = document.getElementById("spinner-single");
  const spinnerBatch = document.getElementById("spinner-batch");
  const simRunBadge = document.getElementById("sim-run-badge");

  // Center scenario elements
  const roundIndicator = document.getElementById("round-indicator");
  const emailCard = document.getElementById("email-card");
  const emailAvatar = document.getElementById("email-avatar");
  const emailSenderName = document.getElementById("email-sender-name");
  const emailSenderEmail = document.getElementById("email-sender-email");
  const emailSubject = document.getElementById("email-subject");
  const emailBody = document.getElementById("email-body");
  const emailIndicatorsBox = document.getElementById("email-indicators-box");
  const indicatorsList = document.getElementById("indicators-list");
  const liveButtons = document.getElementById("live-buttons");
  const simFeed = document.getElementById("sim-feed");
  const simStatusBadge = document.getElementById("sim-status-badge");
  const simTacticTag = document.getElementById("sim-tactic-tag");
  const simReactionMsg = document.getElementById("sim-reaction-msg");

  // Summary and Stats
  const topWeakness = document.getElementById("top-weakness");
  const topWeaknessDetail = document.getElementById("top-weakness-detail");
  const statTotalRounds = document.getElementById("stat-total-rounds");
  const statCumReward = document.getElementById("stat-cum-reward");
  const statAdvantage = document.getElementById("stat-advantage");

  const tactics = ["urgency", "authority", "invoice", "credential"];

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // Initialize Chart.js
  function initChart() {
    const ctx = document.getElementById("learningChart").getContext("2d");
    chartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Thompson Sampling (Adaptive)",
            data: [],
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.1)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.2,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
          {
            label: "Random Baseline (Expected)",
            data: [],
            borderColor: "#94a3b8",
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: { boxWidth: 12, font: { size: 11, weight: "600" } },
          },
          tooltip: {
            callbacks: {
              label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(2)}`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: "Rounds", font: { size: 11 } },
            grid: { display: false },
          },
          y: {
            title: { display: true, text: "Cumulative Detection Reward", font: { size: 11 } },
            beginAtZero: true,
            grid: { color: "#f1f5f9" },
          },
        },
      },
    });
  }

  // Stepper Visual Process Helper
  function setStep(stepNum) {
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById(`step-${i}`);
      if (!el) continue;
      el.classList.remove("active", "completed");
      if (i < stepNum) el.classList.add("completed");
      else if (i === stepNum) el.classList.add("active");
    }
  }

  function resetStepper() {
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById(`step-${i}`);
      if (el) el.classList.remove("active", "completed");
    }
  }

  // Highlight Selected Arm on Left Panel
  function highlightTactic(chosenTactic) {
    tactics.forEach((t) => {
      const itemEl = document.getElementById(`belief-item-${t}`);
      const calloutEl = document.getElementById(`callout-${t}`);
      if (itemEl) itemEl.classList.remove("selected-arm");
      if (calloutEl) calloutEl.classList.add("hidden");
    });

    if (chosenTactic) {
      const itemEl = document.getElementById(`belief-item-${chosenTactic}`);
      const calloutEl = document.getElementById(`callout-${chosenTactic}`);
      if (itemEl) itemEl.classList.add("selected-arm");
      if (calloutEl) {
        calloutEl.textContent = `🎯 Selected for Round`;
        calloutEl.classList.remove("hidden");
      }
    }
  }

  // Update Belief Bars
  function updateBeliefBars(banditState) {
    let highestArm = null;
    let highestMean = -1;

    tactics.forEach((tactic) => {
      const arm = banditState[tactic] || { alpha: 1.0, beta: 1.0, pulls: 0, mean: 0.5 };
      const mean = arm.mean !== undefined ? arm.mean : arm.alpha / (arm.alpha + arm.beta);
      const pct = Math.round(mean * 100);

      const scoreEl = document.getElementById(`score-${tactic}`);
      const barEl = document.getElementById(`bar-${tactic}`);
      const statsEl = document.getElementById(`stats-${tactic}`);
      const riskEl = document.getElementById(`risk-${tactic}`);

      if (scoreEl) scoreEl.textContent = `${pct}%`;
      if (statsEl) statsEl.textContent = `α: ${arm.alpha.toFixed(1)} | β: ${arm.beta.toFixed(1)} (${arm.pulls} pulls)`;

      if (barEl) {
        barEl.style.width = `${pct}%`;
        barEl.className = "bar-fill " + getRiskClass(mean);
      }

      if (riskEl) {
        riskEl.textContent = getRiskText(mean);
        riskEl.style.color = getRiskColor(mean);
      }

      if (mean > highestMean) {
        highestMean = mean;
        highestArm = tactic;
      }
    });

    if (highestArm && highestMean > 0.5) {
      topWeakness.textContent = highestArm.toUpperCase();
      topWeakness.style.color = getRiskColor(highestMean);
      topWeaknessDetail.textContent = `Susceptibility score: ${(highestMean * 100).toFixed(0)}% (dominant learning signal)`;
    } else {
      topWeakness.textContent = "EXPLORING";
      topWeakness.style.color = "#64748b";
      topWeaknessDetail.textContent = "Agent is gathering initial observations across tactics";
    }
  }

  function getRiskClass(mean) {
    if (mean < 0.38) return "risk-low";
    if (mean < 0.62) return "risk-medium";
    return "risk-high";
  }

  function getRiskText(mean) {
    if (mean < 0.38) return "Low Risk";
    if (mean < 0.62) return "Moderate";
    return "High Vulnerability";
  }

  function getRiskColor(mean) {
    if (mean < 0.38) return "#10b981";
    if (mean < 0.62) return "#f59e0b";
    return "#ef4444";
  }

  function setShimmer(active) {
    document.querySelectorAll(".belief-item").forEach((el) => {
      if (active) el.classList.add("active-pulse");
      else el.classList.remove("active-pulse");
    });
  }

  // Load Employees
  async function loadEmployees() {
    try {
      const res = await fetch("/api/employees");
      const emps = await res.json();
      employeeSelect.innerHTML = "";
      emps.forEach((emp) => {
        const opt = document.createElement("option");
        opt.value = emp.id;
        opt.textContent = emp.name;
        employeeSelect.appendChild(opt);
      });
      if (emps.length > 0) {
        currentEmployeeId = emps[0].id;
        await startNewSession(currentEmployeeId);
      }
    } catch (err) {
      console.error("Failed to load employees:", err);
    }
  }

  // Start Session
  async function startNewSession(empId) {
    if (!empId) return;
    if (isSimLoopRunning) {
      stopLoopRequested = true;
      await sleep(200);
    }
    try {
      const res = await fetch("/api/session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: empId,
          selector: "thompson",
          mode: currentMode,
        }),
      });
      const session = await res.json();
      currentSessionId = session.id;
      currentRoundNumber = 0;
      pendingRoundNumber = null;
      resetUI();
      updateBeliefBars(session.bandit_state);
    } catch (err) {
      console.error("Failed to start session:", err);
    }
  }

  function resetUI() {
    roundIndicator.textContent = "Round 0";
    simRunBadge.classList.add("hidden");
    resetStepper();
    highlightTactic(null);

    emailAvatar.textContent = "IT";
    emailSenderName.textContent = "System Security Desk";
    emailSenderEmail.textContent = "<security-alert@internal-gateway.example.com>";
    emailSubject.textContent = "Select an employee and click 'Run 10 Rounds (Animated)' or 'Run 1 Round'";
    emailBody.innerHTML = `<p class="placeholder-text">The adaptive bandit will select a tailored tactic and present an authentic contextual phishing email here.</p>`;
    emailIndicatorsBox.style.display = "none";
    liveButtons.style.display = "none";

    simStatusBadge.className = "feed-badge";
    simStatusBadge.textContent = "Ready";
    simTacticTag.textContent = "No round active";
    simReactionMsg.innerHTML = "Click <strong>Run 10 Rounds (Animated)</strong> to watch the AI test and learn weaknesses step-by-step.";

    statTotalRounds.textContent = "0";
    statCumReward.textContent = "0.0";
    statAdvantage.textContent = "+0.0";

    if (chartInstance) {
      chartInstance.data.labels = [];
      chartInstance.data.datasets[0].data = [];
      chartInstance.data.datasets[1].data = [];
      chartInstance.update();
    }
  }

  // Refresh Session State & Chart
  async function refreshSessionState() {
    if (!currentSessionId) return;
    try {
      const res = await fetch(`/api/session/${currentSessionId}/state`);
      const state = await res.json();

      updateBeliefBars(state.bandit_state);
      statTotalRounds.textContent = state.total_rounds;
      statCumReward.textContent = state.cumulative_reward.toFixed(1);

      // Update Chart data
      if (chartInstance && state.history) {
        const labels = state.history.map((h) => h.round_number);
        const tsData = state.history.map((h) => h.cumulative_reward);
        const baseData = state.baseline_cumulative || [];

        chartInstance.data.labels = labels;
        chartInstance.data.datasets[0].data = tsData;
        chartInstance.data.datasets[1].data = baseData;
        chartInstance.update();

        if (tsData.length > 0 && baseData.length > 0) {
          const lastTs = tsData[tsData.length - 1];
          const lastBase = baseData[baseData.length - 1];
          const adv = lastTs - lastBase;
          statAdvantage.textContent = (adv >= 0 ? "+" : "") + adv.toFixed(1);
          statAdvantage.style.color = adv >= 0 ? "#10b981" : "#ef4444";
        }
      }
    } catch (err) {
      console.error("Failed to refresh state:", err);
    }
  }

  // Render Scenario Email
  function renderScenario(scenario) {
    if (!scenario) return;
    const initial = (scenario.sender_name || "S").substring(0, 2).toUpperCase();
    emailAvatar.textContent = initial;
    emailSenderName.textContent = scenario.sender_name;
    emailSenderEmail.textContent = `<${scenario.sender_email}>`;
    emailSubject.textContent = scenario.subject;
    emailBody.textContent = scenario.body;

    if (scenario.indicators && scenario.indicators.length > 0) {
      indicatorsList.innerHTML = "";
      scenario.indicators.forEach((ind) => {
        const li = document.createElement("li");
        li.textContent = ind;
        indicatorsList.appendChild(li);
      });
      emailIndicatorsBox.style.display = "block";
    } else {
      emailIndicatorsBox.style.display = "none";
    }

    emailCard.classList.add("highlight-scenario");
    setTimeout(() => emailCard.classList.remove("highlight-scenario"), 600);
  }

  // Render Simulated Response Feedback
  function renderSimulatedResponse(round) {
    const tactic = round.tactic_selected;
    const resp = round.response;
    simTacticTag.textContent = `Tested Tactic: ${tactic.toUpperCase()}`;

    if (resp === "report") {
      simStatusBadge.className = "feed-badge badge-success";
      simStatusBadge.textContent = "Reported (Safe)";
      simReactionMsg.innerHTML = `🛡️ Employee recognized suspicious <strong>${tactic}</strong> indicators and <strong>REPORTED</strong> the email. (Detection reward: +0.0, Safety score: +1.0)`;
    } else if (resp === "ignore") {
      simStatusBadge.className = "feed-badge badge-warning";
      simStatusBadge.textContent = "Ignored";
      simReactionMsg.innerHTML = `👁️ Employee ignored/deleted the <strong>${tactic}</strong> email. (Detection reward: +0.3, Safety score: +0.6)`;
    } else if (resp === "click") {
      simStatusBadge.className = "feed-badge badge-danger";
      simStatusBadge.textContent = "Link Clicked";
      simReactionMsg.innerHTML = `⚠️ Employee fell for the <strong>${tactic}</strong> lure and <strong>CLICKED</strong> the link. (Detection reward: +0.7, Safety score: +0.2)`;
    } else if (resp === "credentials") {
      simStatusBadge.className = "feed-badge badge-danger";
      simStatusBadge.textContent = "Credentials Entered";
      simReactionMsg.innerHTML = `🚨 Employee entered credentials on the fake login portal! Strongest vulnerability signal for <strong>${tactic}</strong>. (Detection reward: +1.0, Safety score: +0.0)`;
    }
  }

  // Execute a single animated round through the 4-step pipeline
  async function executeAnimatedRound(roundIndex, totalRounds) {
    if (!currentSessionId) return null;

    // Display round progress banner
    simRunBadge.classList.remove("hidden");
    simRunBadge.textContent = `Simulating: Round ${roundIndex} of ${totalRounds}`;

    // Step 1: Model Choice & Sampling
    setStep(1);
    setShimmer(true);

    const res = await fetch(`/api/session/${currentSessionId}/round`, { method: "POST" });
    const round = await res.json();
    currentRoundNumber = round.round_number;
    roundIndicator.textContent = `Round ${round.round_number}`;

    const chosenTactic = round.tactic_selected;
    highlightTactic(chosenTactic);
    simTacticTag.textContent = `AI Sampling: Selected ${chosenTactic.toUpperCase()}`;
    await sleep(350);

    // Step 2: Contextual Scenario Generation & Presentation
    setStep(2);
    setShimmer(false);
    renderScenario(round.scenario);
    await sleep(400);

    // Step 3: Employee Reaction
    setStep(3);
    renderSimulatedResponse(round);
    await sleep(400);

    // Step 4: AI Learning & Posterior Update
    setStep(4);
    if (round.bandit_state_after) {
      updateBeliefBars(round.bandit_state_after);
    }
    await refreshSessionState();
    await sleep(300);

    return round;
  }

  // Run 10-Round Animated Simulation Loop
  async function handleRun10Simulation() {
    if (isSimLoopRunning) {
      // User clicked stop/pause
      stopLoopRequested = true;
      run10Text.textContent = "Stopping...";
      btnRun10.disabled = true;
      return;
    }

    if (!currentSessionId || isRunning) return;
    isSimLoopRunning = true;
    stopLoopRequested = false;
    btnRun10.classList.remove("btn-accent");
    btnRun10.classList.add("btn-outline");
    run10Text.textContent = "⏸ Pause Simulation";
    spinner10.classList.remove("hidden");
    btnRunRound.disabled = true;
    btnRunBatch.disabled = true;

    try {
      for (let r = 1; r <= 10; r++) {
        if (stopLoopRequested) break;
        await executeAnimatedRound(r, 10);
      }

      simRunBadge.classList.remove("hidden");
      simRunBadge.textContent = "10-Round Simulation Complete!";
      setTimeout(() => simRunBadge.classList.add("hidden"), 3500);
      highlightTactic(null);
      resetStepper();
    } catch (err) {
      console.error("10-Round simulation error:", err);
    } finally {
      isSimLoopRunning = false;
      stopLoopRequested = false;
      spinner10.classList.add("hidden");
      btnRun10.classList.add("btn-accent");
      btnRun10.classList.remove("btn-outline");
      btnRun10.disabled = false;
      run10Text.textContent = "▶ Run 10 Rounds (Animated)";
      btnRunRound.disabled = false;
      btnRunBatch.disabled = false;
      setShimmer(false);
    }
  }

  // Run Single Round
  async function handleRunRound() {
    if (!currentSessionId || isRunning || isSimLoopRunning) return;
    isRunning = true;
    spinnerSingle.classList.remove("hidden");
    btnRunRound.disabled = true;
    btnRun10.disabled = true;

    try {
      if (currentMode === "simulated") {
        await executeAnimatedRound(1, 1);
        setTimeout(() => {
          highlightTactic(null);
          resetStepper();
          simRunBadge.classList.add("hidden");
        }, 1500);
      } else {
        // Live Mode
        setStep(1);
        setShimmer(true);
        const res = await fetch(`/api/session/${currentSessionId}/round`, { method: "POST" });
        const round = await res.json();
        currentRoundNumber = round.round_number;
        roundIndicator.textContent = `Round ${round.round_number}`;

        setStep(2);
        highlightTactic(round.tactic_selected);
        renderScenario(round.scenario);

        pendingRoundNumber = round.round_number;
        liveButtons.style.display = "block";
        simFeed.style.display = "none";
        setStep(3);
      }
    } catch (err) {
      console.error("Round execution failed:", err);
    } finally {
      isRunning = false;
      spinnerSingle.classList.add("hidden");
      btnRunRound.disabled = false;
      btnRun10.disabled = false;
      setShimmer(false);
    }
  }

  // Handle Human Live Response
  async function handleHumanResponse(responseAction) {
    if (!currentSessionId || !pendingRoundNumber) return;
    try {
      setStep(4);
      const res = await fetch(`/api/session/${currentSessionId}/round/${pendingRoundNumber}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: responseAction }),
      });
      const round = await res.json();
      liveButtons.style.display = "none";
      simFeed.style.display = "flex";
      renderSimulatedResponse(round);
      pendingRoundNumber = null;
      await refreshSessionState();
      setTimeout(() => {
        highlightTactic(null);
        resetStepper();
      }, 1500);
    } catch (err) {
      console.error("Failed to submit human response:", err);
    }
  }

  // Run Batch (50 Rounds)
  async function handleRunBatch() {
    if (!currentSessionId || isRunning || isSimLoopRunning) return;
    isRunning = true;
    spinnerBatch.classList.remove("hidden");
    btnRunBatch.disabled = true;
    btnRunRound.disabled = true;
    btnRun10.disabled = true;
    setShimmer(true);

    try {
      const res = await fetch(`/api/session/${currentSessionId}/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rounds: 50 }),
      });
      const summary = await res.json();
      roundIndicator.textContent = `Round ${summary.total_rounds}`;
      simStatusBadge.className = "feed-badge badge-success";
      simStatusBadge.textContent = "Fast 50 Completed";
      simReactionMsg.innerHTML = `Ran <strong>50 simulated rounds</strong> rapidly. Updated posteriors and cumulative detection reward to <strong>${summary.cumulative_reward.toFixed(1)}</strong>.`;
      await refreshSessionState();
    } catch (err) {
      console.error("Batch run failed:", err);
    } finally {
      isRunning = false;
      spinnerBatch.classList.add("hidden");
      btnRunBatch.disabled = false;
      btnRunRound.disabled = false;
      btnRun10.disabled = false;
      setShimmer(false);
    }
  }

  // Event Listeners
  employeeSelect.addEventListener("change", (e) => {
    currentEmployeeId = parseInt(e.target.value, 10);
    startNewSession(currentEmployeeId);
  });

  modeSimulatedBtn.addEventListener("click", () => {
    if (currentMode === "simulated") return;
    currentMode = "simulated";
    modeSimulatedBtn.classList.add("active");
    modeLiveBtn.classList.remove("active");
    btnRun10.style.display = "inline-flex";
    btnRunBatch.style.display = "inline-flex";
    runBtnText.textContent = "Run 1 Round";
    startNewSession(currentEmployeeId);
  });

  modeLiveBtn.addEventListener("click", () => {
    if (currentMode === "live") return;
    currentMode = "live";
    modeLiveBtn.classList.add("active");
    modeSimulatedBtn.classList.remove("active");
    btnRun10.style.display = "none";
    btnRunBatch.style.display = "none";
    runBtnText.textContent = "Next Phish";
    startNewSession(currentEmployeeId);
  });

  btnRun10.addEventListener("click", handleRun10Simulation);
  btnRunRound.addEventListener("click", handleRunRound);
  btnRunBatch.addEventListener("click", handleRunBatch);
  btnReset.addEventListener("click", () => startNewSession(currentEmployeeId));

  // Live action buttons
  document.querySelectorAll(".action-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const action = e.currentTarget.getAttribute("data-action");
      handleHumanResponse(action);
    });
  });

  // Init
  initChart();
  loadEmployees();
});
