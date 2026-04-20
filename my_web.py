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

    if st.session_state.file_list:
        sorted_files = sorted(st.session_state.file_list, key=lambda x: 自然排序(x.name))
        if st.button("🚀 开始拼图"):
            if len(sorted_files) < 2:
                st.warning("请至少上传 2 张图片")
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
                        
                        info = {"w1": img1.width, "h1": img1.height, "w2": img2.width, "h2": img2.height, "dir": direction}
                        meta = PngImagePlugin.PngInfo()
                        meta.add_text("recipe", json.dumps(info))
                        
                        buf = io.BytesIO()
                        canvas.save(buf, format="PNG", pnginfo=meta)
                        zip_file.writestr(f"Result_{i//2 + 1}.png", buf.getvalue())
                        progress_bar.progress((i + 2) / (total_pairs * 2))
                
                st.balloons()
                st.download_button("📂 下载拼图包", data=zip_buffer.getvalue(), file_name="Pugether_Export.zip")

# --- 2. 拆图区 (逻辑已完全修复) ---
with tabs[1]:
    st.markdown("### 1. 上传拼图")
    # 拆图区不需要复杂的管理列表，保持原生即可
    c_files = st.file_uploader("上传拼好的 PNG 图片", type=["png"], accept_multiple_files=True, label_visibility="collapsed", key="unzip_uploader")
    
    if c_files and st.button("🔍 立即拆分还原", key="unzip_btn"):
        progress_bar_u = st.progress(0)
        zip_buffer = io.BytesIO()
        total = len(c_files)
        
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, f in enumerate(c_files):
                img = Image.open(f)
                res1, res2 = None, None
                
                # 优先按元数据拆
                if "recipe" in img.info:
                    recipe = json.loads(img.info["recipe"])
                    if recipe["dir"] == "左右拼":
                        res1 = img.crop((0, 0, recipe["w1"], recipe["h1"]))
                        res2 = img.crop((recipe["w1"], 0, recipe["w1"] + recipe["w2"], recipe["h2"]))
                    else:
                        res1 = img.crop((0, 0, recipe["w1"], recipe["h1"]))
                        res2 = img.crop((0, recipe["h1"], recipe["w2"], recipe["h1"] + recipe["h2"]))
                else:
                    # 自动检测拆分
                    mode, pos = find_divider(img)
                    if mode == "左右":
                        res1 = img.crop((0, 0, pos, img.height))
                        res2 = img.crop((pos, 0, img.width, img.height))
                    else:
                        res1 = img.crop((0, 0, img.width, pos))
                        res2 = img.crop((0, pos, img.width, img.height))
                
                if res1 and res2:
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, format="PNG"); res2.save(b2, format="PNG")
                    zip_file.writestr(f"Split_{f.name}_A.png", b1.getvalue())
                    zip_file.writestr(f"Split_{f.name}_B.png", b2.getvalue())
                
                progress_bar_u.progress((idx + 1) / total)
        
        st.success("✨ 拆分任务已完成！")
        st.download_button("📂 下载还原包", data=zip_buffer.getvalue(), file_name="Pugether_Restored.zip")
