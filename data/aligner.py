"""
时间对齐器

确保不同数据源的时间戳一致：
  - 行情数据 (交易日)
  - 财报数据 (季报/年报发布日)
  - 新闻数据 (7x24)
  - 宏观数据 (月度/季度)
"""
import pandas as pd


class TimeAligner:
    """时间对齐器"""

    @staticmethod
    def align_to_trading_days(df: pd.DataFrame,
                              trading_calendar: pd.DatetimeIndex = None,
                              method: str = "ffill") -> pd.DataFrame:
        """
        将数据对齐到交易日

        Args:
            df: 数据 (index 为日期)
            trading_calendar: 交易日历
            method: 对齐方式 (ffill / nearest)

        Returns:
            对齐后的数据
        """
        if trading_calendar is None:
            # 简化：使用数据本身的日期范围生成交易日历
            # 实际应使用 exchange_calendars 或 tushare 的交易日历
            start = df.index.min()
            end = df.index.max()
            trading_calendar = pd.bdate_range(start, end)

        df = df.reindex(trading_calendar, method=method)
        return df

    @staticmethod
    def align_multi_source(data_dict: dict[str: pd.DataFrame]) -> dict[str: pd.DataFrame]:
        """
        对齐多个数据源的时间

        Args:
            data_dict: {"source_name": DataFrame, ...}

        Returns:
            对齐后的数据字典
        """
        # 找到所有数据的公共日期范围
        all_dates = None
        for name, df in data_dict.items():
            if all_dates is None:
                all_dates = set(df.index)
            else:
                all_dates = all_dates.intersection(set(df.index))

        if not all_dates:
            return data_dict

        common_dates = pd.DatetimeIndex(sorted(all_dates))

        result = {}
        for name, df in data_dict.items():
            result[name] = df.reindex(common_dates)

        return result

    @staticmethod
    def forward_fill_event_data(events: pd.DataFrame,
                                trading_dates: pd.DatetimeIndex,
                                decay_days: int = 5) -> pd.DataFrame:
        """
        将事件数据前向填充到交易日，并带衰减

        Args:
            events: 事件数据 (index 为事件发生日期)
            trading_dates: 交易日历
            decay_days: 衰减天数

        Returns:
            填充后的事件数据
        """
        result = pd.DataFrame(index=trading_dates)

        for col in events.columns:
            aligned = events[col].reindex(trading_dates)
            aligned = aligned.ffill(limit=decay_days)
            result[col] = aligned

        return result
