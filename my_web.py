import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

# 初始化清空计数器（用于重置上传组件）
if 'p_clear_id' not in st.session_state: st.session_state.p_clear_id = 0
if 'u_clear_id' not in st.session_state: st.session_state.u_clear_id = 0

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
    /* 调整按钮样式，使其看起来更像功能键 */
    .stButton>button { border-radius: 10px; padding: 0.2rem 1rem; }
    .clear-text { font-size: 14px; color: #666; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

# --- 1. 拼图区 ---
with tabs[0]:
    # --- 顶层操作栏（模拟右上角清空） ---
    head_col1, head_col2 = st.columns([0.8, 0.2])
    head_col1.markdown("### 1. 上传素材")
    if head_col2.button("🧹 一键清空", key="p_clear_btn"):
        st.session_state.p_clear_id += 1
        st.rerun()

    # 上传组件（已删除下方清单显示）
    uploaded_files = st.file_uploader("拖入多张图片", type=["png", "jpg", "jpeg"], 
                                    accept_multiple_files=True, 
                                    label_visibility="collapsed", 
                                    key=f"p_up_{st.session_state.p_clear_id}")
    
    if uploaded_files:
        st.info(f"已选中 {len(uploaded_files)} 张图片")
        
        col1, col2 = st.columns(2)
        with col1: direction = st.segmented_control("方向", ["左右拼", "上下拼"], default="左右拼")
        with col2: is_align = st.toggle("🧪 智能对齐", value=True)

        if st.button("🚀 开始批量生成", key="p_start"):
            sorted_files = sorted(uploaded_files, key=lambda x: 自然排序(x.name))
            if len(sorted_files) < 2:
                st.warning("请上传至少 2 张图")
            else:
                status = st.empty(); progress = st.progress(0); zip_buf = io.BytesIO()
                total_pairs = len(sorted_files) // 2
                with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                    for i in range(0, total_pairs * 2, 2):
                        curr = i // 2 + 1
                        status.text(f"处理中: {curr}/{total_pairs}")
                        img1, img2 = Image.open(sorted_files[i]).convert("RGBA"), Image.open(sorted_files[i+1]).convert("RGBA")
                        if is_align:
                            if direction == "左右拼":
                                th = max(img1.height, img2.height)
                                img1 = img1.resize((int(img1.width*th/img1.height), th), Image.Resampling.LANCZOS)
                                img2 = img2.resize((int(img2.width*th/img2.height), th), Image.Resampling.LANCZOS)
                            else:
                                tw = max(img1.width, img2.width)
                                img1 = img1.resize((tw, int(img1.height*tw/img1.width)), Image.Resampling.LANCZOS)
                                img2 = img2.resize((tw, int(img2.height*tw/img2.width)), Image.Resampling.LANCZOS)
                        
                        if direction == "左右拼":
                            canvas = Image.new('RGBA', (img1.width+img2.width, img1.height), (0,0,0,0))
                            canvas.paste(img1,(0,0)); canvas.paste(img2,(img1.width,0))
                        else:
                            canvas = Image.new('RGBA', (img1.width, img1.height+img2.height), (0,0,0,0))
                            canvas.paste(img1,(0,0)); canvas.paste(img2,(0,img1.height))
                        
                        buf = io.BytesIO()
                        canvas.save(buf, format="PNG")
                        zf.writestr(f"Result_{curr}.png", buf.getvalue())
                        progress.progress((i+2)/(total_pairs*2))
                status.success("生成完毕！")
                st.download_button("📂 下载拼图包", zip_buf.getvalue(), "Pugether_Export.zip")

# --- 2. 拆图区 ---
with tabs[1]:
    # --- 顶层操作栏（模拟右上角清空） ---
    u_head1, u_head2 = st.columns([0.8, 0.2])
    u_head1.markdown("### 1. 上传拼图")
    if u_head2.button("🧹 一键清空", key="u_clear_btn"):
        st.session_state.u_clear_id += 1
        st.rerun()

    uploaded_unzip = st.file_uploader("上传 PNG 图片", type=["png"], 
                                     accept_multiple_files=True, 
                                     label_visibility="collapsed", 
                                     key=f"u_up_{st.session_state.u_clear_id}")
    
    if uploaded_unzip:
        st.info(f"已选中 {len(uploaded_unzip)} 张拼图")
        if st.button("🔍 立即拆分", key="u_start"):
            status_u = st.empty(); progress_u = st.progress(0); zip_buf_u = io.BytesIO()
            total = len(uploaded_unzip)
            with zipfile.ZipFile(zip_buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(uploaded_unzip):
                    status_u.text(f"拆解中: {idx+1}/{total}")
                    img = Image.open(f)
                    # 简化逻辑，此处保留你之前的自动检测拆分代码
                    arr = np.array(img.convert("L"))
                    h, w = arr.shape
                    # (此处 find_divider 逻辑内联简化，保持核心功能)
                    search_w = range(int(w*0.4), int(w*0.6))
                    best_col = w//2; min_v = float('inf')
                    for j in search_w:
                        v = np.var(arr[:, j])
                        if v < min_v: min_v, best_col = v, j
                    
                    res1 = img.crop((0,0,best_col,h))
                    res2 = img.crop((best_col,0,w,h))
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, "PNG"); res2.save(b2, "PNG")
                    zf.writestr(f"Split_{idx}_A.png", b1.getvalue())
                    zf.writestr(f"Split_{idx}_B.png", b2.getvalue())
                    progress_u.progress((idx+1)/total)
            st.success("拆分完毕！")
            st.download_button("📂 下载还原包", zip_buf_u.getvalue(), "Restored.zip")
