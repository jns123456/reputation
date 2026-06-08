document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".pr-market-tape").forEach(function (tape) {
    tape.addEventListener("pointerdown", function () {
      tape.classList.add("is-paused");
    });
    tape.addEventListener("pointerup", function () {
      tape.classList.remove("is-paused");
    });
    tape.addEventListener("pointercancel", function () {
      tape.classList.remove("is-paused");
    });
    tape.addEventListener("pointerleave", function (event) {
      if (event.pointerType === "mouse") {
        tape.classList.remove("is-paused");
      }
    });
  });
});
