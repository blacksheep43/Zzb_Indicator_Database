import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
import streamlit_antd_components as sac
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go


@st.cache_resource
def create_db_engine():
    db_config = st.secrets["connections"]["my_database"]

    # 构建连接字符串
    driver = db_config["driver"].replace(" ", "+")  # 替换空格为加号
    user = db_config["username"]
    password = db_config["password"]
    server = db_config["host"]
    port = db_config["port"]
    database = db_config["database"]

    con_str = f"mssql+pyodbc://{user}:{password}@{server}:{port}/{database}?driver={driver}"
    engine = create_engine(con_str, fast_executemany=True)
    return engine


engine = create_db_engine()


@st.cache_data
def query_fund_data(_engine, fund_main_code, start_date, end_date):
    try:
        with _engine.connect() as conn:
            # 创建临时表
            create_temp_table_sql = '''
            CREATE TABLE #MainCodes (
                SecuCode VARCHAR(50)
            );
            '''
            conn.execute(text(create_temp_table_sql))

            # 插入数据到临时表
            insert_sql = 'INSERT INTO #MainCodes (SecuCode) VALUES (:secu_code)'
            for secu_code in fund_main_code:
                conn.execute(text(insert_sql), {"secu_code": secu_code})

            # 确保日期参数转换为字符串格式 YYYY-MM-DD
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            # 查询拆分、分红和净值数据，直接返回结果
            sql = '''
            WITH AllDates AS (
                SELECT m.InnerCode, m.TradingDay
                FROM MF_NetValuePerformanceHis m
                WHERE m.TradingDay BETWEEN :start_date AND :end_date
                UNION ALL
                SELECT d.InnerCode, d.ExRightDate AS TradingDay
                FROM MF_Dividend d
                WHERE d.ExRightDate BETWEEN :start_date AND :end_date
                UNION ALL
                SELECT ss.InnerCode, ss.ActualSplitDay AS TradingDay
                FROM MF_SharesSplit ss
                WHERE ss.ActualSplitDay BETWEEN :start_date AND :end_date
            )
            SELECT 
                a.InnerCode, 
                s.SecuCode, 
                s.ChiName, 
                a.TradingDay,
                MAX(d.ActualRatioAfterTax / 10) AS ActualRatioAfterTax,   -- 聚合分红数据
                MAX(ss.SplitRatio) AS SplitRatio,                        -- 聚合拆分数据
                MAX(m.UnitNV) AS UnitNV,                                 -- 聚合单位净值数据
                MAX(f.UnitNVRestored) AS UnitNVRestored                  -- 聚合复权单位净值数据
            FROM AllDates a
            LEFT JOIN SecuMain s ON a.InnerCode = s.InnerCode
            LEFT JOIN MF_Dividend d ON a.InnerCode = d.InnerCode AND a.TradingDay = d.ExRightDate
            LEFT JOIN MF_SharesSplit ss ON a.InnerCode = ss.InnerCode AND a.TradingDay = ss.ActualSplitDay
            LEFT JOIN MF_NetValuePerformanceHis m ON a.InnerCode = m.InnerCode AND a.TradingDay = m.TradingDay
            LEFT JOIN MF_FundNetValueRe f ON a.InnerCode = f.InnerCode AND a.TradingDay = f.TradingDay
            JOIN #MainCodes mc ON s.SecuCode = mc.SecuCode  -- 使用 SecuMain 表关联 SecuCode
            WHERE s.SecuCategory = 8
            GROUP BY 
                a.InnerCode, 
                s.SecuCode, 
                s.ChiName, 
                a.TradingDay
            ORDER BY 
                s.SecuCode, 
                a.TradingDay;


            '''

            # 确保 `params` 正确绑定日期
            df = pd.read_sql_query(text(sql), conn, params={"start_date": start_date_str, "end_date": end_date_str})

            # 清除临时表
            conn.execute(text('DROP TABLE #MainCodes'))

        return df

    except Exception as e:
        st.error(f"查询数据时出错: {e}")
        print(f"查询数据时出错: {e}")
        return pd.DataFrame()  # 返回空数据框以防止应用崩溃


# def show():
#     st.title("提取净值")
#
#     # 手动输入基金代码部分
#     st.header("手动输入基金代码")
#     fund_code_input = st.text_input("请输入基金代码（例如：000014）：", value="")
#
#     # Excel 文件上传部分
#     st.header("或上传包含 SecuCode 的 Excel 文件")
#     uploaded_file = st.file_uploader("上传一个包含 SecuCode 的 Excel 文件", type="xlsx")
#
#     # 检查用户是通过手动输入还是上传 Excel 文件来提供 SecuCode
#     if st.button("查询"):
#         secucodes = []
#
#         if fund_code_input:
#             # 手动输入的基金代码
#             secucodes = [code.strip() for code in fund_code_input.split(",")]
#             st.session_state['secucodes'] = secucodes
#             st.success(f"基金代码 {fund_code_input} 已保存。")
#
#         elif uploaded_file is not None:
#             # 上传 Excel 文件并读取 SecuCode 列
#             df = pd.read_excel(uploaded_file)
#             if 'SecuCode' in df.columns:
#                 secucodes = df['SecuCode'].tolist()
#                 st.session_state['secucodes'] = secucodes
#                 st.success(f"成功读取 {len(secucodes)} 个 SecuCode。")
#             else:
#                 st.error("Excel 文件中未找到 'SecuCode' 列。")
#
#         if secucodes:
#
#             # 调用 query_fund_data 函数来获取基金数据
#             result_df = query_fund_data(engine, secucodes)
#
#             if not result_df.empty:
#                 # 显示查询结果
#                 st.write("查询结果如下：")
#                 st.dataframe(result_df, use_container_width=True)
#
#                 # 提供下载为 Excel 文件的选项
#                 output = BytesIO()
#                 with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
#                     result_df.to_excel(writer, index=False, sheet_name='Sheet1')
#                 processed_data = output.getvalue()
#
#                 st.download_button(
#                     label="下载结果为 Excel",
#                     data=processed_data,
#                     file_name='基金净值数据.xlsx',
#                     mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#                 )
#             else:
#                 st.write("未找到符合条件的基金数据。")
#         else:
#             st.warning("请提供基金代码或上传包含基金代码的 Excel 文件。")
# 自定义 CSS 调整控件对齐，并向下移动右侧开关

def secucode_input(key=""):
    col1, col2 = st.columns([4, 1])

    with col1:
        # 手动输入基金代码部分，添加唯一的 key
        fund_code_input = st.text_input("请输入基金代码（例如：000014）：", value="", key=f"{key}_fund_code_input")
        if fund_code_input:
            st.session_state['secucodes'] = fund_code_input.split(",")
            st.success("基金代码已保存。")

    with col2:
        show_uploader = sac.switch(label='上传文件', align='center', size='md',
                                   description='请上传一个带有需要查询的SecuCode列（去除后缀的基金代码）的excel文件',
                                   radius='xs', key=f"{key}_switch")

    secucodes = []

    # 根据 sac.switch 的开关状态显示上传器，添加唯一的 key
    if show_uploader:
        uploaded_file = st.file_uploader("上传一个包含 SecuCode 的 Excel 文件", type="xlsx", key=f"{key}_file_uploader")
        if uploaded_file is not None:
            # 处理上传的文件
            df = pd.read_excel(uploaded_file, converters={'SecuCode': str})
            if 'SecuCode' in df.columns:
                secucodes = df['SecuCode'].dropna().tolist()
                st.session_state['secucodes'] = secucodes
                st.success(f"成功读取 {len(secucodes)} 个基金代码")
            else:
                st.error("文件中未找到 'SecuCode' 列")

    return st.session_state.get('secucodes', [])


def save_net_value_data(data):
    st.session_state[f'{data}'] = data


def get_net_value_data():
    return st.session_state.get('net_value_data', pd.DataFrame())


def download_large_dataframe(df, filename="data.xlsx", sheet_name_prefix="Sheet", max_rows_per_sheet=1048576):
    """
    将一个大的 DataFrame 拆分成多个工作表，并生成下载按钮。

    :param df: 需要下载的 DataFrame
    :param filename: 下载的文件名
    :param sheet_name_prefix: 每个工作表的前缀名称
    :param max_rows_per_sheet: 每个工作表最多包含的行数
    :return: 生成 Streamlit 下载按钮
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        num_sheets = (len(df) // max_rows_per_sheet) + 1

        for i in range(num_sheets):
            start_row = i * max_rows_per_sheet
            end_row = start_row + max_rows_per_sheet
            df.iloc[start_row:end_row].to_excel(writer, index=False, sheet_name=f'{sheet_name_prefix}{i + 1}')

    processed_data = output.getvalue()

    st.download_button(
        label=f"下载结果为 {filename}",
        data=processed_data,
        file_name=filename,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# 设置页面配置为宽模式

# def calculate_adjustment_coefficients(data, cutoff_date):
#     '''
#     本函数用于计算每个基金从成立至截止日期的所有调整系数 a 和 b，并将结果保存在 DataFrame 中。
#     '''
#     # 按日期排序并过滤截止日期之前的数据
#     data = data.sort_values(by=['SecuCode', 'TradingDay']).copy()
#     data['TradingDay'] = pd.to_datetime(data['TradingDay'])
#     data = data[data['TradingDay'] <= pd.to_datetime(cutoff_date)]
#
#     # 确保 SplitRatio 列为数值类型，如果无法转换则填充为1.0
#     data['SplitRatio'] = pd.to_numeric(data['SplitRatio'], errors='coerce').fillna(1.0)
#
#     # 初始化调整系数 a 和 b
#     data['a'] = data.groupby('SecuCode')['SplitRatio'].cumprod()
#
#     # 计算 b，使用a的前一行值和当前行的ActualRatioAfterTax
#     data['ActualRatioAfterTax'] = pd.to_numeric(data['ActualRatioAfterTax'], errors='coerce').fillna(0.0)
#     data['b'] = (data['a'].shift(1, fill_value=1.0) * data['ActualRatioAfterTax']).groupby(data['SecuCode']).cumsum()
#
#     return data


@st.cache_data
def generate_excel_file(df, sheet_name_prefix="Sheet", max_rows_per_sheet=1000000):
    """
    生成 Excel 文件并缓存起来。

    :param df: 需要下载的 DataFrame
    :param sheet_name_prefix: 每个工作表的前缀名称
    :param max_rows_per_sheet: 每个工作表最多包含的行数
    :return: 生成的 Excel 文件数据
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        num_sheets = (len(df) // max_rows_per_sheet) + 1

        for i in range(num_sheets):
            start_row = i * max_rows_per_sheet
            end_row = start_row + max_rows_per_sheet
            df.iloc[start_row:end_row].to_excel(writer, index=False, sheet_name=f'{sheet_name_prefix}{i + 1}')

    return output.getvalue()


# def show():
#     st.title("调整系数计算")
#
#     # 检查是否有提取出的净值数据
#     data = get_net_value_data()
#     if data.empty:
#         st.warning("请先在提取净值页面提取数据。")
#         return
#
#     # 使用公用的 secucode 输入函数
#     secucodes = secucode_input()
#
#     if secucodes:
#         # 日期选择器
#         cutoff_date = st.date_input("选择截止日期", value=datetime.date.today(), min_value=datetime.date(1980, 1, 1))
#
#         # 触发计算的按钮
#         if st.button("计算调整系数"):
#             # 筛选出用户选择的 secucodes
#             filtered_data = data[data['SecuCode'].isin(secucodes)]
#
#             if not filtered_data.empty:
#                 result_data = calculate_adjustment_coefficients(filtered_data, cutoff_date)
#                 st.session_state['result_data'] = result_data  # 将计算结果存入 session_state
#                 st.write("计算结果：")
#                 st.dataframe(result_data, use_container_width=True)
#
#         # 检查是否已经有计算结果存储在 session_state 中
#         if 'result_data' in st.session_state:
#             # 提供生成和下载文件的按钮
#             if st.button("生成下载文件"):
#                 # 确保在点击"生成并下载文件"按钮时才执行文件生成
#                 processed_data = generate_excel_file(st.session_state['result_data'])
#
#                 # 下载文件
#                 st.download_button(
#                     label="点击下载",
#                     data=processed_data,
#                     file_name='基金分红拆分净值.xlsx',
#                     mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
#                 )


# 各个计算函数
def calculate_adjustment_coefficients(data):
    # 确保 SplitRatio 列为数值类型，如果不能转换则填充为 1.0
    data['SplitRatio'] = pd.to_numeric(data['SplitRatio'], errors='coerce').fillna(1.0)

    # 确保 ActualRatioAfterTax 列为数值类型，如果不能转换则填充为 0.0
    data['ActualRatioAfterTax'] = pd.to_numeric(data['ActualRatioAfterTax'], errors='coerce').fillna(0.0)

    data['a'] = 1.0
    data['b'] = 0.0

    data['a'] = data.groupby('SecuCode')['SplitRatio'].cumprod()
    data['b'] = (
            data['a'].shift(1, fill_value=1.0) * data['ActualRatioAfterTax']
    ).groupby(data['SecuCode']).cumsum()
    return data


def calculate_adjusted_unitnv(data):
    data['AdjustedUnitNV'] = data['UnitNV'] * data['a'] + data['b']
    return data


def secucode_input_with_upload(label, text_input_label, upload_button_label, key):
    """
    封装的输入和文件上传功能函数

    参数:
    - label: 输入框的描述标签
    - text_input_label: 手动输入框的提示
    - upload_button_label: 上传按钮的标签
    - key: session_state 中存储状态的键
    """
    # 添加自定义 CSS 样式，使按钮和输入框高度一致
    st.markdown(
        """
        <style>
        .stButton button {
            margin-top: 27px; /* 调整按钮的上边距，使其向下移动 */
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.subheader(label)

    # 手动输入基金代码，保存在 session_state 中
    if f'{key}_input' not in st.session_state:
        st.session_state[f'{key}_input'] = ""

    # 初始化上传状态为 False，防止未初始化时报错
    if f'{key}_upload' not in st.session_state:
        st.session_state[f'{key}_upload'] = False

    col1, col2 = st.columns([4, 1])

    with col1:
        st.session_state[f'{key}_input'] = st.text_input(text_input_label, value=st.session_state[f'{key}_input'])

    with col2:
        if st.button(upload_button_label, key=f"{key}_upload_button"):
            st.session_state[f'{key}_upload'] = not st.session_state[f'{key}_upload']

    # 如果按钮被点击，显示上传框
    if st.session_state[f'{key}_upload']:
        uploaded_file = st.file_uploader("上传文件", type="xlsx", key=f"{key}_file_uploader")
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file, converters={'SecuCode': str})
            st.session_state[f"{key}_data"] = df['SecuCode'].tolist()  # 假设文件中有 'SecuCode' 列
            st.success(f"上传成功，共读取到 {len(df)} 条基金代码")
        else:
            st.warning("请上传一个包含基金代码的 Excel 文件")

    # 合并手动输入的基金代码和上传的基金代码
    all_fund_codes = st.session_state[f'{key}_input'].split(',') if st.session_state[f'{key}_input'] else []
    if f'{key}_data' in st.session_state:
        all_fund_codes += st.session_state[f'{key}_data']

    # 更新 secucodes 到 session_state
    st.session_state[f'{key}_codes'] = list(set([x.strip() for x in all_fund_codes if x.strip()]))

    # 返回 session_state 中的基金代码列表，保持与之前的逻辑一致
    return st.session_state.get(f'{key}_codes', [])


def show():
    st.title("基金净值分析")

    # 使用封装的 secucode_input_with_upload 函数来输入研究基金代码
    secucodes = secucode_input_with_upload(
        label="研究基金输入",
        text_input_label="请输入研究基金代码：",
        upload_button_label="上传",
        key="research_fund_input"
    )

    # 使用封装的 secucode_input_with_upload 函数来输入对比基金池的基金代码
    comparison_fund_pool = secucode_input_with_upload(
        label="对比基金池输入",
        text_input_label="请输入对比基金代码：",
        upload_button_label="上传",
        key="comparison_fund_input"
    )

    # 保存对比基金池到 session_state
    if st.button("保存对比基金池"):
        if comparison_fund_pool:
            st.session_state['comparison_fund_pool'] = comparison_fund_pool
            st.success("对比基金池已保存。")
        else:
            st.warning("请输入至少一个基金代码。")

    # 日期选择
    start_date = st.date_input("选择开始日期", value=datetime.date(2023, 1, 1), min_value=datetime.date(1980, 1, 1))
    end_date = st.date_input("选择结束日期", value=datetime.date.today(), min_value=start_date)
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date

    # 保存查询按钮的状态
    if "query_clicked" not in st.session_state:
        st.session_state['query_clicked'] = False

    # 查询数据并存储
    if st.button("查询"):
        if secucodes:
            result_df = query_fund_data(engine, secucodes, st.session_state['start_date'], st.session_state['end_date'])
            if not result_df.empty:
                # 计算调整系数和调整后的净值
                result_df = calculate_adjustment_coefficients(result_df)
                result_df = calculate_adjusted_unitnv(result_df)

                # 保存查询数据到 session_state
                st.session_state['query_clicked'] = True
                st.session_state['result_df'] = result_df

                # 对比基金池处理
                if 'comparison_fund_pool' in st.session_state:
                    comparison_fund_list = st.session_state['comparison_fund_pool']
                    comparison_df = query_fund_data(engine, comparison_fund_list, st.session_state['start_date'],
                                                    st.session_state['end_date'])
                    if not comparison_df.empty:
                        # 计算对比基金的调整系数和净值
                        comparison_df = calculate_adjustment_coefficients(comparison_df)
                        comparison_df = calculate_adjusted_unitnv(comparison_df)
                        st.session_state['comparison_df'] = comparison_df

                st.success("查询和计算完成")
            else:
                st.write("未找到符合条件的基金数据。")
        else:
            st.warning("请提供基金代码或上传包含基金代码的 Excel 文件。")

    # 如果已经查询数据，展示基金数据
    if 'query_clicked' in st.session_state and st.session_state['query_clicked']:
        if 'result_df' in st.session_state:
            result_df = st.session_state['result_df']

            # 使用 sac.checkbox 创建复选框
            selected_items = sac.checkbox(
                items=[
                    '调整系数 (a, b)',
                    '调整后净值',
                    '复权单位净值'
                ],
                label='选择要显示的内容'
            )

            # 初始化显示数据，包含基础的 TradingDay 和 UnitNV 信息
            display_data = result_df[['SecuCode', 'ChiName', 'TradingDay', 'UnitNV']].copy()

            # 如果用户选择了 "调整系数 (a, b)"，则显示调整系数
            if '调整系数 (a, b)' in selected_items:
                display_data = pd.merge(display_data, result_df[['TradingDay', 'SecuCode', 'a', 'b']],
                                        on=['TradingDay', 'SecuCode'], how='left')

            # 如果用户选择了 "调整后净值"，则显示调整后的净值
            if '调整后净值' in selected_items:
                display_data = pd.merge(display_data, result_df[['TradingDay', 'SecuCode', 'AdjustedUnitNV']],
                                        on=['TradingDay', 'SecuCode'], how='left')

            # 如果用户选择了 "复权单位净值"，则显示复权净值
            if '复权单位净值' in selected_items:
                display_data = pd.merge(display_data, result_df[['TradingDay', 'SecuCode', 'UnitNVRestored']],
                                        on=['TradingDay', 'SecuCode'], how='left')

            # 显示研究基金的净值表格
            st.dataframe(display_data[display_data['SecuCode'].isin(secucodes)], use_container_width=True)

            st.session_state['display_data'] = display_data

            # 添加绘图部分，默认绘制"累计净值"
            plot_data = pd.DataFrame({'日期': display_data['TradingDay'], '累计净值': display_data['UnitNV'], 'SecuCode': display_data['SecuCode']})
            # st.write(plot_data)
            # 动态添加其他净值曲线
            if '调整后净值' in selected_items and 'AdjustedUnitNV' in display_data.columns:
                plot_data['调整后净值'] = display_data['AdjustedUnitNV']

            if '复权单位净值' in selected_items and 'UnitNVRestored' in display_data.columns:
                plot_data['复权单位净值'] = display_data['UnitNVRestored']

            # 检查 plot_data 是否为空，避免图表消失
            if not plot_data.empty:
                fig = go.Figure()

                # 根据基金代码分组
                for fund_code, fund_data in plot_data.groupby('SecuCode'):

                    # 添加累计净值曲线
                    fig.add_trace(go.Scatter(
                        x=fund_data['日期'], y=fund_data['累计净值'],
                        mode='lines', name=f'{fund_code} 累计净值',
                        # hovertemplate=f'{fund_code} 累计净值: %{y:.2f}<extra></extra>'  # 使用 Plotly 的 %{y} 占位符来引用 y 轴值
                    ))

                    # 根据选择动态添加其他曲线
                    if '调整后净值' in selected_items and '调整后净值' in fund_data.columns:
                        fig.add_trace(go.Scatter(
                            x=fund_data['日期'], y=fund_data['调整后净值'],
                            mode='lines', name=f'{fund_code} 调整后净值',
                            # hovertemplate=f'{fund_code} 累计净值: %{y:.2f}<extra></extra>'  # 使用 Plotly 的 %{y} 占位符来引用 y 轴值
                        ))

                    if '复权单位净值' in selected_items and '复权单位净值' in fund_data.columns:
                        fig.add_trace(go.Scatter(
                            x=fund_data['日期'], y=fund_data['复权单位净值'],
                            mode='lines', name=f'{fund_code} 复权单位净值',
                            # hovertemplate=f'{fund_code} 累计净值: %{y:.2f}<extra></extra>'  # 使用 Plotly 的 %{y} 占位符来引用 y 轴值
                        ))


                fig.update_layout(
                    width=1200,  # 设置图表的宽度
                    height=500,  # 设置图表的高度
                    title="基金净值曲线",
                    # xaxis_title="日期",
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
                        # dtick="M6",  # 每6个月显示一个刻度
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

                # 绘制图表
                st.plotly_chart(fig, use_container_width=False)

            # 下载表格功能
            if 'display_data' in st.session_state:
                if st.button("生成下载文件"):
                    processed_data = generate_excel_file(st.session_state['display_data'])
                    st.download_button(
                        label="点击下载",
                        data=processed_data,
                        file_name='基金净值分析.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    )
