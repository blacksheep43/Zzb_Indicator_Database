import datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy import stats
from dateutil.relativedelta import relativedelta
import streamlit_antd_components as sac


def calculate_rolling_returns(data, interval_years, net_value_column, start_date, end_date):
    """
    计算指定区间内的滚动年化收益率。

    参数:
    - data: 基金数据 DataFrame，包含 'SecuCode'、'TradingDay'、'AdjustedUnitNV' 等列。
    - interval_years: 滚动窗口的年数。
    - start_date: 用户设定的开始日期。
    - end_date: 用户设定的结束日期。
    """
    results = []
    # 确保交易日和用户设定的日期为日期类型
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # 支持小于1年的interval_years，计算对应的月份
    interval_months = int(interval_years * 12)  # 1年 = 12个月

    for secu_code in data['SecuCode'].unique():
        fund_data = data[data['SecuCode'] == secu_code].copy()
        fund_data = fund_data.sort_values(by='TradingDay')

        for start_date_window in fund_data['TradingDay']:
            # 如果滚动窗口的开始日期早于用户设定的 start_date，跳过
            if start_date_window < start_date:
                continue

            # 计算滚动窗口的结束日期
            end_date_window = start_date_window + relativedelta(months=interval_months)

            # 如果滚动窗口的结束日期超过用户设定的 end_date，停止计算
            if end_date_window > end_date:
                break

            # 获取符合结束日期的交易数据
            end_data = fund_data[fund_data['TradingDay'] <= end_date_window]
            if end_data.empty or len(end_data) <= 1:
                continue

            # 获取起始净值和结束净值
            start_nv = fund_data.loc[fund_data['TradingDay'] == start_date_window, net_value_column].values[0]
            end_nv = end_data[net_value_column].values[-1]

            # 计算天数
            days_diff = (end_data['TradingDay'].values[-1] - start_date_window).days

            # 打印调试信息
            if days_diff == 0:
                st.write(
                    f"⚠️ Days difference is 0 for fund {secu_code}, start_date: {start_date_window}, end_date: {end_data['TradingDay'].values[-1]}")

            if days_diff == 0:
                continue  # 跳过 days_diff 为 0 的情况

            # 按天计算年化收益率
            annualized_return = ((end_nv / start_nv) ** (365 / days_diff)) - 1

            # 存储结果
            results.append({
                'SecuCode': secu_code,
                'start_date': start_date_window,
                'end_date': end_data['TradingDay'].values[-1],
                'annualized_return_rate': annualized_return * 100,
                'interval': interval_years
            })

    return pd.DataFrame(results)


# 计算对比基金的调整后净值
def calculate_adjusted_net_value_for_comparison_funds(data, comparison_fund_pool):
    comparison_fund_data = data[data['SecuCode'].isin(comparison_fund_pool)]
    comparison_fund_data['AdjustedUnitNV'] = comparison_fund_data['UnitNV'] * comparison_fund_data['a'] + \
                                             comparison_fund_data['b']
    return comparison_fund_data


# 计算统计指标
def calculate_statistics(data):
    skewness = stats.skew(data)
    kurtosis = stats.kurtosis(data, fisher=False)

    return {
        '最小值': data.min(),
        '最大值': data.max(),
        '平均值': data.mean(),
        '标准差': data.std(),
        '中位数': data.median(),
        '偏度': skewness,
        '峰度': kurtosis,
        '25%分位点': data.quantile(0.25),
        '75%分位点': data.quantile(0.75),
        '75%分位点-25%分位点': data.quantile(0.75) - data.quantile(0.25),
        '左0.1%尾部': data.quantile(0.001),
        '右0.1%尾部': data.quantile(0.999)
    }


def plot_and_calculate_distributions(data, comparison_data, research_funds_to_compare, comparison_funds_to_compare,
                                     intervals, net_value_column):
    statistics = []
    fig = go.Figure()
    start_date = st.session_state['start_date']
    end_date = st.session_state['end_date']

    # 遍历每个区间
    for interval in intervals:
        interval_data = calculate_rolling_returns(data, interval, net_value_column, start_date, end_date)
        st.write(interval_data)
        # 处理研究基金
        for fund_code in research_funds_to_compare:
            fund_returns = interval_data[interval_data['SecuCode'] == fund_code]['annualized_return_rate'].dropna()
            all_returns = interval_data['annualized_return_rate'].dropna()

            if fund_returns.empty or all_returns.empty:
                continue

            # 计算研究基金的统计指标
            stats_dict = calculate_statistics(fund_returns)
            stats_dict.update({
                '基金代码': fund_code,
                '区间': interval,
                '类型': '研究基金'
            })
            statistics.append(stats_dict)

            # 绘制研究基金的核密度图
            x_vals_fund = np.sort(fund_returns)
            y_vals_fund = stats.gaussian_kde(fund_returns)(x_vals_fund)
            fig.add_trace(go.Scatter(
                x=x_vals_fund,
                y=y_vals_fund,
                mode='lines',
                name=f'基金 {fund_code} - 区间 {interval}',
                hovertemplate=f'基金 {fund_code} 区间 {interval}: y=%{{y:.2f}}<extra></extra>'  # 显式设置 hover 信息的格式
            ))

        # 如果有对比基金池
        if comparison_data is not None:
            comparison_interval_data = calculate_rolling_returns(comparison_data, interval, net_value_column,
                                                                 start_date, end_date)
            if comparison_funds_to_compare:
                # 只计算选中的对比基金
                comparison_returns = \
                    comparison_interval_data[comparison_interval_data['SecuCode'].isin(comparison_funds_to_compare)][
                        'annualized_return_rate'].dropna()
            else:
                # 计算全部对比基金
                comparison_returns = comparison_interval_data['annualized_return_rate'].dropna()

            if not comparison_returns.empty:
                # 计算对比基金池的统计指标
                comp_stats_dict = calculate_statistics(comparison_returns)
                comp_stats_dict.update({
                    '基金代码': '对比基金池',
                    '区间': interval,
                    '类型': '对比基金'
                })
                statistics.append(comp_stats_dict)

                # 绘制对比基金池的核密度图
                x_vals_comp = np.sort(comparison_returns)
                y_vals_comp = stats.gaussian_kde(comparison_returns)(x_vals_comp)
                comparison_fund_name = '对比基金池'
                fig.add_trace(go.Scatter(
                    x=x_vals_comp,
                    y=y_vals_comp,
                    mode='lines',
                    name=f'对比基金池 - 区间 {interval}',
                    hovertemplate=f'{comparison_fund_name} 区间 {interval}: y=%{{y:.2f}}<extra></extra>'  # 显式设置 hover 信息的格式
                ))

    # 将统计指标转换为 DataFrame
    statistics_df = pd.DataFrame(statistics)
    return statistics_df, fig


# 计算每日收益率的通用函数
def calculate_daily_returns(data, column_name, returns_column="Adjusted_Returns"):
    """
    计算不同基金的每日收益率，按基金代码进行分组。
    """
    fund_groups = data.groupby('SecuCode')

    # 对每个基金分别计算每日收益率
    for fund_code, fund_data in fund_groups:
        initial_nv = fund_data[column_name].iloc[0]  # 获取每个基金的期初净值
        data.loc[fund_data.index, returns_column] = ((fund_data[column_name] / initial_nv) - 1) * 100  # 计算收益率

    return data


# 绘制每日收益率图的函数
def plot_daily_returns(data):
    """
    绘制不同基金的每日收益率曲线，应用自定义样式模板
    """
    # 将 Adjusted_Returns 和 Manager_Returns 限制为两位小数
    data['Adjusted_Returns'] = data['Adjusted_Returns'].round(2)
    data['Manager_Returns'] = data['Manager_Returns'].round(2)

    fig = go.Figure()

    # 对每个基金分别绘制调整后的每日收益率和管理人收益率
    fund_groups = data.groupby('SecuCode')

    for fund_code, fund_data in fund_groups:
        # 绘制调整后的每日收益率
        fig.add_trace(go.Scatter(
            x=fund_data['TradingDay'],
            y=fund_data['Adjusted_Returns'],
            mode='lines',
            name=f'{fund_code} - 调整后收益率',
            # hovertemplate=f'{fund_code} 调整后收益率: %{y:.2f}<extra></extra>'
        ))

        # 绘制管理人收益率
        fig.add_trace(go.Scatter(
            x=fund_data['TradingDay'],
            y=fund_data['Manager_Returns'],
            mode='lines',
            name=f'{fund_code} - 管理人收益率',
            # hovertemplate=f'{fund_code} 管理人收益率: %{y:.2f}<extra></extra>'
        ))

    # 应用我们之前定义的样式模板
    fig = apply_custom_layout(fig)

    return fig



#
# def show():
#     st.title("基金滚动收益率分布分析")
#
#     # 假设 'display_data' 已经存储在 session_state 中
#     if 'result_df' not in st.session_state:
#         st.error("未找到净值数据，请先在之前的页面中计算净值。")
#         return
#
#     data = st.session_state['result_df']
#
#     # 检查是否有对比基金池
#     comparison_fund_pool = st.session_state.get('comparison_fund_pool', None)
#     comparison_data = None
#     if comparison_fund_pool:
#         # 计算对比基金池的调整后净值
#         comparison_data = st.session_state['comparison_df']
#
#     # 创建 Streamlit 原生 Tabs
#     tab1, tab2, tab3 = st.tabs(["滚动收益率分布分析", "每日收益率", "管理人收益率滚动分布"])
#
#     with tab1:
#         st.header("滚动收益率分布分析")
#
#         # 选择区间
#         intervals = st.multiselect("选择滚动收益率的区间（以年为单位）", [1, 2, 3], default=[1], key="intervals_tab1")
#
#         # 基金选择框
#         research_funds_to_compare = st.multiselect(
#             "选择要分析的研究基金",
#             data['SecuCode'].unique(),
#             default=data['SecuCode'].unique(),
#             key="research_funds_tab1"
#         )
#
#         # 对比基金选择框，默认是对比基金池中的所有基金
#         comparison_funds_to_compare = st.multiselect(
#             "选择要分析的对比基金",
#             comparison_data['SecuCode'].unique() if comparison_data is not None else [],
#             default=[],
#             key="comparison_funds_tab1"
#         )
#
#         if st.button("开始分析", key="analyze_button_tab1"):
#             if not intervals:
#                 st.warning("请提供至少一个区间")
#                 return
#
#             # 计算滚动收益率并绘制图表
#             statistics_df, fig = plot_and_calculate_distributions(
#                 data, comparison_data, research_funds_to_compare, comparison_funds_to_compare, intervals,
#                 "AdjustedUnitNV"
#             )
#
#             if not statistics_df.empty:
#                 # 确保所有数值列都是数值型
#                 num_cols = ['最小值', '最大值', '平均值', '标准差', '中位数', '偏度', '峰度', '25%分位点', '75%分位点',
#                             '75%分位点-25%分位点', '左0.1%尾部', '右0.1%尾部']
#                 statistics_df[num_cols] = statistics_df[num_cols].apply(pd.to_numeric, errors='coerce')
#
#                 # 删除 "类型" 列，不让其参与透视表
#                 stats_pivot = statistics_df.drop(columns=['类型']).set_index(['基金代码', '区间']).T
#
#                 # 按行展示每个区间的统计指标，列保持为指标
#                 st.subheader("所有区间的统计指标")
#                 st.dataframe(stats_pivot)
#
#             # 展示核密度图
#             if fig:
#                 st.plotly_chart(fig)
#
#     with tab2:
#         st.header("每日收益率分析")
#
#         # 计算每日收益率
#         fund_data = data.copy()
#
#         # 计算调整后净值的每日收益率，列名为 Adjusted_Returns
#         fund_data = calculate_daily_returns(fund_data, 'AdjustedUnitNV', returns_column="Adjusted_Returns")
#
#         # 计算管理人净值的每日收益率，列名为 Manager_Returns
#         fund_data = calculate_daily_returns(fund_data, 'UnitNVRestored', returns_column="Manager_Returns")
#
#         # 显示每日收益率
#         st.subheader("每日收益率数据")
#         st.dataframe(fund_data[['TradingDay', 'AdjustedUnitNV', 'UnitNVRestored', 'Adjusted_Returns', 'Manager_Returns']])
#
#         # 绘制每日收益率图
#         st.subheader("每日收益率和净值图表")
#         fig = plot_daily_returns(fund_data)
#         st.plotly_chart(fig)
#
#     with tab3:
#         st.header("管理人收益率滚动分布分析")
#
#         # 选择区间
#         intervals = st.multiselect("选择管理人收益率滚动的区间（以年为单位）", [1, 2, 3], default=[1],
#                                    key="intervals_tab3")
#
#         # 基金选择框
#         research_funds_to_compare = st.multiselect(
#             "选择要分析的研究基金",
#             data['SecuCode'].unique(),
#             default=data['SecuCode'].unique(),
#             key="research_funds_tab3"
#         )
#
#         # 对比基金选择框
#         comparison_funds_to_compare = st.multiselect(
#             "选择要分析的对比基金",
#             comparison_data['SecuCode'].unique() if comparison_data is not None else [],
#             default=[],
#             key="comparison_funds_tab3"
#         )
#
#         if st.button("分析管理人收益率滚动分布", key="analyze_button_tab3"):
#             if not intervals:
#                 st.warning("请提供至少一个区间")
#                 return
#
#             # 基于复权单位净值的管理人收益率的滚动计算
#             statistics_df, fig = plot_and_calculate_distributions(
#                 data, comparison_data, research_funds_to_compare, comparison_funds_to_compare, intervals,
#                 "UnitNVRestored"
#             )
#
#             if not statistics_df.empty:
#                 # 确保所有数值列都是数值型
#                 num_cols = ['最小值', '最大值', '平均值', '标准差', '中位数', '偏度', '峰度', '25%分位点', '75%分位点',
#                             '75%分位点-25%分位点', '左0.1%尾部', '右0.1%尾部']
#                 statistics_df[num_cols] = statistics_df[num_cols].apply(pd.to_numeric, errors='coerce')
#
#                 # 删除 "类型" 列，不让其参与透视表
#                 stats_pivot = statistics_df.drop(columns=['类型']).set_index(['基金代码', '区间']).T
#
#                 # 按行展示每个区间的统计指标，列保持为指标
#                 st.subheader("所有区间的统计指标")
#                 st.dataframe(stats_pivot)
#
#             # 展示核密度图
#             if fig:
#                 st.plotly_chart(fig)

# 生成核密度图时添加自定义样式
def apply_custom_layout(fig):
    fig.update_layout(
        width=1200,  # 设置图表的宽度
        height=500,  # 设置图表的高度
        title="基金净值曲线",
        # xaxis_title="日期",  # 不需要 x 轴标题
        yaxis_title="净值",
        hovermode='x unified',  # 设置 hovermode
        legend=dict(
            orientation="h",  # 将图例横向排列
            yanchor="bottom",  # 图例的 y 锚点设为底部
            y=-0.2,  # 图例放在图表的下方
            xanchor="center",  # 图例的 x 锚点设为中心
            x=0.5  # 将图例居中
        ),
        # 自定义 X 轴
        xaxis=dict(
            tickformat="%Y-%m-%d",  # 显示年份、月份、日期
            nticks=10,
            ticklabelmode="period",  # 设置日期刻度的显示方式
            showline=True,  # 显示X轴线
            linewidth=1.5,  # X轴线宽度
            linecolor='grey',  # X轴线颜色
            ticks="inside",  # 刻度线在外
            ticklen=4,  # 刻度线的长度
            tickwidth=1,  # 刻度线宽度
            tickcolor='grey'  # 刻度线颜色
        ),
        # 自定义 Y 轴
        yaxis=dict(
            showline=True,  # 显示Y轴线
            linewidth=1.5,  # Y轴线宽度
            linecolor='grey',  # Y轴线颜色
            ticks="inside",  # 刻度线在外
            ticklen=4,  # 刻度线的长度
            tickwidth=1,  # 刻度线宽度
            tickcolor='grey'  # 刻度线颜色
        ),
        # 自定义图表背景
        plot_bgcolor='white',  # 设置背景颜色为白色
    )

    return fig


def analyze_rolling_returns(tab_title, column_name, result_key, data, comparison_data):
    st.header(tab_title)

    # 选择区间
    intervals = st.multiselect(f"选择{tab_title}的区间（以年为单位）", [0.5, 1, 2, 3, 5], default=[1],
                               key=f"intervals_{result_key}")

    # 基金选择框
    research_funds_to_compare = st.multiselect(
        "选择要分析的研究基金",
        data['SecuCode'].unique(),
        default=data['SecuCode'].unique(),
        key=f"research_funds_{result_key}"
    )

    # 对比基金选择框
    comparison_funds_to_compare = st.multiselect(
        "选择要分析的对比基金",
        comparison_data['SecuCode'].unique() if comparison_data is not None else [],
        default=[],
        key=f"comparison_funds_{result_key}"
    )

    if st.button(f"分析{tab_title}", key=f"analyze_button_{result_key}"):
        if not intervals:
            st.warning("请提供至少一个区间")
            return

        # 计算滚动收益率并绘制图表
        statistics_df, fig = plot_and_calculate_distributions(
            data, comparison_data, research_funds_to_compare, comparison_funds_to_compare, intervals,
            column_name
        )

        # 将计算结果保存到 session_state
        st.session_state[f'stats_df_{result_key}'] = statistics_df
        st.session_state[f'fig_{result_key}'] = fig

    # 如果之前已经计算过，直接从 session_state 中读取
    if f'stats_df_{result_key}' in st.session_state and f'fig_{result_key}' in st.session_state:
        statistics_df = st.session_state[f'stats_df_{result_key}']
        fig = st.session_state[f'fig_{result_key}']

        if not statistics_df.empty:
            # 确保所有数值列都是数值型
            num_cols = ['最小值', '最大值', '平均值', '标准差', '中位数', '偏度', '峰度', '25%分位点', '75%分位点',
                        '75%分位点-25%分位点', '左0.1%尾部', '右0.1%尾部']
            statistics_df[num_cols] = statistics_df[num_cols].apply(pd.to_numeric, errors='coerce')

            # 删除 "类型" 列，不让其参与透视表
            stats_pivot = statistics_df.drop(columns=['类型']).set_index(['基金代码', '区间']).T

            # 按行展示每个区间的统计指标，列保持为指标
            st.subheader(f"所有区间的{tab_title}统计指标")
            st.dataframe(stats_pivot)

        # 展示核密度图
        if fig:
            fig = apply_custom_layout(fig)
            st.plotly_chart(fig)


def show():
    st.title("基金收益率分析")

    # 检查 'result_df' 是否在 session_state 中
    if 'result_df' not in st.session_state:
        st.error("未找到净值数据，请先在之前的页面中计算净值。")
        return

    data = st.session_state['result_df']

    # 检查是否有对比基金池
    comparison_fund_pool = st.session_state.get('comparison_fund_pool', None)
    comparison_data = None
    if comparison_fund_pool:
        comparison_data = st.session_state['comparison_df']

    # 创建 tabs
    tab1, tab2, tab3 = st.tabs(["滚动收益率分布分析", "每日收益率", "管理人收益率滚动分布"])

    # 滚动收益率分布分析
    with tab1:
        analyze_rolling_returns("滚动收益率分布分析", "AdjustedUnitNV", "tab1", data, comparison_data)

    # 每日收益率分析
    with tab2:
        st.header("每日收益率分析")

        # 计算每日收益率
        fund_data = data.copy()

        # 计算调整后净值的每日收益率
        fund_data = calculate_daily_returns(fund_data, 'AdjustedUnitNV', returns_column="Adjusted_Returns")

        # 计算管理人净值的每日收益率
        fund_data = calculate_daily_returns(fund_data, 'UnitNVRestored', returns_column="Manager_Returns")

        # 展示每日收益率
        st.subheader("每日收益率数据")
        st.dataframe(
            fund_data[['TradingDay', 'AdjustedUnitNV', 'UnitNVRestored', 'Adjusted_Returns', 'Manager_Returns']])

        # 绘制每日收益率图
        st.subheader("每日收益率和净值图表")
        fig = plot_daily_returns(fund_data)
        st.plotly_chart(fig)

    # 管理人收益率滚动分布分析
    with tab3:
        analyze_rolling_returns("管理人收益率滚动分布分析", "UnitNVRestored", "tab3", data, comparison_data)
