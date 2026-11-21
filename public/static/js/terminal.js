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
  // The story so far. The server is stateless, so the browser keeps the
  // conversation and sends it with every command. Reloading starts a new game.
  var chatHistory = [];
  // This run's rules (move limit, hidden easter egg), picked by the server
  // when the game starts and sent back with every move.
  var run = null;

  var HELP_TEXT = [
    "Commands:",
    "  start    begin the game",
    "  help     show this list",
    "  clear    clear the screen",
    "  restart  start a new game",
    "  menu     back to the main menu",
    "",
    "Once the game has started, type anything you want to do.",
    "Each run lasts 8-10 moves. Then you escape or you don't."
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

  // Light markdown cleanup for text that's still streaming in. The server
  // sends the fully cleaned reply at the end, which replaces this.
  function liveClean(text) {
    return text.replace(/\*\*|__/g, "").replace(/^#{1,6}\s*/gm, "");
  }

  // Reads the server's newline-delimited JSON stream, calling onEvent for
  // each line as it arrives. Works even if the host delivers it all at once.
  function readEvents(res, onEvent) {
    var decoder = new TextDecoder();
    var buffer = "";

    function handleLines(final) {
      var lines = buffer.split("\n");
      buffer = final ? "" : lines.pop();
      lines.forEach(function (line) {
        if (line.trim()) onEvent(JSON.parse(line));
      });
    }

    if (!res.body || !res.body.getReader) {
      return res.text().then(function (text) { buffer = text; handleLines(true); });
    }
    var reader = res.body.getReader();
    function pump() {
      return reader.read().then(function (step) {
        if (step.done) { handleLines(true); return; }
        buffer += decoder.decode(step.value, { stream: true });
        handleLines(false);
        return pump();
      });
    }
    return pump();
  }

  function sendToNarrator(message, onSuccess) {
    setBusy(true);
    var thinking = print("The forest stirs", "system thinking");
    var replyLine = null;
    var streamed = "";
    var finished = false;

    function showReply(text) {
      if (!replyLine) {
        thinking.remove();
        replyLine = print("");
      }
      replyLine.textContent = text;
      output.scrollTop = output.scrollHeight;
    }

    function fail(text) {
      finished = true;
      thinking.remove();
      if (replyLine) replyLine.remove();
      print("Error: " + text + ". Try again.", "error");
    }

    function onEvent(event) {
      if (event.type === "chunk") {
        streamed += event.text;
        showReply(liveClean(streamed));
      } else if (event.type === "done") {
        finished = true;
        showReply(event.answer);
        // Only record the turn once it succeeded, so a failed request can be retried.
        chatHistory.push({ role: "user", content: message });
        chatHistory.push({ role: "assistant", content: event.answer });
        run = event.run;  // chosen by the server on the opening move; sent back each move
        if (onSuccess) onSuccess();
        handleStatus(event);
      } else if (event.type === "error") {
        fail(event.error || "something went wrong");
      }
    }

    fetch(window.STREAM_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, history: chatHistory, run: run })
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (data) { fail(data.error || "something went wrong"); });
        }
        return readEvents(res, onEvent).then(function () {
          if (!finished) fail("the connection dropped before the reply finished");
        });
      })
      .catch(function () {
        if (!finished) fail("could not reach the server");
      })
      .finally(function () {
        setBusy(false);
      });
  }

  function handleStatus(event) {
    var status = event.status;
    if (status === "DEAD") {
      gameOver = true;
      print("*** YOU DIED ***", "dead");
    } else if (status === "WON") {
      gameOver = true;
      print("*** YOU ESCAPED THE FOREST ***", "won");
    } else if (status === "DREAM") {
      gameOver = true;
      print("*** YOU WAKE UP ***", "won");
    }

    if (gameOver) {
      if (event.easter_egg) {
        print(
          "EASTER EGG FOUND: " + event.easter_egg.title + "\n" +
          "This run hid one of " + event.easter_egg.total + " secret easter eggs. Can you find the others?",
          "egg"
        );
      }
      print("Type 'restart' to " + (status === "DEAD" ? "try again." : "play again."), "system");
      return;
    }

    if (event.moves_left === 1) {
      print("[ Final move. Choose wisely. ]", "system");
    } else if (event.moves_left > 1 && event.move > 0) {
      print("[ " + event.moves_left + " moves left ]", "system");
    } else if (event.move === 0) {
      print("[ You have " + event.moves_left + " moves to find a way out. ]", "system");
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
      // Only count the game as started once the opening scene arrives, so a
      // failed request can be retried by typing 'start' again.
      return sendToNarrator("Start the game. Describe where I wake up in the forest.", function () {
        started = true;
      });
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
