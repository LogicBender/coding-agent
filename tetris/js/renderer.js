/**
 * renderer.js —— Canvas 渲染（模块 4）
 * 负责绘制棋盘、已堆叠方块、幽灵投影、当前方块与下一方块预览。
 */
(function (global) {
  'use strict';
  const T = (global.Tetris = global.Tetris || {});
  const { COLS, ROWS, CELL } = T.constants;

  let ctx, nextCtx;

  function init(boardCanvasId, nextCanvasId) {
    const board = document.getElementById(boardCanvasId);
    const next = document.getElementById(nextCanvasId);
    ctx = board.getContext('2d');
    nextCtx = next.getContext('2d');
  }

  // 绘制单个带立体感的方块
  function drawBlock(context, px, py, size, color, ghost) {
    if (ghost) {
      context.fillStyle = 'rgba(255,255,255,0.06)';
      context.fillRect(px, py, size, size);
      context.strokeStyle = color;
      context.globalAlpha = 0.5;
      context.lineWidth = 1.5;
      context.strokeRect(px + 0.75, py + 0.75, size - 1.5, size - 1.5);
      context.globalAlpha = 1;
      return;
    }
    const s = size - 1;
    context.fillStyle = color;
    context.fillRect(px, py, s, s);
    // 高光（上左）
    context.fillStyle = 'rgba(255,255,255,0.35)';
    context.fillRect(px, py, s, 3);
    context.fillRect(px, py, 3, s);
    // 阴影（下右）
    context.fillStyle = 'rgba(0,0,0,0.3)';
    context.fillRect(px, py + s - 3, s, 3);
    context.fillRect(px + s - 3, py, 3, s);
  }

  function drawGrid() {
    ctx.clearRect(0, 0, COLS * CELL, ROWS * CELL);
    ctx.strokeStyle = 'rgba(255,255,255,0.045)';
    ctx.lineWidth = 1;
    for (let c = 1; c < COLS; c++) {
      const x = c * CELL;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ROWS * CELL); ctx.stroke();
    }
    for (let r = 1; r < ROWS; r++) {
      const y = r * CELL;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(COLS * CELL, y); ctx.stroke();
    }
  }

  // 计算幽灵投影位置（当前方块能下落到的最远位置）
  function ghostY(board, piece) {
    let gy = piece.y;
    while (T.board.valid(board, { ...piece, y: gy + 1 })) gy++;
    return gy;
  }

  function drawBoard(board, piece, showGhost) {
    drawGrid();

    // 已堆叠的方块
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const color = board[r][c];
        if (color) drawBlock(ctx, c * CELL, r * CELL, CELL, color, false);
      }
    }

    if (!piece) return;

    // 幽灵投影
    if (showGhost && T.board.valid(board, piece)) {
      const gy = ghostY(board, piece);
      if (gy !== piece.y) {
        const m = piece.matrix;
        for (let r = 0; r < m.length; r++) {
          for (let c = 0; c < m[r].length; c++) {
            if (m[r][c]) {
              drawBlock(ctx, (piece.x + c) * CELL, (gy + r) * CELL, CELL, piece.color, true);
            }
          }
        }
      }
    }

    // 当前方块
    const m = piece.matrix;
    for (let r = 0; r < m.length; r++) {
      for (let c = 0; c < m[r].length; c++) {
        if (m[r][c] && piece.y + r >= 0) {
          drawBlock(ctx, (piece.x + c) * CELL, (piece.y + r) * CELL, CELL, piece.color, false);
        }
      }
    }
  }

  function drawNext(piece) {
    const size = 120; // 预览画布大小
    nextCtx.clearRect(0, 0, size, size);
    if (!piece) return;
    const m = piece.matrix;
    const n = m.length;
    const cellSize = size / 4;
    const offsetX = (4 - n) * cellSize / 2;
    const offsetY = (4 - n) * cellSize / 2;
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (m[r][c]) {
          drawBlock(nextCtx, offsetX + c * cellSize, offsetY + r * cellSize, cellSize, piece.color, false);
        }
      }
    }
  }

  T.renderer = { init, drawBoard, drawNext };
})(window);
