/**
 * board.js —— 棋盘状态管理（模块 2）
 * 负责棋盘创建、碰撞检测、方块固定、消行。
 */
(function (global) {
  'use strict';
  const T = (global.Tetris = global.Tetris || {});
  const { COLS, ROWS } = T.constants;

  // 创建空棋盘：ROWS 行 × COLS 列，每格 null 表示空，否则存颜色
  function create() {
    return Array.from({ length: ROWS }, () => Array(COLS).fill(null));
  }

  // 提取方块占据的所有格子坐标（相对棋盘）
  function pieceCells(piece) {
    const cells = [];
    const m = piece.matrix;
    for (let r = 0; r < m.length; r++) {
      for (let c = 0; c < m[r].length; c++) {
        if (m[r][c]) cells.push({ x: piece.x + c, y: piece.y + r });
      }
    }
    return cells;
  }

  // 判断方块在棋盘上是否合法（不越界、不重叠）
  function valid(board, piece) {
    for (const cell of pieceCells(piece)) {
      if (cell.x < 0 || cell.x >= COLS || cell.y >= ROWS) return false;
      if (cell.y < 0) continue; // 允许在顶面上方
      if (board[cell.y][cell.x] !== null) return false;
    }
    return true;
  }

  // 将方块固定到棋盘
  function merge(board, piece) {
    for (const cell of pieceCells(piece)) {
      if (cell.y >= 0) board[cell.y][cell.x] = piece.color;
    }
  }

  // 消除满行，返回消除的行数
  function clearLines(board) {
    let cleared = 0;
    for (let r = ROWS - 1; r >= 0; r--) {
      if (board[r].every((cell) => cell !== null)) {
        board.splice(r, 1);
        board.unshift(Array(COLS).fill(null));
        cleared++;
        r++; // 上方行下沉后重新检查同一索引
      }
    }
    return cleared;
  }

  T.board = { create, pieceCells, valid, merge, clearLines };
})(window);
