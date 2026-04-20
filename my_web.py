import streamlit as st
from PIL import Image, PngImagePlugin
import json
import io
import zipfile
import re
import numpy as np

# --- 1. 页面设置 ---
st.set_page_config(page_title="Pugether Studio", page_icon="🔧", layout="centered")

# 初始化计数器
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
    .stButton>button { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("Pugether Studio")
tabs = st.tabs(["🧩 批量拼图", "🔩 快速拆图"])

def 自然排序(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', text)]

def find_divider_dynamic(img):
    """
    核心修复：每张图调用此函数，动态计算分割线。
    通过扫描图像中部的方差最小值来定位拼接缝隙。
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    mid_w, mid_h = w // 2, h // 2
    
    # 垂直扫描 (探测左右拼)
    search_w = range(int(w*0.3), int(w*0.7))
    best_col, min_var_w = mid_w, float('inf')
    for j in search_w:
        v = np.var(arr[:, j])
        if v < min_var_w:
            min_var_w, best_col = v, j
            
    # 水平扫描 (探测上下拼)
    search_h = range(int(h*0.3), int(h*0.7))
    best_row, min_var_h = mid_h, float('inf')
    for i in search_h:
        v = np.var(arr[i, :])
        if v < min_var_h:
            min_var_h, best_row = v, i
            
    # 比较哪个方向的“缝隙”更像一条直线（方差更小）
    if min_var_w <= min_var_h:
        return "左右", best_col
    else:
        return "上下", best_row

# --- 1. 拼图区 ---
with tabs[0]:
    h_col1, h_col2 = st.columns([0.8, 0.2])
    h_col1.markdown("### 1. 上传素材")
    if h_col2.button("🧹 一键清空", key="p_clear"):
        st.session_state.p_clear_id += 1
        st.rerun()

    uploaded_files = st.file_uploader("拖入多张图片", type=["png", "jpg", "jpeg"], 
                                    accept_multiple_files=True, label_visibility="collapsed", 
                                    key=f"p_up_{st.session_state.p_clear_id}")
    
    if uploaded_files:
        st.info(f"已选中 {len(uploaded_files)} 张图片")
        c1, c2 = st.columns(2)
        with c1: direction = st.segmented_control("方向", ["左右", "上下"], default="左右")
        with c2: is_align = st.toggle("无痕拼图", value=False)

        if st.button("🚀 开始批量拼图", key="p_go"):
            sorted_files = sorted(uploaded_files, key=lambda x: 自然排序(x.name))
            status = st.empty(); progress = st.progress(0); zip_buf = io.BytesIO()
            total_pairs = len(sorted_files) // 2
            
            with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zf:
                for i in range(0, total_pairs * 2, 2):
                    curr = i // 2 + 1
                    status.text(f"拼图中: {curr}/{total_pairs}")
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
                    
                    # 写入元数据方便精准拆分
                    info = {"w1": img1.width, "h1": img1.height, "dir": direction}
                    meta = PngImagePlugin.PngInfo(); meta.add_text("recipe", json.dumps(info))
                    
                    buf = io.BytesIO(); canvas.save(buf, format="PNG", pnginfo=meta)
                    zf.writestr(f"Result_{curr}.png", buf.getvalue())
                    progress.progress((i+2)/(total_pairs*2))
            st.success("拼图完成！")
            st.download_button("📂 下载拼图包", zip_buf.getvalue(), "Pugether_Export.zip")

# --- 2. 拆图区 ---
with tabs[1]:
    u_h1, u_h2 = st.columns([0.8, 0.2])
    u_h1.markdown("### 1. 上传拼图")
    if u_h2.button("🧹 一键清空", key="u_clear"):
        st.session_state.u_clear_id += 1
        st.rerun()

    uploaded_unzip = st.file_uploader("上传拼好的图片", type=["png"], 
                                     accept_multiple_files=True, label_visibility="collapsed", 
                                     key=f"u_up_{st.session_state.u_clear_id}")
    
    if uploaded_unzip:
        st.info(f"待处理: {len(uploaded_unzip)} 张")
        if st.button("🔍 智能拆分还原", key="u_go"):
            status_u = st.empty(); progress_u = st.progress(0); zip_buf_u = io.BytesIO()
            total = len(uploaded_unzip)
            
            with zipfile.ZipFile(zip_buf_u, "a", zipfile.ZIP_DEFLATED) as zf:
                for idx, f in enumerate(uploaded_unzip):
                    status_u.text(f"正在分析并拆解第 {idx+1} 张: {f.name}")
                    img = Image.open(f)
                    
                    # --- 核心逻辑：每张图都重新检测 ---
                    if "recipe" in img.info:
                        # 方案 A：如果有元数据，用元数据秒切（最准）
                        r = json.loads(img.info["recipe"])
                        if r.get("dir") == "左右拼":
                            res1 = img.crop((0, 0, r["w1"], img.height))
                            res2 = img.crop((r["w1"], 0, img.width, img.height))
                        else:
                            res1 = img.crop((0, 0, img.width, r["h1"]))
                            res2 = img.crop((0, r["h1"], img.width, img.height))
                    else:
                        # 方案 B：没有元数据，动态寻找当前图的分割线
                        mode, pos = find_divider_dynamic(img)
                        if mode == "左右":
                            res1 = img.crop((0, 0, pos, img.height))
                            res2 = img.crop((pos, 0, img.width, img.height))
                        else:
                            res1 = img.crop((0, 0, img.width, pos))
                            res2 = img.crop((0, pos, img.width, img.height))
                    
                    b1, b2 = io.BytesIO(), io.BytesIO()
                    res1.save(b1, "PNG"); res2.save(b2, "PNG")
                    zf.writestr(f"Split_{f.name}_A.png", b1.getvalue())
                    zf.writestr(f"Split_{f.name}_B.png", b2.getvalue())
                    progress_u.progress((idx+1)/total)
            
            st.success("所有图片已按各自的比例拆分完毕！")
            st.download_button("📂 下载还原包", zip_buf_u.getvalue(), "Restored.zip")
