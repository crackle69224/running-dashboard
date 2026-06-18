function setupAuthForm(formId, endpoint) {
  const form = document.getElementById(formId);
  const errorBox = document.getElementById("authError");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.textContent = "";

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Something went wrong");
      }
      window.location.href = "/";
    } catch (err) {
      errorBox.textContent = err.message;
      submitBtn.disabled = false;
    }
  });
}
