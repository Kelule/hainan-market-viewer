import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import datetime

# ================= 1. 网页基础设置 =================
st.set_page_config(page_title="海南电力交易复盘看板", layout="wide", page_icon="⚡")
st.title("⚡ 海南电力市场多维复盘看板 (查阅端)")

EXCEL_FILE = "批量交易日报_历史对比大表.xlsx"

# ================= 2. 数据读取与处理 =================
@st.cache_data
def load_data():
    if not os.path.exists(EXCEL_FILE):
        return None, None, None, None
            
    df_hourly = pd.read_excel(EXCEL_FILE, sheet_name='现货分时量价')
    df_spot = pd.read_excel(EXCEL_FILE, sheet_name='现货指标')
    df_ml = pd.read_excel(EXCEL_FILE, sheet_name='中长期指标')
    df_ml_source = pd.read_excel(EXCEL_FILE, sheet_name='中长期分电源')
    
    if df_hourly.empty: return None, None, None, None

    df_spot = df_spot.sort_values(by='日期').reset_index(drop=True)
    df_ml = df_ml.sort_values(by='日期').reset_index(drop=True)
    df_ml_source = df_ml_source.sort_values(by='日期').reset_index(drop=True)

    df_hourly['日期'] = pd.to_datetime(df_hourly['日期'])
    df_da = df_hourly[['日期', '时刻', '发电侧日前市场分时出清电量', '发电侧日前市场分时出清加权平均价', '日前用户侧统一结算点电价']].copy()
    df_da.rename(columns={'日期': '运行日'}, inplace=True)
    df_rt = df_hourly[['日期', '时刻', '发电侧实时市场分时出清电量', '发电侧实时市场分时出清加权平均价', '实时用户侧统一结算点电价']].copy()
    df_rt['运行日'] = df_rt['日期'] - pd.Timedelta(days=1)
    df_rt.drop(columns=['日期'], inplace=True)
    
    df_hourly_aligned = pd.merge(df_da, df_rt, on=['运行日', '时刻'], how='outer')
    df_hourly_aligned = df_hourly_aligned.dropna(subset=['运行日']) 
    df_hourly_aligned['运行日'] = df_hourly_aligned['运行日'].dt.strftime('%Y-%m-%d')
    df_hourly_aligned = df_hourly_aligned.sort_values(by=['运行日', '时刻']).reset_index(drop=True)
    df_hourly_aligned['实时-日前价差'] = df_hourly_aligned['发电侧实时市场分时出清加权平均价'] - df_hourly_aligned['发电侧日前市场分时出清加权平均价']

    df_spot['日期'] = pd.to_datetime(df_spot['日期'])
    spot_da = df_spot[['日期', '指标大类', '指标名称', '日前市场', '单位']].copy()
    spot_da.rename(columns={'日期': '运行日'}, inplace=True)
    spot_rt = df_spot[['日期', '指标大类', '指标名称', '实时市场', '单位']].copy()
    spot_rt['运行日'] = spot_rt['日期'] - pd.Timedelta(days=1)
    spot_rt.drop(columns=['日期'], inplace=True)
    
    df_spot_aligned = pd.merge(spot_da, spot_rt, on=['运行日', '指标大类', '指标名称', '单位'], how='outer')
    df_spot_aligned = df_spot_aligned.dropna(subset=['运行日'])
    df_spot_aligned['运行日'] = df_spot_aligned['运行日'].dt.strftime('%Y-%m-%d')
    df_spot_aligned = df_spot_aligned.sort_values(by=['运行日', '指标名称']).reset_index(drop=True)

    return df_hourly_aligned, df_spot_aligned, df_ml, df_ml_source

df_hourly_aligned, df_spot_aligned, df_ml, df_ml_source = load_data()

if df_hourly_aligned is None:
    st.info("🚧 管理员尚未上传最新数据，请稍后再来查看。")
    st.stop()

# ================= 3. 定义时间视窗 =================
max_date_str = df_hourly_aligned['运行日'].max()
max_date = datetime.datetime.strptime(max_date_str, "%Y-%m-%d")
default_start_date = (max_date - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
min_date_str = df_hourly_aligned['运行日'].min()

def apply_time_window(fig, time_col="日期"):
    fig.update_xaxes(range=[default_start_date, max_date_str], rangeslider_visible=False)
    return fig

# ================= 4. 页面布局 =================
tab1, tab2, tab3 = st.tabs(["📊 现货分时博弈 (2D/3D)", "📈 现货宏观指标", "🏛️ 中长期市场复盘"])

# ----------------- Tab 1: 现货分时博弈 -----------------
with tab1:
    view_mode = st.radio("请选择观测视角：", ["📊 经典 2D：单日精细对齐复盘", "🧊 实验性 3D：多日瀑布折线图 (书籍排布法)"], horizontal=True)
    
    if view_mode == "📊 经典 2D：单日精细对齐复盘":
        # 🌟 改进 1：将下拉菜单改为日历组件 🌟
        selected_date_obj = st.date_input(
            "📅 选择要复盘的运行日：",
            value=max_date.date(),
            min_value=datetime.datetime.strptime(min_date_str, "%Y-%m-%d").date(),
            max_value=max_date.date()
        )
        selected_date = selected_date_obj.strftime("%Y-%m-%d")
        daily_data = df_hourly_aligned[df_hourly_aligned['运行日'] == selected_date]
        
        if daily_data.empty:
            st.warning(f"⚠️ {selected_date} 当天没有分时数据记录，请尝试选择其他日期。")
        else:
            fig_h = make_subplots(specs=[[{"secondary_y": True}]])
            fig_h.add_trace(go.Bar(x=daily_data['时刻'], y=daily_data['发电侧实时市场分时出清电量'], name='实时电量', marker_color='lightblue', opacity=0.6), secondary_y=True)
            fig_h.add_trace(go.Bar(x=daily_data['时刻'], y=daily_data['发电侧日前市场分时出清电量'], name='日前电量', marker_color='lightgray', opacity=0.6), secondary_y=True)
            fig_h.add_trace(go.Scatter(x=daily_data['时刻'], y=daily_data['发电侧实时市场分时出清加权平均价'], mode='lines+markers', name='实时均价', line=dict(color='firebrick', width=3)), secondary_y=False)
            fig_h.add_trace(go.Scatter(x=daily_data['时刻'], y=daily_data['发电侧日前市场分时出清加权平均价'], mode='lines+markers', name='日前均价', line=dict(color='royalblue', width=3)), secondary_y=False)
    
            fig_h.update_layout(title=f"{selected_date} 真正对齐量价对比", hovermode="x unified", height=600, barmode='group')
            st.plotly_chart(fig_h, use_container_width=True)

    else:
        st.markdown("**使用指南**：拖拽旋转视角，滚轮缩放大小。不同颜色的线条代表不同日期的价格走势，犹如书架上依次排列的书籍。")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            surface_target = st.selectbox("选择要渲染的三维数据：", ["发电侧日前市场分时出清加权平均价", "发电侧实时市场分时出清加权平均价", "实时-日前价差"])
        with col2:
            selected_dates = st.date_input(
                "🗓️ 选择要查看的历史时间段：",
                value=(datetime.datetime.strptime(default_start_date, "%Y-%m-%d").date(), max_date.date()),
                min_value=datetime.datetime.strptime(min_date_str, "%Y-%m-%d").date(),
                max_value=max_date.date()
            )
        
        if len(selected_dates) == 2:
            start_date_filter, end_date_filter = selected_dates
        else:
            start_date_filter = selected_dates[0]
            end_date_filter = max_date.date()

        start_str = start_date_filter.strftime("%Y-%m-%d")
        end_str = end_date_filter.strftime("%Y-%m-%d")
        df_recent_3d = df_hourly_aligned[(df_hourly_aligned['运行日'] >= start_str) & (df_hourly_aligned['运行日'] <= end_str)]
        
        if df_recent_3d.empty:
            st.warning("⚠️ 在所选的时间段内没有找到数据，请重新选择日期范围。")
        else:
            df_pivot = pd.pivot_table(df_recent_3d, values=surface_target, index='运行日', columns='时刻', aggfunc='mean')
            fig_3d = go.Figure()
            colors = px.colors.sequential.Viridis if "日前" in surface_target else (px.colors.sequential.Reds if "实时" in surface_target else px.colors.sequential.RdBu_r)
            
            for i, row_date in enumerate(df_pivot.index):
                color_index = int((i / max(1, len(df_pivot.index) - 1)) * (len(colors) - 1))
                line_color = colors[color_index]
                fig_3d.add_trace(go.Scatter3d(
                    x=df_pivot.columns, y=[row_date] * len(df_pivot.columns), z=df_pivot.loc[row_date].values,
                    mode='lines', line=dict(width=4, color=line_color), name=str(row_date)
                ))
                
            fig_3d.update_layout(title=f"{start_str} 至 {end_str} - 多日电价瀑布折线图", autosize=False, height=750, showlegend=False,
                                 scene=dict(xaxis_title='时刻', yaxis_title='运行日', zaxis_title='价格/价差', camera=dict(eye=dict(x=1.5, y=1.5, z=0.5))))
            st.plotly_chart(fig_3d, use_container_width=True)

# ----------------- Tab 2: 现货宏观指标 -----------------
with tab2:
    st.header("现货市场多日趋势对比 (实际运行日对齐)")
    
    def plot_spot_trend(df, title, y_title="数值"):
        fig = go.Figure()
        for metric in df['指标名称'].unique():
            temp = df[df['指标名称'] == metric]
            # 🌟 改进 2：添加 connectgaps=True 让断点连线 🌟
            if temp['日前市场'].notna().any():
                fig.add_trace(go.Scatter(x=temp['运行日'], y=temp['日前市场'], mode='lines+markers', name=f"{metric} (日前)", connectgaps=True))
            if temp['实时市场'].notna().any():
                fig.add_trace(go.Scatter(x=temp['运行日'], y=temp['实时市场'], mode='lines+markers', name=f"{metric} (实时)", line=dict(dash='dash'), connectgaps=True))
        fig.update_layout(title=title, hovermode="x unified", height=450, yaxis_title=y_title)
        st.plotly_chart(apply_time_window(fig), use_container_width=True)
    
    price_df = df_spot_aligned[df_spot_aligned['单位'] == '元/兆瓦时']
    available_prices = price_df['指标名称'].unique().tolist()
    default_selections = [p for p in ['发电侧出清均价', '燃煤出清均价', '燃气出清均价', '海风出清均价'] if p in available_prices]
    selected_prices = st.multiselect("🔎 请选择【出清均价】对比指标：", options=available_prices, default=default_selections if default_selections else available_prices[:2])
    if selected_prices:
        plot_spot_trend(price_df[price_df['指标名称'].isin(selected_prices)], "各类机组与大盘出清均价走势", "元/兆瓦时")
    
    vol_df = df_spot_aligned[df_spot_aligned['指标名称'].isin(['发电侧总出清电量', '用电侧总出清电量'])]
    plot_spot_trend(vol_df, "发电侧与用电侧出清总电量", "兆瓦时")
    
    entity_df = df_spot_aligned[df_spot_aligned['指标名称'].isin(['售电公司', '批发用户', '电网企业', '发电企业', '发电机组'])]
    plot_spot_trend(entity_df, "市场主体与发电机组总台数", "家/台")
    
    gen_df = df_spot_aligned[df_spot_aligned['指标名称'].isin(['燃煤机组', '燃气机组', '新能源机组', '储能'])]
    plot_spot_trend(gen_df, "四大类机组开机/参与台数变化", "台")

# ----------------- Tab 3: 中长期市场复盘 -----------------
with tab3:
    st.header("中长期市场核心指标多日趋势")
    
    # 🌟 改进 3：过滤掉偶尔发生、数据极少的双边协商板块，仅保留集中竞价等 🌟
    allowed_ml_cats = [cat for cat in df_ml['指标大类'].unique() if cat not in ["中长期-多月绿电双边协商", "中长期-多月双边协商"]]
    
    for cat in allowed_ml_cats:
        with st.expander(f"📌 {cat}", expanded=True):
            cat_data = df_ml[df_ml['指标大类'] == cat]
            vol_data = cat_data[cat_data['单位'] == '兆瓦时']
            count_data = cat_data[cat_data['单位'] == '家']
            price_data = cat_data[cat_data['单位'] == '元/兆瓦时']
            
            fig_vol_count = make_subplots(specs=[[{"secondary_y": True}]])
            for metric in vol_data['指标名称'].unique():
                temp = vol_data[vol_data['指标名称'] == metric]
                # 🌟 改进 2：添加 connectgaps=True 🌟
                fig_vol_count.add_trace(go.Scatter(x=temp['日期'], y=temp['数值'], name=metric, mode='lines+markers', line=dict(width=3), connectgaps=True), secondary_y=False)
            for metric in count_data['指标名称'].unique():
                temp = count_data[count_data['指标名称'] == metric]
                fig_vol_count.add_trace(go.Bar(x=temp['日期'], y=temp['数值'], name=metric, opacity=0.4), secondary_y=True)
            
            fig_vol_count.update_layout(title_text="申报/成交电量 (折线) vs 主体数量 (柱状)", hovermode="x unified", barmode='group')
            st.plotly_chart(apply_time_window(fig_vol_count), use_container_width=True)

            if not price_data.empty:
                fig_price = px.line(price_data, x="日期", y="数值", color="指标名称", markers=True, title="均价指标追踪对比")
                # 🌟 px.line 开跨越空白的补丁 🌟
                fig_price.update_traces(connectgaps=True)
                fig_price.update_layout(hovermode="x unified")
                st.plotly_chart(apply_time_window(fig_price), use_container_width=True)
            
            source_data = df_ml_source[df_ml_source['指标大类'] == cat].dropna(subset=['成交电量', '成交均价'], how='all')
            if not source_data.empty:
                fig_source = make_subplots(specs=[[{"secondary_y": True}]])
                for unit_type in source_data['机组类型'].unique():
                    temp = source_data[source_data['机组类型'] == unit_type]
                    if temp['成交电量'].notna().any():
                        fig_source.add_trace(go.Bar(x=temp['日期'], y=temp['成交电量'], name=f"{unit_type} (电量)", opacity=0.6), secondary_y=False)
                    if temp['成交均价'].notna().any():
                        # 🌟 改进 2：添加 connectgaps=True 🌟
                        fig_source.add_trace(go.Scatter(x=temp['日期'], y=temp['成交均价'], name=f"{unit_type} (均价)", mode='lines+markers', connectgaps=True), secondary_y=True)
                fig_source.update_layout(title_text="各电源类型：成交电量 vs 成交均价", hovermode="x unified", barmode='group')
                st.plotly_chart(apply_time_window(fig_source), use_container_width=True)