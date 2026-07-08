"""
因子共线性分析（B2.2）。

检测 29 个已注册因子之间的 Pearson 相关性，识别高相关因子组，
帮助避免因子过拟合。**只报告不自动删减**，由人工决策保留哪些因子。

数据来源：DuckDB `factors` 表（long format: ticker, date, factor_name, factor_value）。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


def _load_factor_wide_matrix(ticker_list: list[str] = None,
                             date_range: tuple[str, str] = None,
                             storage=None) -> pd.DataFrame:
    """
    从 storage 加载因子数据并透视成宽表（行=日期/标的，列=因子名）。

    Args:
        ticker_list: 标的列表；None 则全部
        date_range: (start_date, end_date) 字符串元组；None 则不限
        storage: DataStorage 实例；None 则新建

    Returns:
        宽表 DataFrame，每列一个因子，index 为 (ticker, date)
    """
    if storage is None:
        from data.storage import DataStorage
        storage = DataStorage()

    start_date = date_range[0] if date_range else None
    end_date = date_range[1] if date_range else None

    chunks = []
    tickers = ticker_list or [None]
    for ticker in tickers:
        df = storage.load_factors(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )
        if not df.empty:
            chunks.append(df)

    if not chunks:
        return pd.DataFrame()

    raw = pd.concat(chunks, ignore_index=True)
    if raw.empty:
        return pd.DataFrame()

    # 透视：行 = (ticker, date)，列 = factor_name，值 = factor_value
    wide = raw.pivot_table(
        index=["ticker", "date"],
        columns="factor_name",
        values="factor_value",
    )
    return wide


def compute_factor_correlation(ticker_list: list[str] = None,
                               date_range: tuple[str, str] = None,
                               storage=None) -> pd.DataFrame:
    """
    计算 29 个因子的 Pearson 相关性矩阵。

    Args:
        ticker_list: 标的列表；None 则使用全部可用因子数据
        date_range: (start_date, end_date)；None 则不限
        storage: DataStorage 实例

    Returns:
        n×n 相关性矩阵 DataFrame，行列均为因子名，值域 [-1, 1]
    """
    wide = _load_factor_wide_matrix(ticker_list, date_range, storage)
    if wide.empty:
        logger.warning("无因子数据，返回空矩阵")
        return pd.DataFrame()

    # 去掉全 NaN 列，再 dropna 计算相关性
    wide = wide.dropna(axis=1, how="all")
    corr = wide.corr(method="pearson")
    return corr


def detect_collinear_groups(corr_matrix: pd.DataFrame = None,
                            threshold: float = 0.7,
                            ticker_list: list[str] = None,
                            storage=None) -> list[list[str]]:
    """
    识别高相关因子组（|相关性| > threshold），使用并查集合并传递相关因子。

    Args:
        corr_matrix: 预计算的相关性矩阵；None 则现场计算
        threshold: 相关性绝对值阈值，默认 0.7
        ticker_list: 当 corr_matrix 为 None 时使用
        storage: 当 corr_matrix 为 None 时使用

    Returns:
        因子组列表，每组是强相关的因子名列表（长度 >= 2 的组才有意义）
    """
    if corr_matrix is None:
        corr_matrix = compute_factor_correlation(ticker_list, storage=storage)

    if corr_matrix.empty:
        return []

    factors = list(corr_matrix.columns)
    n = len(factors)

    # 并查集
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # 遍历上三角，合并高相关因子对
    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr_matrix.iloc[i, j]) > threshold:
                union(i, j)

    # 收集分组
    groups_map: dict[int, list[str]] = {}
    for i, f in enumerate(factors):
        root = find(i)
        groups_map.setdefault(root, []).append(f)

    # 只返回长度 >= 2 的组（单因子无共线性问题）
    groups = [members for members in groups_map.values() if len(members) >= 2]
    return groups


def generate_collinearity_report(threshold: float = 0.7,
                                 ticker_list: list[str] = None,
                                 date_range: tuple[str, str] = None,
                                 storage=None) -> dict:
    """
    生成完整共线性报告。

    **只报告不自动删减**，提供数据供人工决策。

    Args:
        threshold: 高相关阈值，默认 0.7
        ticker_list: 标的列表
        date_range: 日期范围
        storage: DataStorage 实例

    Returns:
        {
            "factor_count": int,
            "threshold": float,
            "high_correlation_pairs": [{"factor_a", "factor_b", "correlation"}],
            "collinear_groups": [[factor_name, ...], ...],
            "recommendations": [str, ...],
            "correlation_matrix": {factor: {factor: float}},
        }
    """
    corr = compute_factor_correlation(ticker_list, date_range, storage)

    if corr.empty:
        return {
            "factor_count": 0,
            "threshold": threshold,
            "high_correlation_pairs": [],
            "collinear_groups": [],
            "recommendations": ["无因子数据，请先运行因子计算"],
            "correlation_matrix": {},
        }

    factors = list(corr.columns)
    n = len(factors)

    # 收集高相关因子对
    high_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            c = float(corr.iloc[i, j])
            if abs(c) > threshold:
                high_pairs.append({
                    "factor_a": factors[i],
                    "factor_b": factors[j],
                    "correlation": round(c, 4),
                })
    high_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    # 共线性组
    groups = detect_collinear_groups(corr, threshold)

    # 生成建议
    recommendations = []
    for idx, group in enumerate(groups, 1):
        recommendations.append(
            f"组 {idx}: {', '.join(group)} 高度相关，建议每组仅保留一个"
        )
    if not recommendations:
        recommendations.append(f"未发现 |相关性| > {threshold} 的因子组，因子独立性良好")

    # 相关性矩阵序列化（保留 4 位小数）
    corr_serialized = {
        f: {g: round(float(corr.loc[f, g]), 4) for g in factors}
        for f in factors
    }

    return {
        "factor_count": n,
        "threshold": threshold,
        "high_correlation_pairs": high_pairs,
        "high_pair_count": len(high_pairs),
        "collinear_groups": groups,
        "group_count": len(groups),
        "recommendations": recommendations,
        "correlation_matrix": corr_serialized,
    }
