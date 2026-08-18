document.querySelectorAll(".toggle-pw").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.target);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.textContent = showing ? "Show" : "Hide";
  });
});

const showAll = document.getElementById("show-all-pw");
if (showAll) {
  showAll.addEventListener("change", () => {
    document.querySelectorAll(".password-field input").forEach((input) => {
      input.type = showAll.checked ? "text" : "password";
    });
    document.querySelectorAll(".toggle-pw").forEach((btn) => {
      btn.textContent = showAll.checked ? "Hide" : "Show";
    });
  });
}
