/**
 * piece.js —— 活动方块逻辑（模块 3）
 * 负责方块生成、旋转（含墙踢）、移动、硬降。
 */
(function (global) {
  'use strict';
  const T = (global.Tetris = global.Tetris || {});
  const { COLS, COLORS, SHAPES } = T.constants;

  function randomType() {
    const types = Object.keys(SHAPES);
    return types[Math.floor(Math.random() * types.length)];
  }

  // 创建一个新方块（可选指定类型）
  function create(type) {
    type = type || randomType();
    const matrix = SHAPES[type].map((row) => row.slice()); // 深拷贝
    return {
      type,
      color: COLORS[type],
      matrix,
      x: Math.floor((COLS - matrix[0].length) / 2), // 水平居中
      y: 0,
    };
  }

  // 矩阵顺时针旋转 90°
  function rotateMatrix(m) {
    const n = m.length;
    const res = Array.from({ length: n }, () => Array(n).fill(0));
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        res[c][n - 1 - r] = m[r][c];
      }
    }
    return res;
  }

  // 顺时针旋转，带简单墙踢（依次尝试左右偏移）
  function rotate(piece, board) {
    const rotated = rotateMatrix(piece.matrix);
    const kicks = [0, -1, 1, -2, 2];
    for (const dx of kicks) {
      const candidate = { ...piece, matrix: rotated, x: piece.x + dx };
      if (T.board.valid(board, candidate)) {
        piece.matrix = rotated;
        piece.x += dx;
        return true;
      }
    }
    return false;
  }

  // 逆时针旋转（等于顺时针 3 次），同样带墙踢
  function rotateCCW(piece, board) {
    for (let i = 0; i < 3; i++) {
      if (!rotate(piece, board)) return false;
    }
    return true;
  }

  // 平移；成功返回 true
  function move(piece, board, dx, dy) {
    const candidate = { ...piece, x: piece.x + dx, y: piece.y + dy };
    if (T.board.valid(board, candidate)) {
      piece.x += dx;
      piece.y += dy;
      return true;
    }
    return false;
  }

  // 硬降：直接落到底，返回下落格数
  function drop(piece, board) {
    let dist = 0;
    while (move(piece, board, 0, 1)) dist++;
    return dist;
  }

  T.piece = { create, rotate, rotateCCW, move, drop, randomType };
})(window);
