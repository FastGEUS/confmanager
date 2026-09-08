const $ = (selector) => document.querySelector(selector);
let token = sessionStorage.getItem("confmanager-token") || "";
let user = null;
const statuses = {new: "Новая", under_review: "На рассмотрении", accepted: "Принята", rejected: "Отклонена"};

function message(text, error = false) {
  $("#message").textContent = text;
  $("#message").className = error ? "error" : "success";
}

function resetSession() {
  token = "";
  user = null;
  sessionStorage.removeItem("confmanager-token");
  $("#workspace").hidden = true;
  $("#auth-panels").hidden = false;
  $("#logout").hidden = true;
  $("#applications-body").replaceChildren();
}

async function api(path, options = {}) {
  const headers = {...options.headers};
  if (token) headers.Authorization = "Bearer " + token;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const response = await fetch(path, {...options, headers});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") resetSession();
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.loc.join(".") + ": " + item.msg).join("; ")
      : data.detail;
    throw new Error(detail || "Не удалось выполнить запрос");
  }
  return data;
}

function cell(row, text) {
  const element = document.createElement("td");
  element.textContent = text;
  row.append(element);
  return element;
}

function action(parent, label, callback) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await callback();
      await loadApplications();
      message("Изменения сохранены");
    } catch (error) {
      message(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  parent.append(button);
}

async function loadApplications() {
  const applications = await api("/applications");
  const body = $("#applications-body");
  body.replaceChildren();
  $("#empty-state").hidden = applications.length > 0;
  $("#applications-table").hidden = applications.length === 0;
  for (const application of applications) {
    const row = document.createElement("tr");
    cell(row, application.id);
    cell(row, "#" + application.participant_id);
    cell(row, application.topic);
    const statusCell = cell(row, "");
    const badge = document.createElement("span");
    badge.className = "status " + application.status;
    badge.textContent = statuses[application.status];
    statusCell.append(badge);
    const fee = application.fee;
    cell(row, fee ? Number(fee.amount).toLocaleString("ru-RU", {minimumFractionDigits: 2})
      + " ₽ · " + (fee.status === "paid" ? "Оплачен" : "Не оплачен") : "Не назначен");
    const actions = cell(row, user.role === "committee" ? "" : "—");
    if (user.role === "committee") {
      if (!fee || fee.status !== "paid") {
        for (const status of ["under_review", "accepted", "rejected"]) {
          if (status === application.status) continue;
          action(actions, statuses[status], () => api("/applications/" + application.id + "/status",
            {method: "PATCH", json: {status}}));
        }
      }
      if (!fee) {
        const amount = document.createElement("input");
        amount.type = "number";
        amount.min = "0.01";
        amount.max = "9999999999.99";
        amount.step = "0.01";
        amount.placeholder = "Сумма, ₽";
        amount.setAttribute("aria-label", "Оргвзнос для заявки " + application.id);
        actions.append(amount);
        action(actions, "Назначить взнос", () => {
          if (!amount.value || !amount.checkValidity()) throw new Error("Введите положительную сумму");
          return api("/fees", {method: "POST", json: {
            application_id: application.id, amount: Number(amount.value)
          }});
        });
      } else if (fee.status === "unpaid" && application.status === "accepted") {
        action(actions, "Отметить оплату", () => api("/fees/" + fee.id + "/pay", {method: "POST"}));
      }
    }
    body.append(row);
  }
}

async function enterWorkspace() {
  user = await api("/auth/me");
  $("#account-name").textContent = user.full_name;
  $("#account-role").textContent = user.role === "committee" ? "Оргкомитет" : "Участник";
  $("#applications-heading").textContent = user.role === "committee" ? "Все заявки" : "Мои заявки";
  $("#auth-panels").hidden = true;
  $("#workspace").hidden = false;
  $("#logout").hidden = false;
  await loadApplications();
}

function formAction(selector, callback) {
  $(selector).addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    try { await callback(new FormData(event.currentTarget)); }
    catch (error) { message(error.message, true); }
    finally { button.disabled = false; }
  });
}

formAction("#login-form", async (data) => {
  const response = await api("/auth/login", {method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body: new URLSearchParams({username: data.get("email"), password: data.get("password")})});
  token = response.access_token;
  sessionStorage.setItem("confmanager-token", token);
  $("#login-form").reset();
  await enterWorkspace();
  message("Вход выполнен");
});

formAction("#registration-form", async (data) => {
  const created = await api("/participants", {method: "POST", json: {
    full_name: data.get("full_name"), email: data.get("email"),
    organization: data.get("organization").trim() || null, password: data.get("password")
  }});
  $("#registration-form").reset();
  $("#login-form").elements.email.value = created.email;
  message("Регистрация выполнена. Войдите с вашим email и паролем.");
});

formAction("#application-form", async (data) => {
  await api("/applications", {method: "POST", json: {topic: data.get("topic")}});
  $("#application-form").reset();
  await loadApplications();
  message("Заявка подана");
});

$("#logout").addEventListener("click", () => {
  resetSession();
  message("Вы вышли из аккаунта");
});
$("#refresh").addEventListener("click", () => loadApplications().catch((error) => message(error.message, true)));
if (token) enterWorkspace().catch((error) => { resetSession(); message(error.message, true); });
