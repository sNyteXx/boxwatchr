var TEXT_OPERATORS_HTML = '<option value="equals">equals</option><option value="not_equals">does not equal</option><option value="contains">contains</option><option value="not_contains">does not contain</option><option value="is_empty">is empty</option>';
var NUMERIC_OPERATORS_HTML = '<option value="greater_than">greater than</option><option value="less_than">less than</option><option value="greater_than_or_equal">greater than or equal</option><option value="less_than_or_equal">less than or equal</option>';

function onFieldChange(select) {
    var row = select.closest(".condition-row");
    var operatorSelect = row.querySelector(".cond-operator");
    var textInput = row.querySelector(".value-text");
    var boolSelect = row.querySelector(".value-bool");
    var isNumeric = select.value === "rspamd_score" || select.value === "email_age_days";

    operatorSelect.innerHTML = isNumeric ? NUMERIC_OPERATORS_HTML : TEXT_OPERATORS_HTML;

    if (isNumeric) {
        textInput.disabled = false;
        textInput.classList.remove("d-none");
        boolSelect.disabled = true;
        boolSelect.classList.add("d-none");
    } else {
        onOperatorChange(operatorSelect);
    }
}

function onOperatorChange(select) {
    var row = select.closest(".condition-row");
    var textInput = row.querySelector(".value-text");
    var boolSelect = row.querySelector(".value-bool");
    var isEmpty = select.value === "is_empty";
    textInput.disabled = isEmpty;
    textInput.classList.toggle("d-none", isEmpty);
    boolSelect.disabled = !isEmpty;
    boolSelect.classList.toggle("d-none", !isEmpty);
}

function onActionTypeChange(select) {
    var row = select.closest(".action-row");
    var destInput = row.querySelector(".action-dest");
    var webhookInput = row.querySelector(".action-webhook");
    var isMove = select.value === "move";
    var isDiscord = select.value === "notify_discord";
    destInput.classList.toggle("d-none", !isMove);
    destInput.disabled = !isMove;
    if (webhookInput) {
        webhookInput.classList.toggle("d-none", !isDiscord);
        webhookInput.disabled = !isDiscord;
    }
}

function removeCondition(btn) {
    btn.closest(".condition-row").remove();
    updateEmptyNotice("conditions-container", "conditions-empty");
}

function removeAction(btn) {
    btn.closest(".action-row").remove();
    updateEmptyNotice("actions-container", "actions-empty");
}

function updateEmptyNotice(containerId, noticeId) {
    var container = document.getElementById(containerId);
    var notice = document.getElementById(noticeId);
    if (!notice) return;
    notice.classList.toggle("d-none", container.children.length > 0);
}

function addCondition() {
    var template = document.getElementById("condition-template");
    var clone = template.content.cloneNode(true);
    document.getElementById("conditions-container").appendChild(clone);
    var notice = document.getElementById("conditions-empty");
    if (notice) notice.classList.add("d-none");
}

function addAction() {
    var template = document.getElementById("action-template");
    var clone = template.content.cloneNode(true);
    var typeSelect = clone.querySelector("[name='action_type']");
    onActionTypeChange(typeSelect);
    document.getElementById("actions-container").appendChild(clone);
    var notice = document.getElementById("actions-empty");
    if (notice) notice.classList.add("d-none");
}

document.addEventListener("DOMContentLoaded", function() {
    var condContainer = document.getElementById("conditions-container");
    if (condContainer) {
        condContainer.addEventListener("change", function(e) {
            if (e.target.classList.contains("cond-field")) {
                onFieldChange(e.target);
            } else if (e.target.classList.contains("cond-operator")) {
                onOperatorChange(e.target);
            }
        });
        condContainer.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-action='remove-condition']");
            if (btn) removeCondition(btn);
        });
    }

    var actionsContainer = document.getElementById("actions-container");
    if (actionsContainer) {
        actionsContainer.addEventListener("change", function(e) {
            if (e.target.classList.contains("action-type")) {
                onActionTypeChange(e.target);
            }
        });
        actionsContainer.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-action='remove-action']");
            if (btn) removeAction(btn);
        });
    }

    var addCondBtn = document.querySelector("[data-action='add-condition']");
    if (addCondBtn) addCondBtn.addEventListener("click", addCondition);

    var addActBtn = document.querySelector("[data-action='add-action']");
    if (addActBtn) addActBtn.addEventListener("click", addAction);

    // Simulation
    function esc(s) {
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    var simBtn = document.getElementById("simulate-btn");
    if (simBtn) {
        simBtn.addEventListener("click", function() {
            var overlay = document.getElementById("simulate-overlay");
            var loading = document.getElementById("simulate-loading");
            var results = document.getElementById("simulate-results");
            var errorDiv = document.getElementById("simulate-error");

            overlay.classList.remove("d-none");
            loading.classList.remove("d-none");
            results.classList.add("d-none");
            errorDiv.classList.add("d-none");

            var form = document.querySelector("form[method='post']");
            var name = form.querySelector("[name='name']").value || "Simulation";
            var match = form.querySelector("[name='match']").value || "all";

            var condRows = form.querySelectorAll(".condition-row");
            var conditions = [];
            condRows.forEach(function(row) {
                var field = row.querySelector("[name='condition_field']");
                var op = row.querySelector("[name='condition_operator']:not(:disabled)");
                var valText = row.querySelector(".value-text");
                var valBool = row.querySelector(".value-bool");
                if (field && field.value) {
                    var val = "";
                    if (valText && !valText.disabled) val = valText.value;
                    else if (valBool && !valBool.disabled) val = valBool.value;
                    conditions.push({
                        field: field.value,
                        operator: op ? op.value : "",
                        value: val
                    });
                }
            });

            var actionRows = form.querySelectorAll(".action-row");
            var actions = [];
            actionRows.forEach(function(row) {
                var at = row.querySelector("[name='action_type']");
                if (at && at.value) {
                    var a = {type: at.value};
                    if (at.value === "move") {
                        var dest = row.querySelector("[name='action_destination']");
                        if (dest) a.destination = dest.value;
                    }
                    if (at.value === "notify_discord") {
                        var wh = row.querySelector("[name='action_webhook_url']");
                        if (wh) a.webhook_url = wh.value;
                    }
                    actions.push(a);
                }
            });

            var csrf = document.querySelector("meta[name='csrf-token']");
            var csrfToken = csrf ? csrf.content : "";

            fetch("/api/rules/simulate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    name: name,
                    match: match,
                    conditions: conditions,
                    actions: actions.length ? actions : [{type: "mark_read"}]
                })
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                loading.classList.add("d-none");
                if (data.error) {
                    errorDiv.textContent = data.error;
                    errorDiv.classList.remove("d-none");
                    return;
                }
                results.classList.remove("d-none");
                document.getElementById("sim-total").textContent = data.total_emails;
                document.getElementById("sim-matched").textContent = data.matched;
                var rate = data.total_emails > 0 ? (data.matched / data.total_emails * 100).toFixed(1) : "0";
                document.getElementById("sim-rate").textContent = rate + "%";

                var preview = document.getElementById("sim-preview");
                if (data.matched_emails && data.matched_emails.length > 0) {
                    var html = '<table class="table table-sm mb-0"><thead><tr><th>Sender</th><th>Subject</th><th>Date</th><th>Score</th></tr></thead><tbody>';
                    data.matched_emails.forEach(function(e) {
                        var score = e.spam_score != null ? Number(e.spam_score).toFixed(1) : "\u2014";
                        html += "<tr><td class=\"small\">" + esc(e.sender || "\u2014") + "</td><td class=\"small text-truncate\" style=\"max-width:200px\">" + esc(e.subject || "\u2014") + "</td><td class=\"small text-nowrap\">" + esc(e.date_received || "\u2014") + "</td><td class=\"small\">" + esc(score) + "</td></tr>";
                    });
                    html += "</tbody></table>";
                    if (data.matched > 50) html += '<p class="text-secondary small mt-2 mb-0">Showing 50 of ' + data.matched + " matches.</p>";
                    preview.innerHTML = html;
                } else {
                    preview.innerHTML = '<p class="text-secondary small mb-0">No emails matched this rule.</p>';
                }
            })
            .catch(function(err) {
                loading.classList.add("d-none");
                errorDiv.textContent = "Simulation failed: " + err.message;
                errorDiv.classList.remove("d-none");
            });
        });

        var closeBtn = document.getElementById("simulate-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", function() {
                document.getElementById("simulate-overlay").classList.add("d-none");
            });
        }
    }
});
