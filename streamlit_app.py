# import streamlit as st
#
#
# def authenticated_menu():
#     # Show a navigation menu for authenticated users
#     st.sidebar.page_link("app.py", label="Switch accounts")
#     st.sidebar.page_link("pages/user.py", label="Your profile")
#     if st.session_state.role in ["admin", "super-admin"]:
#         st.sidebar.page_link("pages/home.py", label="Manage users")
#         st.sidebar.page_link(
#             "pages/super-home.py",
#             label="Manage admin access",
#             disabled=st.session_state.role != "super-admin",
#         )
#
#
# def unauthenticated_menu():
#     # Show a navigation menu for unauthenticated users
#     st.sidebar.page_link("app.py", label="Log in")
#
#
# def menu():
#     # Determine if a user is logged in or not, then show the correct
#     # navigation menu
#     if "role" not in st.session_state or st.session_state.role is None:
#         unauthenticated_menu()
#         return
#         authenticated_menu()
#
#
# def menu_with_redirect():
#     # Redirect users to the main page if not logged in, otherwise continue to
#     # render the navigation menu
#     if "role" not in st.session_state or st.session_state.role is None:
#         st.switch_page("app.py")
#     menu()


# import streamlit as st
# import streamlit_antd_components as sac
#
# # 定义不同页面的内容
# def home_page():
#     st.title("Home")
#     st.write("This is the home page.")
#
# def extract_net_value_page():
#     st.title("提取净值")
#     st.write("这是提取净值的页面。")
#
# def adjust_coefficient_page():
#     st.title("调整系数")
#     st.write("这是调整系数的页面。")
#
# def calculate_returns_page():
#     st.title("计算收益率")
#     st.write("这是计算收益率的页面。")
#
# def rolling_returns_page():
#     st.title("滚动收益率")
#     st.write("这是滚动收益率的页面。")
#
# # 设置侧边栏菜单
# with st.sidebar.container():
#     selected_menu_item = sac.menu([
#         sac.MenuItem('Home', icon='house-fill'),
#         sac.MenuItem('功能列表', icon='box-fill', description='main functions', children=[
#             sac.MenuItem('提取净值', icon='apple'),
#             sac.MenuItem('收益率计算', icon='git', children=[
#                 sac.MenuItem('调整系数', icon='google'),
#                 sac.MenuItem('计算收益率', icon='gitlab'),
#                 sac.MenuItem('滚动收益率', icon='wechat'),
#             ]),
#         ]),
#         sac.MenuItem('disabled', disabled=True),
#         sac.MenuItem(type='divider'),
#         sac.MenuItem('link', type='group', children=[
#             sac.MenuItem('antd-menu', icon='heart-fill', href='https://ant.design/components/menu#menu'),
#             sac.MenuItem('bootstrap-icon', icon='bootstrap-fill', href='https://icons.getbootstrap.com/'),
#         ]),
#     ], size='sm', open_all=True)
#
# # 根据选择的菜单项显示相应页面
# if selected_menu_item == 'home':
#     home_page()
# elif selected_menu_item == '提取净值':
#     extract_net_value_page()
# elif selected_menu_item == '调整系数':
#     adjust_coefficient_page()
# elif selected_menu_item == '计算收益率':
#     calculate_returns_page()
# elif selected_menu_item == '滚动收益率':
#     rolling_returns_page()
# else:
#     st.write("请选择一个页面。")

import streamlit as st
import streamlit_antd_components as sac
from menu import run_menu


# 获取当前查询参数
selected_page = st.query_params.get("page", "Home")

# 设置侧边栏菜单
with st.sidebar:
    selected_menu_item = sac.menu([
        sac.MenuItem('Home', icon='house-fill'),
        sac.MenuItem('功能列表', icon='box-fill', description='main functions', children=[
            sac.MenuItem('净值与收益率分析', icon='git', children=[
                sac.MenuItem('净值分析', icon='google'),
                sac.MenuItem('收益率分析', icon='gitlab'),
            ]),
        ]),
    ], size='sm', open_all=True)

# 更新 session_state 以反映用户选择
if selected_menu_item:
    st.session_state['selected_page'] = selected_menu_item

# 根据选择的菜单项显示相应页面
run_menu(st.session_state['selected_page'])
