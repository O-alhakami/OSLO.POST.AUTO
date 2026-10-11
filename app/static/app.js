const platformNames = ["instagram", "tiktok", "facebook", "x", "linkedin"];
let uploadedMedia = [];

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || "Request failed.");
  return data;
}

const authForm = document.querySelector("#auth-form");
if (authForm) {
  let endpoint = "/auth/login";
  authForm.querySelectorAll("button[data-endpoint]").forEach((button) => {
    button.addEventListener("click", () => { endpoint = button.dataset.endpoint; });
  });
  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    const target = button?.dataset.endpoint || endpoint;
    const form = new FormData(authForm);
    const message = document.querySelector("#auth-message");
    message.textContent = "";
    try {
      const result = await api(target, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      if (target === "/auth/signup" && !result.authenticated) {
        message.textContent = result.message;
      } else {
        location.assign("/dashboard");
      }
    } catch (error) {
      message.textContent = error.message;
    }
  });
}

const accountsContainer = document.querySelector("#social-accounts");
if (accountsContainer) {
  async function loadAccounts() {
    const accounts = await api("/api/social-accounts");
    const connected = new Set(accounts.map((account) => account.platform));
    accountsContainer.replaceChildren();
    platformNames.forEach((platform) => {
      const account = accounts.find((item) => item.platform === platform);
      const card = document.createElement("div");
      card.className = "rounded-xl border border-slate-800 bg-slate-900 p-4";
      const title = document.createElement("div");
      title.className = "font-semibold capitalize";
      title.textContent = platform;
      card.append(title);
      if (account) {
        const detail = document.createElement("p");
        detail.className = "mt-1 truncate text-sm text-emerald-300";
        detail.textContent = account.account_name || "Connected";
        card.append(detail);
      } else {
        const link = document.createElement("a");
        link.className = "mt-2 inline-block text-sm text-cyan-300 hover:text-white";
        link.href = `/oauth/${platform}/connect`;
        link.textContent = "Connect account";
        card.append(link);
      }
      accountsContainer.append(card);
    });
    document.querySelectorAll('input[name="platforms"]').forEach((input) => {
      input.disabled = !connected.has(input.value);
    });
  }
  loadAccounts().catch((error) => { accountsContainer.textContent = error.message; });
  loadPosts();
}

async function loadPosts() {
  const container = document.querySelector("#posts-list");
  if (!container) return;
  try {
    const posts = await api("/api/posts");
    container.replaceChildren();
    if (!posts.length) {
      container.textContent = "No posts yet.";
      return;
    }
    posts.forEach((post) => {
      const card = document.createElement("article");
      card.className = "rounded-xl border border-slate-800 bg-slate-900 p-4";
      const heading = document.createElement("div");
      heading.className = "flex justify-between gap-3";
      const status = document.createElement("span");
      status.className = "text-sm font-semibold capitalize text-cyan-300";
      status.textContent = post.status;
      const date = document.createElement("time");
      date.className = "text-xs text-slate-500";
      date.textContent = new Date(post.scheduled_at || post.created_at).toLocaleString();
      heading.append(status, date);
      const caption = document.createElement("p");
      caption.className = "mt-3 whitespace-pre-wrap text-sm text-slate-300";
      caption.textContent = post.content || "Media post";
      const platforms = document.createElement("p");
      platforms.className = "mt-2 text-xs capitalize text-slate-500";
      platforms.textContent = (post.platforms || []).join(", ");
      card.append(heading, caption, platforms);
      if (post.error_message) {
        const error = document.createElement("p");
        error.className = "mt-2 text-xs text-rose-300";
        error.textContent = post.error_message;
        card.append(error);
      }
      container.append(card);
    });
  } catch (error) {
    container.textContent = error.message;
  }
}

const postForm = document.querySelector("#post-form");
if (postForm) {
  postForm.elements.media.addEventListener("change", async (event) => {
    uploadedMedia = [];
    const status = document.querySelector("#media-status");
    status.textContent = "Uploading media…";
    try {
      for (const file of event.target.files) {
        const data = new FormData();
        data.append("file", file);
        uploadedMedia.push(await api("/api/media", { method: "POST", body: data }));
      }
      status.textContent = `${uploadedMedia.length} media file(s) uploaded.`;
    } catch (error) {
      uploadedMedia = [];
      status.textContent = error.message;
    }
  });
  postForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#post-message");
    message.textContent = "";
    message.className = "min-h-5 text-sm";
    const data = new FormData(postForm);
    const platforms = data.getAll("platforms");
    const scheduledInput = data.get("scheduled_at");
    if (!platforms.length) {
      message.textContent = "Connect and select at least one social account.";
      return;
    }
    try {
      const result = await api("/api/posts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: data.get("content"),
          platforms,
          media_urls: uploadedMedia.map((item) => item.url),
          media_public_ids: uploadedMedia.map((item) => ({ public_id: item.public_id, resource_type: item.resource_type })),
          scheduled_at: scheduledInput ? new Date(scheduledInput).toISOString() : null,
        }),
      });
      message.classList.add("text-emerald-300");
      message.textContent = `Post queued (${result.status}). Publishing API calls are mocked.`;
      postForm.reset();
      uploadedMedia = [];
      document.querySelector("#media-status").textContent = "";
      loadPosts();
    } catch (error) {
      message.classList.add("text-rose-300");
      message.textContent = error.message;
    }
  });
}

document.querySelector("#logout")?.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    location.assign("/login");
  } catch (error) {
    window.alert(error.message);
  }
});
