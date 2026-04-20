import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 苹果风格页面设置与 UI 增强 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

# 初始化“记忆”：用于存放拼图区的图片
if 'file_list' not in st.session_state:
    st.session_state.file_list = []

st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7; }
    .main .block-container {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(20px);
        padding: 3rem;
        border-radius: 30px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.05);
    }
    /* 隐藏拼图区原生的混乱预览 */
    .st-key-pintu_uploader [data-testid="stFileUploaderDeleteBtn"], 
    .st-key-pintu_uploader [data-testid="stFileUploaderFileName"] { display: none; }
    
    .stButton>button { border-radius: 12px; font-weight: 600; }
    h1 { font-weight: 700; color: #1D1D1F; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def find_divider(img):
    """自动寻找分割线的核心逻辑"""
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    mid_w, mid_h = w // 2, h // 2
    
    # 垂直扫描 (左右拼)
    search_w = range(int(w*0.4), int(w*0.6))
    best_col, min_var_w = mid_w, float('inf')
    for j in search_w:
        v = np.var(arr[:, j])
        if v < min_var_w: min_var_w, best_col = v, j
            
    # 水平扫描 (上下拼)
    search_h = range(int(h*0.4), int(h*0.6))
    best_row, min_var_h = mid_h, float('inf')
    for i in search_h:
        v = np.var(arr[i, :])
        if v < min_var_h: min_var_h, best_row = v, i
            
    return ("左右", best_col) if min_var_w < min_var_h else ("上下", best_row)

# --- 1. 拼图区 ---
with tabs[0]:
    st.markdown("### 1. 上传素材")
    # 使用 key="pintu_uploader" 方便 CSS 精确控制
    uploaded_files = st.file_uploader("拖入图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed", key="pintu_uploader")
    
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in [x.name for x in st.session_state.file_list]:
                st.session_state.file_list.append(f)

    # 批量管理列表
    if st.session_state.file_list:
        st.markdown("##### 📝 待处理清单")
        col_btn1, col_btn2 = st.columns([0.7, 0.3])
        if col_btn2.button("🗑️ 清空全部"):
            st.session_state.file_list = []
            st.rerun()

        for idx, file in enumerate(st.session_state.file_list):
            c = st.columns([0.85, 0.15])
            c[0].caption(f"📄 {file.name}")
            if c[1].button("❌", key=f"del_{file.name}_{idx}"):
                st.session_state.file_list.pop(idx)
                st.rerun()
        
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        direction = st.segmented_control("拼接方向", ["左右拼", "上下拼"], default="左右拼")
    with col2:
        is_align = st.toggle("智能对齐", value=True)

    if st.session_state.file_list
