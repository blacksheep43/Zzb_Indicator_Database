from pages.home import show as home_show
from pages.returns.adjust_coefficient import show as adjust_coefficient_show
from pages.returns.calculate_returns import show as calculate_returns_show

# 定义一个字典，键为菜单项名称，值为对应的页面主函数
menu_dict = {
    "Home": home_show,
    "净值分析": adjust_coefficient_show,
    "收益率分析": calculate_returns_show,
}

def run_menu(selected_menu):
    # 根据用户选择的菜单项，调用对应的页面函数
    if selected_menu in menu_dict:
        menu_dict[selected_menu]()
    else:
        st.error(f"Page '{selected_menu}' not found.")
