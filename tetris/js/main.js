/**
 * main.js —— 游戏主逻辑（模块 5，最后加载）
 * 负责游戏循环、输入处理、计分、等级、暂停与重新开始。
 */
(function (global) {
  'use strict';
  const T = global.Tetris;
  const C = T.constants;

  // DOM 元素
  const scoreEl = document.getElementById('score');
  const levelEl = document.getElementById('level');
  const linesEl = document.getElementById('lines');
  const bestEl = document.getElementById('best');
  const overlay = document.getElementById('overlay');
  const overlayTitle = document.getElementById('overlay-title');
  const overlayText = document.getElementById('overlay-text');
  const startBtn = document.getElementById('start-btn');

  // 游戏状态
  let board, current, next;
  let score, lines, level, best;
  let running = false, paused = false, over = false;
  let accumulator = 0, lastTime = 0;

  T.renderer.init('board', 'next');
  best = Number(localStorage.getItem(C.BEST_KEY) || 0);
  bestEl.textContent = best;

  function dropInterval() {
    return Math.max(C.MIN_INTERVAL, C.BASE_INTERVAL * Math.pow(C.SPEED_FACTOR, level - 1));
  }

  function updateHud() {
    scoreEl.textContent = score;
    levelEl.textContent = level;
    linesEl.textContent = lines;
    bestEl.textContent = best;
  }

  function spawn() {
    current = next || T.piece.create();
    next = T.piece.create();
    // 出生即碰撞 => 游戏结束
    if (!T.board.valid(board, current)) {
      return false;
    }
    return true;
  }

  function newGame() {
    board = T.board.create();
    score = 0;
    lines = 0;
    level = 1;
    next = T.piece.create();
    accumulator = 0;
    over = false;
    paused = false;
    running = true;
    updateHud();
    if (!spawn()) {
      return gameOver();
    }
    hideOverlay();
    T.renderer.drawBoard(board, current, true);
    T.renderer.drawNext(next);
  }

  function gameOver() {
    running = false;
    over = true;
    if (score > best) {
      best = score;
      localStorage.setItem(C.BEST_KEY, best);
    }
    updateHud();
    showOverlay('游戏结束 💀', `本局得分 <b>${score}</b><br>最高纪录 <b>${best}</b>`);
  }

  function showOverlay(title, html) {
    overlayTitle.textContent = title;
    overlayText.innerHTML = html;
    startBtn.textContent = running ? '继续游戏' : '开始游戏';
    overlay.classList.remove('hidden');
  }
  function hideOverlay() {
    overlay.classList.add('hidden');
  }

  function togglePause() {
    if (!running || over) return;
    paused = !paused;
    if (paused) {
      showOverlay('已暂停', '按 P 或点击按钮继续');
    } else {
      hideOverlay();
      lastTime = performance.now();
    }
  }

  // 固定当前方块，消行并计分，生成下一个
  function lockPiece() {
    T.board.merge(board, current);
    const cleared = T.board.clearLines(board);
    if (cleared > 0) {
      score += C.SCORE_TABLE[cleared] * level;
      lines += cleared;
      level = Math.floor(lines / C.LINES_PER_LEVEL) + 1;
    }
    updateHud();
    if (!spawn()) {
      gameOver();
      return;
    }
    T.renderer.drawNext(next);
  }

  // 下落一步；无法下落则固定
  function stepDown() {
    if (!T.piece.move(current, board, 0, 1)) {
      lockPiece();
    }
  }

  function hardDrop() {
    if (!running || paused || over) return;
    score += T.piece.drop(current, board) * C.HARD_DROP_SCORE;
    updateHud();
    lockPiece();
  }

  // 主循环（requestAnimationFrame，基于时间累积下落）
  function frame(time) {
    if (running && !paused && !over) {
      const dt = lastTime ? time - lastTime : 0;
      accumulator += dt;
      const interval = dropInterval();
      while (accumulator >= interval) {
        stepDown();
        accumulator -= interval;
        if (over) break;
      }
      T.renderer.drawBoard(board, current, true);
    }
    lastTime = time;
    requestAnimationFrame(frame);
  }

  // 键盘输入
  window.addEventListener('keydown', (e) => {
    const key = e.key;
    if (!running) {
      if (key === 'Enter' || key === ' ') {
        e.preventDefault();
        newGame();
      }
      return;
    }
    switch (key) {
      case 'ArrowLeft': case 'a': case 'A':
        e.preventDefault();
        if (!paused && !over) T.piece.move(current, board, -1, 0);
        break;
      case 'ArrowRight': case 'd': case 'D':
        e.preventDefault();
        if (!paused && !over) T.piece.move(current, board, 1, 0);
        break;
      case 'ArrowDown': case 's': case 'S':
        e.preventDefault();
        if (!paused && !over && T.piece.move(current, board, 0, 1)) {
          score += C.SOFT_DROP_SCORE;
          updateHud();
        }
        break;
      case 'ArrowUp': case 'x': case 'X':
        e.preventDefault();
        if (!paused && !over) T.piece.rotate(current, board);
        break;
      case 'z': case 'Z':
        e.preventDefault();
        if (!paused && !over) T.piece.rotateCCW(current, board);
        break;
      case ' ':
        e.preventDefault();
        hardDrop();
        break;
      case 'p': case 'P':
        e.preventDefault();
        togglePause();
        break;
    }
    T.renderer.drawBoard(board, current, true);
  });

  startBtn.addEventListener('click', () => {
    if (!running || over) newGame();
    else togglePause();
  });

  // 初始画面
  board = T.board.create();
  next = T.piece.create();
  T.renderer.drawBoard(board, null, false);
  T.renderer.drawNext(next);
  showOverlay('俄罗斯方块', '← → 移动 · ↓ 软降<br>↑/X 旋转 · 空格硬降<br>按 空格/回车 开始');

  requestAnimationFrame((t) => { lastTime = t; requestAnimationFrame(frame); });
})(window);
