(function () {
  "use strict";

  var output = document.getElementById("output");
  var form = document.getElementById("input-form");
  var input = document.getElementById("command");

  var started = false;
  var gameOver = false;
  var busy = false;
  var commandHistory = [];
  var historyIndex = 0;

  var HELP_TEXT = [
    "Commands:",
    "  start    begin the game",
    "  help     show this list",
    "  clear    clear the screen",
    "  restart  start a new game",
    "  menu     back to the main menu",
    "",
    "Once the game has started, type anything you want to do."
  ].join("\n");

  function print(text, cls) {
    var p = document.createElement("p");
    p.className = "line" + (cls ? " " + cls : "");
    p.textContent = text;
    output.appendChild(p);
    output.scrollTop = output.scrollHeight;
    return p;
  }

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    if (!value) input.focus();
  }

  function sendToNarrator(message) {
    setBusy(true);
    var thinking = print("The forest stirs", "system thinking");

    fetch(window.TERMINAL_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message })
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (result) {
        thinking.remove();
        if (!result.ok) {
          print("Error: " + (result.data.error || "something went wrong") + ". Try again.", "error");
          return;
        }
        print(result.data.answer);
        handleStatus(result.data.status);
      })
      .catch(function () {
        thinking.remove();
        print("Error: could not reach the server. Try again.", "error");
      })
      .finally(function () {
        setBusy(false);
      });
  }

  function handleStatus(status) {
    if (status === "DEAD") {
      gameOver = true;
      print("*** YOU DIED ***", "dead");
      print("Type 'restart' to try again.", "system");
    } else if (status === "WON") {
      gameOver = true;
      print("*** YOU ESCAPED THE FOREST ***", "won");
      print("Type 'restart' to play again.", "system");
    }
  }

  function handleCommand(raw) {
    var text = raw.trim();
    if (!text) return;

    commandHistory.push(text);
    historyIndex = commandHistory.length;
    print("> " + text, "user");

    var cmd = text.toLowerCase();

    if (cmd === "help") return print(HELP_TEXT, "system");
    if (cmd === "clear") { output.innerHTML = ""; return; }
    if (cmd === "restart") { window.location.reload(); return; }
    if (cmd === "menu") { window.location.href = window.MENU_URL; return; }

    if (gameOver) return print("The game is over. Type 'restart' to play again.", "system");

    if (!started) {
      if (cmd !== "start") return print("Type 'start' to begin, or 'help' for commands.", "system");
      started = true;
      return sendToNarrator("Start the game. Describe where I wake up in the forest.");
    }

    sendToNarrator(text);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (busy) return;
    var value = input.value;
    input.value = "";
    handleCommand(value);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowUp") {
      if (historyIndex > 0) historyIndex--;
      input.value = commandHistory[historyIndex] || "";
      e.preventDefault();
    } else if (e.key === "ArrowDown") {
      if (historyIndex < commandHistory.length) historyIndex++;
      input.value = commandHistory[historyIndex] || "";
      e.preventDefault();
    }
  });

  document.addEventListener("click", function () {
    if (!busy && !window.getSelection().toString()) input.focus();
  });

  print("FOREST TERMINAL v1.0", "system");
  print("Type 'start' to begin or 'help' for commands.", "system");
})();
