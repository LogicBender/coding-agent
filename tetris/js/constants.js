/**
 * constants.js —— 全局常量与配置（模块 1）
 * 通过 window.Tetris 命名空间与其他模块协同，避免全局变量污染。
 */
(function (global) {
  'use strict';
  const T = (global.Tetris = global.Tetris || {});

  T.constants = {
    COLS: 10,
    ROWS: 20,
    CELL: 30, // 每个格子的像素尺寸

    // 7 种标准方块的颜色
    COLORS: {
      I: '#22d3ee', // 青
      O: '#facc15', // 黄
      T: '#a855f7', // 紫
      S: '#4ade80', // 绿
      Z: '#f87171', // 红
      J: '#60a5fa', // 蓝
      L: '#fb923c', // 橙
    },

    // 方块形状（矩阵，1 表示有块）
    SHAPES: {
      I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
      O: [[1, 1], [1, 1]],
      T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
      S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
      Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
      J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
      L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
    },

    // 一次性消行数对应的基础得分
    SCORE_TABLE: { 1: 100, 2: 300, 3: 500, 4: 800 },

    LINES_PER_LEVEL: 10, // 每消 10 行升一级
    BASE_INTERVAL: 800,  // 1 级时的下落间隔(ms)
    MIN_INTERVAL: 80,    // 最快下落间隔(ms)
    SPEED_FACTOR: 0.82,  // 每升一级，间隔乘以该系数
    SOFT_DROP_SCORE: 1,  // 软降一格加分
    HARD_DROP_SCORE: 2,  // 硬降一格加分
    BEST_KEY: 'tetris-best',
  };
})(window);
