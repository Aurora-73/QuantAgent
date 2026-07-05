"""
数据提供者 — baostock(优先) + pytdx(指数) + AKShare(补充)

职责:
  - 获取 A 股行情数据 (日线、分钟线)
  - 获取基本面数据 (财务指标、估值、行业)
  - 获取资金数据 (北向资金、融资融券)
  - 获取指数数据 (沪深300、中证500)
  - 获取股票列表、行业板块等

数据源优先级:
  行情: baostock -> AKShare
  指数: pytdx -> AKShare
  财务/行业: baostock -> AKShare
  资金/板块: AKShare (独家数据)
所有数据统一输出为 pandas DataFrame，列名标准化。
"""
import contextlib
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    logger.warning("akshare 未安装，pip install akshare")

try:
    import baostock as bs
    HAS_BAOSTOCK = True
except ImportError:
    HAS_BAOSTOCK = False
    logger.warning("baostock 未安装，pip install baostock")

try:
    from pytdx.hq import TdxHq_API
    HAS_PYTDX = True
except ImportError:
    HAS_PYTDX = False
    logger.warning("pytdx 未安装，pip install pytdx")


# ── pytdx 配置 ─────────────────────────────────────────────────────

_PYTDX_SERVERS = [
    ("119.147.212.81", 7709),
    ("218.75.126.41", 7709),
]


def _pytdx_market(code: str) -> int:
    """判断 pytdx market 参数: 0=深圳, 1=上海"""
    if code.startswith("000") or code.startswith("91"):
        return 1   # 上证系列指数 / 上海债券
    if code.startswith("399") or code.startswith(("8", "3")):
        return 0   # 深证系列指数 / 深圳创业板 / 三板
    if code.startswith(("6", "9")):
        return 1   # 上海股票
    if code.startswith(("0", "2")):
        return 0   # 深圳股票 / 北京
    return 1


def _safe_float(value) -> Optional[float]:
    """安全转换 float，处理 None/NaN"""
    if value is None:
        return None
    try:
        v = float(value)
        if v != v:  # NaN check
            return None
        return v
    except (ValueError, TypeError):
        return None


@contextlib.contextmanager
def _no_proxy():
    """临时绕过系统代理 — AKShare 连接国内服务器，走代理会连不上。"""
    olds = {}
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        olds[k] = os.environ.pop(k, None)
    old_no_proxy = os.environ.pop("NO_PROXY", None)
    os.environ["NO_PROXY"] = "*"
    try:
        yield
    finally:
        if old_no_proxy is not None:
            os.environ["NO_PROXY"] = old_no_proxy
        else:
            os.environ.pop("NO_PROXY", None)
        for k, v in olds.items():
            if v is not None:
                os.environ[k] = v


class DataProvider:
    """
    A 股数据提供者

    统一接口获取各类数据，数据源优先级:
      行情: baostock -> AKShare
      指数: pytdx -> AKShare
      财务/行业: baostock -> AKShare
      资金/板块: AKShare (独家数据)
    """

    # ============================================================
    # 行情数据
    # ============================================================

    @staticmethod
    def get_stock_daily(ticker: str, start_date: str = None,
                        end_date: str = None,
                        adjust: str = "qfq") -> pd.DataFrame:
        """
        获取个股日线数据

        数据源优先级: baostock -> AKShare

        Args:
            ticker: 股票代码，如 "000001"
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            adjust: 复权方式 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)

        Returns:
            标准化 DataFrame (date index, open, high, low, close, volume, amount, turnover, pct_chg)
        """
        # baostock 优先：稳定、含换手率、无代理问题
        if HAS_BAOSTOCK and adjust in ("qfq", ""):
            try:
                df = _baostock_daily(ticker, start_date, end_date)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"baostock 获取 {ticker} 失败: {e}")

        return _akshare_stock_daily(ticker, start_date, end_date)

    @staticmethod
    def get_index_daily(index_code: str = "000300",
                        start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """
        获取指数日线数据

        数据源优先级: pytdx(通达信直连) -> AKShare。
        pytdx 通过通达信协议直连，无代理问题。

        Args:
            index_code: 指数代码 "000300"(沪深300) / "000905"(中证500) / "000016"(上证50)

        Returns:
            标准化 DataFrame (date index, open, high, low, close, volume)
        """
        # pytdx 优先：协议直连，无代理问题
        if HAS_PYTDX:
            try:
                df = _pytdx_index_daily(index_code, start_date, end_date)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"pytdx 获取指数 {index_code} 失败: {e}")

        # AKShare 回退
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装，且 pytdx 无数据")
        try:
            with _no_proxy():
                df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
        except Exception:
            try:
                with _no_proxy():
                    df = ak.stock_zh_index_daily(symbol=f"sz{index_code}")
            except Exception as e:
                logger.error(f"获取指数 {index_code} 数据失败: {e}")
                return pd.DataFrame()

        if df.empty:
            return df

        col_map = {"date": "date", "open": "open", "high": "high",
                   "low": "low", "close": "close", "volume": "volume"}
        df = df.rename(columns=col_map)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        return df

    # ============================================================
    # 基本面数据
    # ============================================================

    @staticmethod
    def get_stock_industry(ticker: str) -> str:
        """
        获取个股行业分类 (baostock)

        Returns:
            行业名称，如 "半导体"，查不到返回 ""
        """
        if not HAS_BAOSTOCK:
            return ""
        try:
            lg = bs.login()
            if lg.error_code != "0":
                return ""
            rs = bs.query_stock_industry()
            industry = ""
            while (rs.error_code == "0") and rs.next():
                row = rs.get_row_data()
                if len(row) >= 4:
                    code = row[1].split(".")[-1] if "." in row[1] else row[1]
                    if code == ticker:
                        industry = row[3]
                        break
            bs.logout()
            return industry
        except Exception as e:
            logger.warning(f"baostock 获取行业失败: {e}")
            return ""

    @staticmethod
    def get_all_industries() -> dict[str, tuple[str, str]]:
        """
        获取全市场行业分类映射 (baostock)

        Returns:
            {ticker: (股票名称, 行业名称)} 字典
        """
        if not HAS_BAOSTOCK:
            return {}
        try:
            lg = bs.login()
            if lg.error_code != "0":
                return {}
            rs = bs.query_stock_industry()
            result = {}
            while (rs.error_code == "0") and rs.next():
                row = rs.get_row_data()
                if len(row) >= 4:
                    code = row[1].split(".")[-1] if "." in row[1] else row[1]
                    result[code] = (row[2], row[3])
            bs.logout()
            return result
        except Exception as e:
            logger.warning(f"baostock 获取全行业失败: {e}")
            return {}

    @staticmethod
    def get_stock_basic_info(ticker: str) -> dict:
        """
        获取个股基本信息 (baostock)

        Returns:
            {name, ipo_date, out_date, type, status} 字典
        """
        if not HAS_BAOSTOCK:
            return {}
        try:
            prefix = "sh" if ticker.startswith("6") else "sz"
            symbol = f"{prefix}.{ticker}"
            lg = bs.login()
            if lg.error_code != "0":
                return {}
            rs = bs.query_stock_basic(symbol)
            result = {}
            if rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                result = {
                    "name": row[1] if len(row) > 1 else "",
                    "ipo_date": row[2] if len(row) > 2 else "",
                    "out_date": row[3] if len(row) > 3 else "",
                    "type": row[4] if len(row) > 4 else "",
                    "status": row[5] if len(row) > 5 else "",
                }
            bs.logout()
            return result
        except Exception as e:
            logger.warning(f"baostock 获取基本信息失败: {e}")
            return {}

    @staticmethod
    def get_stock_financial_reports(ticker: str, year: int = None,
                                     quarter: int = None) -> dict[str, pd.DataFrame]:
        """
        获取个股财务报表 (baostock)

        Args:
            ticker: 股票代码
            year: 年份，默认最近一年
            quarter: 季度 (1-4)，默认最近一季

        Returns:
            {"profit": DataFrame, "operation": DataFrame, "growth": DataFrame,
             "balance": DataFrame, "cash_flow": DataFrame}
            各 DataFrame 为空表示无数据
        """
        if not HAS_BAOSTOCK:
            return {}
        if year is None:
            year = datetime.now().year
        if quarter is None:
            quarter = (datetime.now().month - 1) // 3
            quarter = max(1, quarter)

        prefix = "sh" if ticker.startswith("6") else "sz"
        symbol = f"{prefix}.{ticker}"

        result = {}
        try:
            lg = bs.login()
            if lg.error_code != "0":
                return {}

            apis = {
                "profit": bs.query_profit_data,
                "operation": bs.query_operation_data,
                "growth": bs.query_growth_data,
                "balance": bs.query_balance_data,
                "cash_flow": bs.query_cash_flow_data,
            }
            for name, api in apis.items():
                try:
                    rs = api(symbol, year, quarter)
                    rows = []
                    while (rs.error_code == "0") and rs.next():
                        rows.append(rs.get_row_data())
                    if rows:
                        cols = rs.fields if isinstance(rs.fields[0], str) else [desc[0] for desc in rs.fields]
                        result[name] = pd.DataFrame(rows, columns=cols)
                except Exception as e:
                    logger.debug(f"baostock {name} 获取失败: {e}")

            bs.logout()
        except Exception as e:
            logger.warning(f"baostock 获取财务报表失败: {e}")
        return result

    @staticmethod
    def get_stock_valuation(ticker: str) -> dict:
        """获取个股估值数据 (PE/PB/PS/市值等) — AKShare"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_value_em(symbol=ticker)
            if df.empty:
                return {}
            latest = df.iloc[-1]
            return {
                "pe_ttm": _safe_float(latest.get("PE(TTM)")),
                "pe": _safe_float(latest.get("PE(静)")),
                "pb": _safe_float(latest.get("市净率")),
                "ps": _safe_float(latest.get("市销率")),
                "pc": _safe_float(latest.get("市现率")),
                "peg": _safe_float(latest.get("PEG值")),
                "total_mv": _safe_float(latest.get("总市值")),
                "circ_mv": _safe_float(latest.get("流通市值")),
                "close": _safe_float(latest.get("当日收盘价")),
                "pct_chg": _safe_float(latest.get("当日涨跌幅")),
                "date": str(latest.get("数据日期", "")),
            }
        except Exception as e:
            logger.error(f"获取 {ticker} 估值数据失败: {e}")
            return {}

    @staticmethod
    def get_stock_financial(ticker: str) -> pd.DataFrame:
        """获取个股财务指标 (AKShare)"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_financial_abstract_ths(symbol=ticker, indicator="按报告期")
            return df
        except Exception as e:
            logger.error(f"获取 {ticker} 财务数据失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_batch_valuation(tickers: list[str]) -> pd.DataFrame:
        """
        批量获取估值数据 (PE/PB/总市值)

        Returns:
            DataFrame with columns: ticker, total_mv, pe_ttm, pb
        """
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        results = []
        for ticker in tickers:
            try:
                val = DataProvider.get_stock_valuation(ticker)
                if val:
                    results.append({
                        "ticker": ticker,
                        "total_mv": val.get("total_mv"),
                        "pe_ttm": val.get("pe_ttm"),
                        "pb": val.get("pb"),
                    })
            except Exception as e:
                logger.debug(f"  {ticker} 估值获取失败: {e}")
        return pd.DataFrame(results)

    # ============================================================
    # 资金数据
    # ============================================================

    @staticmethod
    def get_north_flow(start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """获取北向资金数据"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]
            return df
        except Exception as e:
            logger.error(f"获取北向资金数据失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_margin_data(ticker: str = None) -> pd.DataFrame:
        """获取融资融券数据"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            if ticker:
                with _no_proxy():
                    df = ak.stock_margin_detail_szse(date=datetime.now().strftime("%Y%m%d"))
            else:
                with _no_proxy():
                    df = ak.stock_margin_sse(date=datetime.now().strftime("%Y%m%d"))
            return df
        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return pd.DataFrame()

    # ============================================================
    # 市场数据
    # ============================================================

    @staticmethod
    def get_stock_list(market: str = "A") -> pd.DataFrame:
        """
        获取股票列表

        Args:
            market: "A" / "HK" / "US"

        Returns:
            DataFrame 包含股票代码和名称
        """
        if market == "A" and HAS_BAOSTOCK:
            try:
                lg = bs.login()
                if lg.error_code == "0":
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    for day in [today_str, "2026-07-02", "2026-07-01", "2026-06-30"]:
                        rs = bs.query_all_stock(day=day)
                        rows = []
                        while (rs.error_code == "0") and rs.next():
                            rows.append(rs.get_row_data())
                        if rows:
                            break
                    bs.logout()
                    if rows:
                        df = pd.DataFrame(rows, columns=["date", "code", "name"])
                        df["ticker"] = df["code"].str.split(".").str[-1].str.strip()
                        df["name"] = df["name"].str.strip()
                        df = df[["ticker", "name"]]
                        return df
            except Exception as e:
                logger.warning(f"baostock 获取股票列表失败: {e}")

        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_zh_a_spot_em()
            col_map = {"代码": "ticker", "名称": "name", "最新价": "close",
                       "涨跌幅": "pct_change", "成交量": "volume", "成交额": "amount"}
            df = df.rename(columns=col_map)
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_sector_data() -> pd.DataFrame:
        """获取行业板块数据"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            logger.error(f"获取行业板块数据失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_concept_data() -> pd.DataFrame:
        """获取概念板块数据"""
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            logger.error(f"获取概念板块数据失败: {e}")
            return pd.DataFrame()

    # ============================================================
    # 批量获取
    # ============================================================

    @classmethod
    def get_universe_daily(cls, tickers: list[str],
                           start_date: str = None,
                           end_date: str = None,
                           sleep_sec: float = 0.3) -> dict[str, pd.DataFrame]:
        """批量获取多只股票的日线数据"""
        result = {}
        for i, ticker in enumerate(tickers):
            logger.info(f"获取 {ticker} ({i+1}/{len(tickers)})...")
            df = cls.get_stock_daily(ticker, start_date, end_date)
            if not df.empty:
                result[ticker] = df
            time.sleep(sleep_sec)
        return result

    @classmethod
    def get_csi300_components(cls) -> list[str]:
        """获取沪深300成分股 (baostock -> AKShare)"""
        if HAS_BAOSTOCK:
            try:
                lg = bs.login()
                if lg.error_code == "0":
                    rs = bs.query_hs300_stocks()
                    codes = []
                    while (rs.error_code == "0") and rs.next():
                        row = rs.get_row_data()
                        if len(row) >= 2:
                            codes.append(row[1].split(".")[-1])
                    bs.logout()
                    if codes:
                        return codes
            except Exception as e:
                logger.warning(f"baostock 获取沪深300成分股失败: {e}")

        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.index_stock_cons(symbol="000300")
            return df["品种代码"].tolist()
        except Exception as e:
            logger.error(f"AKShare 获取沪深300成分股失败: {e}")
            return []

    @classmethod
    def get_csi500_components(cls) -> list[str]:
        """获取中证500成分股 (baostock -> AKShare)"""
        if HAS_BAOSTOCK:
            try:
                lg = bs.login()
                if lg.error_code == "0":
                    rs = bs.query_hs500_stocks()
                    codes = []
                    while (rs.error_code == "0") and rs.next():
                        row = rs.get_row_data()
                        if len(row) >= 2:
                            codes.append(row[1].split(".")[-1])
                    bs.logout()
                    if codes:
                        return codes
            except Exception as e:
                logger.warning(f"baostock 获取中证500成分股失败: {e}")

        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装")
        try:
            with _no_proxy():
                df = ak.index_stock_cons(symbol="000905")
            return df["品种代码"].tolist()
        except Exception as e:
            logger.error(f"AKShare 获取中证500成分股失败: {e}")
            return []


# ================================================================
# 内部数据获取函数
# ================================================================

def _baostock_daily(ticker: str, start_date: str = None,
                     end_date: str = None) -> pd.DataFrame:
    """通过 baostock 获取日线（无代理问题，含换手率/涨跌幅）"""
    prefix = "sh" if ticker.startswith("6") else "sz"
    symbol = f"{prefix}.{ticker}"
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = "2020-01-01"

    lg = bs.login()
    if lg.error_code != "0":
        logger.warning(f"baostock 登录失败: {lg.error_msg}")
        return pd.DataFrame()

    rs = bs.query_history_k_data_plus(
        symbol,
        "date,open,high,low,close,volume,amount,turn,pctChg",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2",
    )
    data = []
    while (rs.error_code == "0") and rs.next():
        data.append(rs.get_row_data())
    bs.logout()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close",
                                      "volume", "amount", "turn", "pct_chg"])
    for col in ["open", "high", "low", "close", "volume", "amount", "turn", "pct_chg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df.rename(columns={"turn": "turnover"})
    return df


def _akshare_stock_daily(ticker: str, start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
    """AKShare 回退获取日线数据"""
    if not HAS_AKSHARE:
        raise ImportError("akshare 未安装，且 baostock 无数据")

    try:
        with _no_proxy():
            df = ak.stock_zh_a_daily(
                symbol=f"sh{ticker}" if ticker.startswith("6") else f"sz{ticker}",
                start_date=start_date.replace("-", "") if start_date else "20200101",
                end_date=end_date.replace("-", "") if end_date else datetime.now().strftime("%Y%m%d"),
            )
    except Exception as e:
        logger.error(f"AKShare 获取 {ticker} 数据失败: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    expected_cols = {"date", "open", "high", "low", "close", "volume"}
    if not expected_cols.issubset(df.columns):
        logger.warning(f"{ticker} 数据列不完整: {list(df.columns)}")
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    if "pct_chg" not in df.columns:
        df["pct_chg"] = df["close"].pct_change() * 100

    return df


def _pytdx_connect():
    """连接 pytdx 服务器，返回 api 实例或 None"""
    for host, port in _PYTDX_SERVERS:
        try:
            api = TdxHq_API()
            api.connect(host, port, time_out=_PYTDX_TIMEOUT)
            return api
        except Exception:
            continue
    return None


def _pytdx_index_daily(index_code: str, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
    """通过 pytdx 获取指数日线数据（无代理问题）"""
    market = _pytdx_market(index_code)
    api = _pytdx_connect()
    if api is None:
        return pd.DataFrame()

    try:
        # 取足够多的数据 (约 3 年)
        bars = api.get_security_bars(9, market, index_code, 0, 800)
        api.disconnect()
    except Exception:
        api.disconnect()
        return pd.DataFrame()

    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    # pytdx 返回字段: year, month, day, hour, minute, open, high, low, close, price, volume, amount
    df["date"] = pd.to_datetime(df[["year", "month", "day"]])
    df = df.rename(columns={
        "open": "open", "high": "high", "low": "low",
        "close": "close", "volume": "volume", "amount": "amount",
    })
    df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.set_index("date").sort_index()

    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]
    return df
