const platformNames = ["instagram", "tiktok", "facebook", "x", "linkedin"];
const platformLabels = {
  instagram: "إنستغرام",
  tiktok: "تيك توك",
  facebook: "فيسبوك",
  x: "X",
  linkedin: "لينكدإن",
};

let uploadedMedia = [];

const statusLabels = {
  queued: "قيد الانتظار",
  scheduled: "مجدول",
  published: "تم النشر",
  failed: "فشل",
};

function translateErrorMessage(message) {
  const source = String(message || "");
  const map = {
    "Invalid email or password.": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    "Account created.": "تم إنشاء الحساب بنجاح.",
    "Check your email to confirm your account.": "تحقق من بريدك الإلكتروني لتأكيد الحساب.",
    "Signed in.": "تم تسجيل الدخول بنجاح.",
    "Invalid path specified in request URL": "عنوان الطلب غير صالح.",
    "Only supported image and video formats can be uploaded.": "يُسمح فقط بتحميل الصور ومقاطع الفيديو المدعومة.",
    "The uploaded file exceeds the size limit.": "حجم الملف أكبر من الحد المسموح به.",
    "A post must include text or at least one media item.": "يجب إدراج نص أو عنصر وسائط واحد على الأقل.",
    "Select one or more supported platforms.": "اختر منصة واحدة أو أكثر من المنصات المدعومة.",
    "Connect these accounts first: ": "يرجى ربط هذه الحسابات أولاً: ",
    "Please sign in.": "يرجى تسجيل الدخول أولاً.",
    "Invalid or expired session.": "الجلسة منتهية أو غير صالحة.",
    "Request failed.": "فشل الطلب.",
  };
  return map[source] || source;
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(translateErrorMessage(data.detail || data.message || "Request failed."));
  return data;
}

const authForm = document.querySelector("#auth-form");
if (authForm) {
  const passwordToggle = document.querySelector(".password-toggle");
  if (passwordToggle) {
    passwordToggle.addEventListener("click", () => {
      const input = document.getElementById(passwordToggle.dataset.toggleTarget || "password-input");
      if (!input) return;
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      passwordToggle.textContent = visible ? "إظهار" : "إخفاء";
      passwordToggle.setAttribute("aria-label", visible ? "إظهار كلمة المرور" : "إخفاء كلمة المرور");
    });
  }

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
        message.textContent = result.message || "تم إنشاء الحساب بنجاح.";
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
      card.className = "social-item";

      const nameWrapper = document.createElement("div");
      nameWrapper.className = "social-name";
      const label = document.createElement("span");
      label.textContent = platformLabels[platform] || platform;
      nameWrapper.append(label);

      const pill = document.createElement("span");
      pill.className = "social-pill";
      if (account) {
        pill.textContent = "متصل";
        const detail = document.createElement("div");
        detail.className = "text-sm text-slate-300";
        detail.textContent = account.account_name || "جاهز";
        nameWrapper.append(detail);
      } else {
        pill.textContent = "ربط";
        const link = document.createElement("a");
        link.className = "social-link";
        link.href = `/oauth/${platform}/connect`;
        link.textContent = "ربط الحساب";
        card.append(link);
      }

      card.append(nameWrapper, pill);
      accountsContainer.append(card);
    });
    document.querySelectorAll('input[name="platforms"]').forEach((input) => {
      input.disabled = !connected.has(input.value);
      const text = input.parentElement?.querySelector("span");
      if (text) text.textContent = platformLabels[input.value] || input.value;
    });
    const accountCount = document.querySelector("#account-count");
    if (accountCount) accountCount.textContent = String(accounts.length);
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

    const queuedCount = posts.filter((post) => post.status === "queued" || post.status === "scheduled").length;
    const publishedCount = posts.filter((post) => post.status === "published").length;
    const queuedNode = document.querySelector("#queued-count");
    const publishedNode = document.querySelector("#published-count");
    if (queuedNode) queuedNode.textContent = String(queuedCount);
    if (publishedNode) publishedNode.textContent = String(publishedCount);

    if (!posts.length) {
      container.textContent = "لا توجد منشورات حتى الآن.";
      return;
    }
    posts.forEach((post) => {
      const card = document.createElement("article");
      card.className = "post-item";

      const heading = document.createElement("div");
      heading.className = "post-top";

      const status = document.createElement("span");
      status.className = "post-status";
      status.textContent = statusLabels[post.status] || post.status;

      const date = document.createElement("time");
      date.className = "post-time";
      date.textContent = new Date(post.scheduled_at || post.created_at).toLocaleString("ar-SA");
      heading.append(status, date);

      const caption = document.createElement("p");
      caption.className = "post-text";
      caption.textContent = post.content || "منشور وسائط";

      const platforms = document.createElement("p");
      platforms.className = "post-platforms";
      platforms.textContent = (post.platforms || []).map((item) => platformLabels[item] || item).join(", ");

      card.append(heading, caption, platforms);
      if (post.error_message) {
        const error = document.createElement("p");
        error.className = "post-error";
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
    status.textContent = "جارٍ رفع الوسائط…";
    try {
      for (const file of event.target.files) {
        const data = new FormData();
        data.append("file", file);
        uploadedMedia.push(await api("/api/media", { method: "POST", body: data }));
      }
      status.textContent = `${uploadedMedia.length} ملف(ات) تم رفعه بنجاح.`;
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
      message.textContent = "يرجى اختيار حساب واحد على الأقل.";
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
      message.textContent = `تمت إضافة المنشور (${statusLabels[result.status] || result.status}).`;
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
