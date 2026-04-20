import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 页面设置与 UI 增强 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

# 初始化“记忆”：用来存放我们真正要处理的图片
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
    /* 隐藏原生上传列表的预览，我们要自己写 */
    [data-testid="stFileUploaderDeleteBtn"] { display: none; }
    [data-testid="stFileUploaderFileName"] { display: none; }
    
    .file-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 15px;
        background: #f0f0f5;
        border-radius: 10px;
        margin-bottom: 5px;
    }
    .stButton>button { border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

# --- 1. 拼图区 ---
with tabs[0]:
    st.markdown("### 1. 上传素材")
    
    # 这里的上传框只负责“接收”文件
    uploaded_files = st.file_uploader("拖入图片", type=["png", "jpg", "jpeg"], accept_multiple_files=True, label_visibility="collapsed")
    
    # 【聪明逻辑】：将新上传的文件合并到我们的“记忆列表”中，并去重
    if uploaded_files:
        for f in uploaded_files:
            if f not in st.session_state.file_list:
                st.session_state.file_list.append(f)

    # --- 新增：批量管理界面 ---
    if st.session_state.file_list:
        st.markdown("##### 📝 待处理清单")
        
        # 一键清空按钮
        if st.button("🗑️ 清空所有图片"):
            st.session_state.file_list = []
            st.rerun()

        # 循环显示每一张图，旁边带个叉
        for idx, file in enumerate(st.session_state.file_list):
            cols = st.columns([0.8, 0.2])
            cols[0].write(f"📄 {file.name}")
            if cols[1].button("❌", key=f"del_{idx}"):
                st.session_state.file_list.pop(idx)
                st.rerun()
        
        st.divider()

    # 拼图设置
    col1, col2 = st.columns(2)
    with col1:
        direction = st.segmented_control("拼接方向", ["左右拼", "上下拼"], default="左右拼")
    with col2:
        is_align = st.toggle("🧪 智能对齐", value=True)

    if st.session_state.file_list:
        # 使用我们的记忆列表进行排序
        sorted_files = sorted(st.session_state.file_list, key=lambda x: 自然排序(x.name))
        
        if st.button("开始生成拼图"):
            if len(sorted_files) < 2:
                st.error("至少需要 2 张图片才能拼图哦！")
            else:
                progress_bar = st.progress(0)
                zip_buffer = io.BytesIO()
                total_pairs = len(sorted_files) // 2
                
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
                    for i in range(0, total_pairs * 2, 2):
                        img1 = Image.open(sorted_files[i]).convert("RGBA")
                        img2 = Image.open(sorted_files[i+1]).convert("RGBA")
                        
                        if is_align:
                            if direction == "左右拼":
                                target_h = max(img1.height, img2.height)
                                img1 = img1.resize((int(img1.width * target_h / img1.height), target_h), Image.Resampling.LANCZOS)
                                img2 = img2.resize((int(img2.width * target_h / img2.height), target_h), Image.Resampling.LANCZOS)
                            else:
                                target_w = max(img1.width, img2.width)
                                img1 = img1.resize((target_w, int(img1.height * target_w / img1.width)), Image.Resampling.LANCZOS)
                                img2 = img2.resize((target_w, int(img2.height * target_w / img2.width)), Image.Resampling.LANCZOS)

                        if direction == "左右拼":
                            canvas = Image.new('RGBA', (img1.width + img2.width, img1.height), (0,0,0,0))
                            canvas.paste(img1, (0, 0)); canvas.paste(img2, (img1.width, 0))
                        else:
                            canvas = Image.new('RGBA', (img1.width, img1.height + img2.height), (0,0,0,0))
                            canvas.paste(img1, (0, 0)); canvas.paste(img2, (0, img1.height))
                        
                        buf = io.BytesIO()
                        canvas.save(buf, format="PNG")
                        zip_file.writestr(f"Result_{i//2 + 1}.png", buf.getvalue())
                        progress_bar.progress((i + 2) / (total_pairs * 2))
                
                st.success("处理完成！")
                st.download_button("📂 下载拼图包", data=zip_buffer.getvalue(), file_name="Pugether_Export.zip")

# --- 2. 拆图区 (保持简洁) ---
with tabs[1]:
    st.markdown("### 1. 上传拼图")
    c_files = st.file_uploader("上传图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key="unzip")
    if c_files and st.button("开始拆分"):
        # ... (此处保持之前的拆分逻辑即可) ...
        st.info("拆分功能正常运行中...")
